import time
from copy import deepcopy
import heapq
from itertools import combinations
from typing import List, Tuple, Set

from multi_agent_path_finding.cbs.ct_node import CTNode
from multi_agent_path_finding.common.conflict import (
    Conflict,
    VertexConflict,
    EdgeConflict,
)
from multi_agent_path_finding.common.constraint import (
    Constraint,
    VertexConstraint,
    EdgeConstraint,
)
from multi_agent_path_finding.common.environment import Environment
from multi_agent_path_finding.common.point import Point
from multi_agent_path_finding.stastar.stastar import SpaceTimeAstar


class ConflictBasedSearch:
    def __init__(
        self, start_points: List[Point], goal_points: List[Point], env: Environment
    ):
        # check if the length of start_points and goal_points are the same
        if len(start_points) != len(goal_points):
            raise ValueError(
                f"Length of start_points and goal_points are not the same: {len(start_points)} != {len(goal_points)}"
            )

        self.start_points = start_points
        self.goal_points = goal_points
        self.robot_num = len(start_points)
        self.env = env

        self.open_set: List[CTNode] = list()
        self.individual_planners = [
            SpaceTimeAstar(start_point, goal_point, env)
            for start_point, goal_point in zip(start_points, goal_points)
        ]

    def plan(self):
        root_node = CTNode(
            constraints={},
            solution=[],
            cost=0,
        )
        for agent_id, individual_planner in enumerate(self.individual_planners):
            path = individual_planner.plan()
            if not path:
                print(f"Agent {agent_id} failed to find a path")
                return None
            root_node.solution.append(path)

        root_node.cost = self.calculate_cost(root_node.solution)

        # put root node into the priority queue
        heapq.heappush(self.open_set, root_node)
        ct_size = 0
        planning_avg_time = 0
        generate_avg_time = 0
        copy_avg_time = 0

        while self.open_set:
            # pop the node with the lowest cost
            cur_node = heapq.heappop(self.open_set)
            print(f"Current cost: {cur_node.cost}")
            print(f"CT size: {ct_size}")

            # find the first conflict
            conflict = self.find_first_conflict(cur_node.solution)

            # if there is no conflict, return the solution
            if not conflict:
                return cur_node.solution

            generate_start_time = time.time()
            # if there is a conflict, generate two new nodes
            for agent_id in conflict.agent_ids:
                # if the agent has already passed the conflict time, ignore it
                if (
                    type(conflict) == VertexConflict
                    and len(cur_node.solution[agent_id]) <= conflict.time
                ) or (
                    type(conflict) == EdgeConflict
                    and len(cur_node.solution[agent_id]) <= conflict.times[1]
                ):
                    continue
                # generate child node from the current node
                copy_start_time = time.time()
                new_node = deepcopy(cur_node)
                copy_avg_time += time.time() - copy_start_time
                # print(f"Deepcopy time: {time.time() - deepcopy_start_time}")

                plan_start_time = time.time()
                # generate constraint from the conflict
                new_constraint = self.generate_constraint_from_conflict(
                    agent_id, conflict
                )

                # add the constraint to the child node
                new_node.constraints.setdefault(agent_id, []).append(new_constraint)
                new_node.solution[agent_id] = self.individual_planners[agent_id].plan(
                    constraints=new_node.constraints[agent_id]
                )
                # print(f"Plan time: {time.time() - plan_start_time}")
                if not new_node.solution[agent_id]:
                    continue
                new_node.cost = self.calculate_cost(new_node.solution)
                heapq.heappush(self.open_set, new_node)
                ct_size += 1
                planning_avg_time += time.time() - plan_start_time
            generate_avg_time += time.time() - generate_start_time

            print(f"Planning time: {planning_avg_time / ct_size}")
            print(f"Copy time: {copy_avg_time / ct_size}")
            print(f"Generate time: {generate_avg_time / ct_size}")
        return None

    @staticmethod
    def generate_constraint_from_conflict(
        agent_id: int, conflict: Conflict
    ) -> Constraint:
        if isinstance(conflict, VertexConflict):
            return VertexConstraint(
                agent_id=agent_id,
                point=conflict.point,
                time=conflict.time,
            )
        elif isinstance(conflict, EdgeConflict):
            return EdgeConstraint(
                agent_id=agent_id,
                points=conflict.points[agent_id],
                times=conflict.times,
            )
        else:
            raise ValueError(f"Unknown conflict type: {type(conflict)}")

    @staticmethod
    def get_state(agent_id: int, time: int, solution: List[List[Tuple[Point, int]]]):
        if time >= len(solution[agent_id]):
            return solution[agent_id][-1][0]
        else:
            return solution[agent_id][time][0]

    def calculate_cost(self, solution: List[List[Tuple[Point, int]]]) -> int:
        cost = 0
        for i in range(self.robot_num):
            cost += len(solution[i]) - 1
        return cost

    def find_first_conflict(self, solution: List[List[Tuple[Point, int]]]) -> Conflict:
        # Vertex Conflict
        for agent1, agent2 in combinations(range(self.robot_num), 2):
            max_time = max(len(solution[agent1]), len(solution[agent2]))
            for time in range(max_time):
                point1 = self.get_state(agent1, time, solution)
                point2 = self.get_state(agent2, time, solution)
                if point1 == point2:
                    return VertexConflict(
                        agent_ids=[agent1, agent2],
                        point=point1,
                        time=time,
                    )

        # Edge Conflict
        for agent1, agent2 in combinations(range(self.robot_num), 2):
            max_time = max(len(solution[agent1]), len(solution[agent2]))
            for time in range(max_time - 1):
                prev_point1 = self.get_state(agent1, time, solution)
                next_point1 = self.get_state(agent1, time + 1, solution)
                prev_point2 = self.get_state(agent2, time, solution)
                next_point2 = self.get_state(agent2, time + 1, solution)

                if prev_point1 == next_point2 and prev_point2 == next_point1:
                    return EdgeConflict(
                        agent_ids=[agent1, agent2],
                        points={
                            agent1: (prev_point1, next_point1),
                            agent2: (prev_point2, next_point2),
                        },
                        times=(time, time + 1),
                    )
