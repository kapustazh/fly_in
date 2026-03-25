from __future__ import annotations
import math
from math import hypot, inf
import heapq

from dataclasses import dataclass

from game import GameWorld
from routing_costs import RoutingCostsError, ZoneMovementModel


class PathfindingError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Pathfinding error: {detail}")


@dataclass(order=True)
class PriorityState:
    """Priority queue entry for the A* open set.

    Ordering is lexicographic (dataclass order=True):
    1) f_score (lowest first),
    2) tie_priority (0 = priority zone, preferred per subject VII.1),
    3) h_score,
    4) zone name.

    A* notation:
    - g_score: known cost from start to current zone.
    - h_score: heuristic estimate from current zone to goal.
    - f_score: total estimated cost, f = g + h.
    """

    f_score: float
    tie_priority: int
    h_score: float
    zone: str


class Heuristic:
    @staticmethod
    def euclidean_distance(
        zone_one: tuple[int, int],
        zone_two: tuple[int, int],
    ) -> float:
        return hypot(zone_one[0] - zone_two[0], zone_one[1] - zone_two[1])


class AStar:
    """A* pathfinder over parsed zones/connections graph."""

    def __init__(
        self,
        game_world: GameWorld,
        movement: ZoneMovementModel | None = None,
    ) -> None:
        self.zones = game_world.zones
        self.connections = game_world.connections
        self._movement = movement or ZoneMovementModel(game_world.zones)

    def _validate_zone_name(self, zone_name: str) -> None:
        if zone_name not in self.zones:
            raise PathfindingError(f"Zone '{zone_name}' is not present")

    def _movement_cost(self, zone_name: str) -> float:
        try:
            return self._movement.enter_cost(zone_name)
        except RoutingCostsError as e:
            raise PathfindingError(str(e)) from e

    def _is_passable(self, zone_name: str) -> bool:
        try:
            return self._movement.is_passable(zone_name)
        except RoutingCostsError as e:
            raise PathfindingError(str(e)) from e

    def _link_capacity(self, from_zone_name: str, to_zone_name: str) -> int:
        block = self.connections.get(from_zone_name)
        if block is None:
            return 0
        meta = block.get("metadata", {}).get(to_zone_name)
        if meta is None:
            return 1
        return max(1, getattr(meta, "max_link_capacity", 1))

    def _zone_max_drones(self, zone_name: str) -> int:
        zone = self.zones.get(zone_name)
        if zone is None:
            return 1
        meta = zone.get("metadata")
        if meta is None:
            return 1
        return max(1, getattr(meta, "max_drones", 1))

    def find_path(
        self,
        start_zone: str,
        end_zone: str,
        *,
        link_path_counts: dict[frozenset[str], int] | None = None,
        zone_route_counts: dict[str, int] | None = None,
        exempt_capacity_zones: frozenset[str] | None = None,
    ) -> list[str]:
        """Return the lowest-cost path.

        link_path_counts: planned-path count per unordered zone pair; A* rejects a step when
        the count reaches that connection's max_link_capacity.
        zone_route_counts: planned-path count per zone; A* rejects entering a neighbor when
        the count reaches that zone's max_drones, except for names in exempt_capacity_zones
        (start hub and end hub are passed in from the armada).
        """
        self._validate_zone_name(start_zone)
        self._validate_zone_name(end_zone)

        if start_zone == end_zone:
            return [start_zone]

        if not self._is_passable(start_zone):
            raise PathfindingError(f"Start zone '{start_zone}' is blocked")
        if not self._is_passable(end_zone):
            raise PathfindingError(f"End zone '{end_zone}' is blocked")

        open_heap: list[PriorityState] = []
        came_from: dict[str, str] = {}

        g_score: dict[str, float] = {name: inf for name in self.zones}
        g_score[start_zone] = 0.0

        h_start = self._heuristic(start_zone, end_zone)
        start_tie = 0 if self._movement.is_priority(start_zone) else 1

        heapq.heappush(
            open_heap,
            PriorityState(h_start, start_tie, h_start, start_zone),
        )
        closed_set: set[str] = set()

        while open_heap:
            expanded_zone_name = heapq.heappop(open_heap).zone
            if expanded_zone_name in closed_set:
                continue

            if expanded_zone_name == end_zone:
                return self._reconstruct_path(came_from, end_zone)

            closed_set.add(expanded_zone_name)

            for adjacent_zone_name in self._neighbors(expanded_zone_name):
                if adjacent_zone_name in closed_set:
                    continue
                if not self._is_passable(adjacent_zone_name):
                    continue

                if link_path_counts is not None:
                    undirected_link_key = frozenset(
                        {expanded_zone_name, adjacent_zone_name}
                    )
                    link_capacity = self._link_capacity(
                        expanded_zone_name,
                        adjacent_zone_name,
                    )
                    if link_path_counts.get(undirected_link_key, 0) >= link_capacity:
                        continue

                if (
                    zone_route_counts is not None
                    and exempt_capacity_zones is not None
                    and adjacent_zone_name not in exempt_capacity_zones
                ):
                    zone_capacity = self._zone_max_drones(adjacent_zone_name)
                    if (
                        zone_route_counts.get(adjacent_zone_name, 0)
                        >= zone_capacity
                    ):
                        continue

                candidate_g = g_score[expanded_zone_name] + self._movement_cost(
                    adjacent_zone_name
                )
                if candidate_g >= g_score[adjacent_zone_name]:
                    continue

                came_from[adjacent_zone_name] = expanded_zone_name
                g_score[adjacent_zone_name] = candidate_g
                h_neighbor = self._heuristic(adjacent_zone_name, end_zone)
                f_neighbor = candidate_g + h_neighbor
                nb_tie = (
                    0 if self._movement.is_priority(adjacent_zone_name) else 1
                )
                heapq.heappush(
                    open_heap,
                    PriorityState(
                        f_neighbor, nb_tie, h_neighbor, adjacent_zone_name
                    ),
                )

        raise PathfindingError(
            f"No path exists between '{start_zone}' and '{end_zone}'"
        )

    def _neighbors(self, zone_name: str) -> set[str]:
        zone_connections = self.connections.get(zone_name)
        if zone_connections is None:
            return set()
        return set(zone_connections.get("connections", set()))

    def _heuristic(self, zone_one: str, zone_two: str) -> float:
        first_xy = self._coordinates(zone_one)
        second_xy = self._coordinates(zone_two)
        return Heuristic.euclidean_distance(first_xy, second_xy)

    def _coordinates(self, zone_name: str) -> tuple[int, int]:
        zone = self.zones.get(zone_name)
        if zone is None:
            raise PathfindingError(f"Unknown zone '{zone_name}'")

        coordinates = zone.get("coordinates")
        if coordinates is None:
            raise PathfindingError(
                f"Wrong coordinates '{coordinates} of the zone: '{zone_name}'"
            )
        grid_x, grid_y = coordinates
        if not isinstance(grid_x, int) or not isinstance(grid_y, int):
            raise PathfindingError(
                f"Zone '{zone_name}' has invalid coordinates {coordinates}"
            )

        return (grid_x, grid_y)

    @staticmethod
    def _reconstruct_path(
        came_from: dict[str, str],
        end_zone: str,
    ) -> list[str]:
        path = [end_zone]
        while path[-1] in came_from:
            path.append(came_from[path[-1]])
        path.reverse()
        return path


@dataclass(frozen=True)
class PlannedRoute:
    zone_names: list[str]
    total_enter_cost: float


class RoutePlanner:
    """Planning API: returns a route object; A* is the implementation."""

    def __init__(self, game_world: GameWorld) -> None:
        self._movement = ZoneMovementModel(game_world.zones)
        self._astar = AStar(game_world, self._movement)

    @property
    def movement_model(self) -> ZoneMovementModel:
        return self._movement

    def plan(
        self,
        start_zone: str,
        end_zone: str,
        *,
        link_path_counts: dict[frozenset[str], int] | None = None,
        zone_route_counts: dict[str, int] | None = None,
        exempt_capacity_zones: frozenset[str] | None = None,
    ) -> PlannedRoute:
        zone_names = self._astar.find_path(
            start_zone,
            end_zone,
            link_path_counts=link_path_counts,
            zone_route_counts=zone_route_counts,
            exempt_capacity_zones=exempt_capacity_zones,
        )
        total_enter = math.fsum(
            self._movement.enter_cost(z) for z in zone_names[1:]
        )
        return PlannedRoute(
            zone_names=list(zone_names),
            total_enter_cost=total_enter,
        )
