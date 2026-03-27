"""Zone-graph A* routing and a small PlannedRoute result type."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import hypot, inf
from typing import Any, Dict

from collections.abc import Mapping

from game import GameWorld
from routing_costs import RoutingCostsError, ZoneMovementModel


class PathfindingError(Exception):
    """Raised when start/end are invalid or no route exists."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Pathfinding error: {detail}")


@dataclass(frozen=True)
class PlannedRoute:
    """Ordered zone names from start to goal (capacity-agnostic shortest path).

    When timed_states is set (fleet timed planner), each entry is (zone, global
    turn index t) so simulation can align with link/zone reservations.
    """

    zone_names: list[str]
    timed_states: tuple[tuple[str, int], ...] | None = None


@dataclass(frozen=True, order=True)
class _AStarHeapEntry:
    """Heap row: order by f_score, tie_priority, h_score, zone name."""

    f_score: float
    tie_priority: int
    h_score: float
    zone: str


class RoutePlanner:
    """A* over zones/connections; exposes movement_model for simulation."""

    def __init__(self, game_world: GameWorld) -> None:
        """Index zones and connections and build a ZoneMovementModel."""
        self._zones: Mapping[str, Dict[str, Any]] = game_world.zones
        self._connections: Mapping[str, Dict[str, Any]] = (
            game_world.connections
        )
        self._movement = ZoneMovementModel(game_world.zones)

    @property
    def movement_model(self) -> ZoneMovementModel:
        """Per-zone costs and passability used by simulation and timed search."""
        return self._movement

    def plan(self, start_zone: str, end_zone: str) -> PlannedRoute:
        """Return a minimum-cost zone path from *start_zone* to *end_zone*."""
        zones = self._zones
        connections = self._connections
        movement = self._movement

        if start_zone not in zones or end_zone not in zones:
            raise PathfindingError(
                f"Zone '{start_zone}' or '{end_zone}' is not present"
            )
        if start_zone == end_zone:
            return PlannedRoute(zone_names=[start_zone])

        try:
            if not movement.is_passable(start_zone):
                raise PathfindingError(f"Start zone '{start_zone}' is blocked")
            if not movement.is_passable(end_zone):
                raise PathfindingError(f"End zone '{end_zone}' is blocked")
        except RoutingCostsError as e:
            raise PathfindingError(str(e)) from e

        open_heap: list[_AStarHeapEntry] = []
        came_from: dict[str, str] = {}
        g_score: dict[str, float] = {name: inf for name in zones}
        g_score[start_zone] = 0.0

        start_h = RoutePlanner._heuristic(zones, start_zone, end_zone)
        start_tie = 0 if movement.is_priority(start_zone) else 1
        heapq.heappush(
            open_heap,
            _AStarHeapEntry(start_h, start_tie, start_h, start_zone),
        )
        closed: set[str] = set()

        while open_heap:
            current_zone = heapq.heappop(open_heap).zone
            if current_zone in closed:
                continue
            if current_zone == end_zone:
                return PlannedRoute(
                    zone_names=RoutePlanner._reconstruct_path(
                        came_from, end_zone
                    )
                )
            closed.add(current_zone)
            connection_block = connections.get(current_zone)
            if connection_block is None:
                continue
            for neighbor_zone in connection_block.get("connections", set()):
                if neighbor_zone in closed:
                    continue
                try:
                    if not movement.is_passable(neighbor_zone):
                        continue
                    enter_cost = movement.enter_cost(neighbor_zone)
                except RoutingCostsError as e:
                    raise PathfindingError(str(e)) from e
                tentative_g = g_score[current_zone] + enter_cost
                if tentative_g >= g_score[neighbor_zone]:
                    continue
                came_from[neighbor_zone] = current_zone
                g_score[neighbor_zone] = tentative_g
                neighbor_h = RoutePlanner._heuristic(
                    zones, neighbor_zone, end_zone
                )
                neighbor_tie = 0 if movement.is_priority(neighbor_zone) else 1
                heapq.heappush(
                    open_heap,
                    _AStarHeapEntry(
                        tentative_g + neighbor_h,
                        neighbor_tie,
                        neighbor_h,
                        neighbor_zone,
                    ),
                )

        raise PathfindingError(
            f"No path exists between '{start_zone}' and '{end_zone}'"
        )

    @staticmethod
    def _heuristic(
        zones: Mapping[str, Dict[str, Any]], from_zone: str, to_zone: str
    ) -> float:
        """Straight-line grid distance between zone centers (admissible for A*)."""
        ax, ay = RoutePlanner._grid_xy(zones, from_zone)
        bx, by = RoutePlanner._grid_xy(zones, to_zone)
        return hypot(ax - bx, ay - by)

    @staticmethod
    def _grid_xy(
        zones: Mapping[str, Dict[str, Any]], zone_name: str
    ) -> tuple[int, int]:
        """Integer (x, y) tile coordinates for *zone_name*."""
        z = zones.get(zone_name)
        if z is None:
            raise PathfindingError(f"Unknown zone '{zone_name}'")
        c = z.get("coordinates")
        if c is None:
            raise PathfindingError(
                f"Wrong coordinates '{c} of the zone: '{zone_name}'"
            )
        gx, gy = c
        if not isinstance(gx, int) or not isinstance(gy, int):
            raise PathfindingError(
                f"Zone '{zone_name}' has invalid coordinates {c}"
            )
        return (gx, gy)

    @staticmethod
    def _reconstruct_path(
        came_from: dict[str, str], end_zone: str
    ) -> list[str]:
        """Walk parent pointers from *end_zone* back to the start."""
        path = [end_zone]
        while path[-1] in came_from:
            path.append(came_from[path[-1]])
        path.reverse()
        return path
