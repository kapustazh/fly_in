from __future__ import annotations
from dataclasses import dataclass
from math import hypot, inf
import heapq
from game import GameWorld
from parser import ZoneTypes


class PathfindingError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Pathfinding error: {detail}")


@dataclass(order=True)
class PriorityState:
    """Priority queue entry for the A* open set.

    Ordering is lexicographic (because ``order=True``):
    1) ``f_score`` (lowest first),
    2) ``h_score`` (tie-break),
    3) ``zone`` (deterministic final tie-break).

    A* notation:
    - ``g_score``: known cost from start to current zone.
    - ``h_score``: heuristic estimate from current zone to goal.
    - ``f_score``: total estimated cost, ``f = g + h``.
    """

    f_score: float
    h_score: float
    zone: str


class Heuristic:
    @staticmethod
    def euclidean_distance(
        zone_one: tuple[int, int],
        zone_two: tuple[int, int],
    ) -> float:
        return hypot(zone_one[0] - zone_two[0], zone_one[1] - zone_two[1])


# Excplicit check isn't always bad, it is what it is
# "Key from dicts of A* 24.03.2026"


class AStar:
    """A* pathfinder over parsed zones/connections graph."""

    def __init__(self, game_world: GameWorld) -> None:
        self.game_world = game_world
        self.zones = game_world.zones
        self.connections = game_world.connections

    def _validate_zone_name(self, zone_name: str) -> None:
        if zone_name not in self.zones:
            raise PathfindingError(f"Zone '{zone_name}' is not present")

    def _get_zone_type(self, zone_name: str) -> ZoneTypes:
        """Extract zone type from metadata, defaulting to NORMAL."""
        zone = self.zones.get(zone_name)
        if zone is None:
            raise PathfindingError(f"Unknown zone '{zone_name}'")

        metadata = zone.get("metadata")
        if metadata is None:
            return ZoneTypes.NORMAL

        raw_zone = getattr(metadata, "zone", ZoneTypes.NORMAL)
        if isinstance(raw_zone, ZoneTypes):
            return raw_zone
        return ZoneTypes(str(raw_zone))

    def _movement_cost(self, zone_name: str) -> float:
        """Return the movement cost for entering a zone."""
        zone_type = self._get_zone_type(zone_name)
        if zone_type == ZoneTypes.BLOCKED:
            return inf
        return zone_type.cost

    def _is_passable(self, zone_name: str) -> bool:
        """Check if a zone is passable (not blocked)."""
        zone_type = self._get_zone_type(zone_name)
        return zone_type.is_passable

    def find_path(self, start_zone: str, end_zone: str) -> list[str]:
        """Return the shortest-cost path as a list of zone names."""
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

        heapq.heappush(open_heap, PriorityState(h_start, h_start, start_zone))
        closed_set: set[str] = set()

        while open_heap:
            current = heapq.heappop(open_heap).zone
            if current in closed_set:
                continue

            if current == end_zone:
                return self._reconstruct_path(came_from, end_zone)

            closed_set.add(current)

            for neighbor in self._neighbors(current):
                if neighbor in closed_set:
                    continue
                if not self._is_passable(neighbor):
                    continue

                candidate_g = g_score[current] + self._movement_cost(neighbor)
                if candidate_g >= g_score[neighbor]:
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = candidate_g
                h_neighbor = self._heuristic(neighbor, end_zone)
                f_neighbor = candidate_g + h_neighbor
                heapq.heappush(
                    open_heap,
                    PriorityState(f_neighbor, h_neighbor, neighbor),
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
        first, second = coordinates
        if not isinstance(first, int) or not isinstance(second, int):
            raise PathfindingError(
                f"Zone '{zone_name}' has invalid coordinates {coordinates}"
            )

        return (first, second)

    def _find_hub_by_type(self, hub_type: str) -> str:
        for name, zone in self.zones.items():
            if zone.get("hub_type") == hub_type:
                return name
        raise PathfindingError(f"Hub type '{hub_type}' was not found")

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
