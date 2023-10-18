from dataclasses import dataclass
from typing import List, Tuple, Dict

from multi_agent_path_finding.common.point import Point
from multi_agent_path_finding.common.constraint import Constraint
from multi_agent_path_finding.stastar_epsilon_dp.stastar_epsilon_dp import SpaceTimeAstarEpsilonDP
from multi_agent_path_finding.stastar_epsilon_dp.node import Node


@dataclass
class CTNode:
    constraints: Dict[int, List[Constraint]]
    solution: List[List[Tuple[Point, int]]]
    cost: int
    f_mins: List[int]
    lower_bound: int
    focal_heuristic: int
    individual_planners: List[SpaceTimeAstarEpsilonDP] = None

    def __lt__(self, other):
        if self.focal_heuristic != other.focal_heuristic:
            return self.focal_heuristic < other.focal_heuristic
        return self.cost < other.cost

    def __hash__(self):
        return hash(str(self.solution))

    def deepcopy(self, agent_id: int = None):
        return CTNode(
            constraints=self.constraints.copy(),
            solution=self.solution.copy(),
            cost=self.cost,
            f_mins=self.f_mins.copy(),
            lower_bound=self.lower_bound,
            focal_heuristic=self.focal_heuristic,
            individual_planners=self.copy_planners(agent_id),
        )

    def copy_planners(self, agent_id: int = None):
        individual_planners = self.individual_planners.copy()
        individual_planners[agent_id] = self.deepcopy_planner(agent_id)
        return individual_planners

    def deepcopy_planner(self, agent_id: int = None):
        new_individual_planner = SpaceTimeAstarEpsilonDP(
            start_point=self.individual_planners[agent_id].start_point,
            goal_point=self.individual_planners[agent_id].goal_point,
            env=self.individual_planners[agent_id].env,
            w=self.individual_planners[agent_id].w,
        )

        new_individual_planner.open_set.remove(new_individual_planner.start_node)
        new_individual_planner.focal_set.remove(new_individual_planner.start_node)

        self.post_order_copy(
            self.individual_planners[agent_id].start_node,
            new_individual_planner.start_node,
            new_individual_planner,
            agent_id,
        )

        new_individual_planner.closed_set.add(new_individual_planner.start_node)
        return new_individual_planner

    def post_order_copy(self, org_node, new_node, new_individual_planner, agent_id):
        for org_child in org_node.children:
            new_child = Node(org_child.point, org_child.time)
            new_child.parent = new_node
            new_node.children.append(new_child)
            new_child.g_score = org_child.g_score
            new_child.h_score = org_child.h_score
            new_child.f_score = org_child.f_score
            new_node.d_score = org_node.d_score
            if org_child in self.individual_planners[agent_id].open_set:
                new_individual_planner.open_set.add(new_child)
            if org_child in self.individual_planners[agent_id].focal_set:
                new_individual_planner.focal_set.add(new_child)
            if org_child in self.individual_planners[agent_id].closed_set:
                new_individual_planner.closed_set.add(new_child)
            self.post_order_copy(org_child, new_child, new_individual_planner, agent_id)
