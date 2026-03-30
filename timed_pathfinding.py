"""Timed routing: shared types, space–time search, and per-turn capacity.

Turn-based planning capacity is per turn, not per route name.
Static overlap counts treat every shared zone as conflict; here, limits apply
only when drones share a zone or link on the *same* turn.

Routes use TimedPathfinder and FleetRoutePlanner; per-zone costs use
routing_costs.ZoneMovementModel.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import inf
from typing import Any

from collections.abc import Mapping

from game import GameWorld
from routing_costs import RoutingCostsError, ZoneMovementModel


class PathfindingError(Exception):
    """Raised when timed search cannot connect zones or hits invalid state."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Pathfinding error: {detail}")


@dataclass(frozen=True)
class PlannedRoute:
    """Zone sequence for a drone; optional timed (zone, turn) chain.

    timed_states is None when the planner did not produce a timed path.
    """

    zone_names: list[str]
    timed_states: tuple[tuple[str, int], ...] | None = None


class TimedGraph:
    """Static helpers to read zone graph metadata for timed routing."""

    @staticmethod
    def link_capacity(
        connections: Mapping[str, dict[str, Any]],
        zone_a: str,
        zone_b: str,
    ) -> int:
        """Max drones on this undirected bridge in one simulation turn."""
        block = connections.get(zone_a)
        if block is None:
            return 0
        meta = block.get("metadata", {}).get(zone_b)
        if meta is None:
            return 1
        capacity = getattr(meta, "max_link_capacity", 1)
        return capacity

    @staticmethod
    def zone_max_drones(
        zones: Mapping[str, dict[str, Any]], zone_name: str
    ) -> int:
        """Max drones that may share *zone_name* on one turn."""
        zone = zones.get(zone_name)
        if zone is None:
            return 1
        meta = zone.get("metadata")
        if meta is None:
            return 1
        limit = getattr(meta, "max_drones", 1)
        return limit

    @staticmethod
    def neighbors(
        connections: Mapping[str, dict[str, Any]], zone_name: str
    ) -> set[str]:
        """Adjacent zone names reachable from *zone_name* in one step."""
        block = connections.get(zone_name)
        if block is None:
            return set()
        return set(block.get("connections", set()))


class TurnCapacityTracker:
    """Sparse per-turn usage for zones (capacity) and undirected links."""

    def __init__(
        self,
        zones: Mapping[str, dict[str, Any]],
        connections: Mapping[str, dict[str, Any]],
        *,
        exempt_zone_capacity: frozenset[str],
    ) -> None:
        """Track per-turn zone/link use; *exempt_zone_capacity* skips caps."""
        self._zones = zones
        self._connections = connections
        self._exempt = exempt_zone_capacity
        self._zone_use: dict[tuple[str, int], int] = {}
        self._link_use: dict[tuple[frozenset[str], int], int] = {}

    def can_occupy_zone_at(self, zone_name: str, turn: int) -> bool:
        """Whether one more drone could enter *zone_name* at *turn*."""
        if zone_name in self._exempt:
            return True
        cap = TimedGraph.zone_max_drones(self._zones, zone_name)
        return self._zone_use.get((zone_name, turn), 0) < cap

    def add_zone_turn(self, zone_name: str, turn: int) -> None:
        """Record one drone in *zone_name* at *turn* (unless exempt)."""
        if zone_name in self._exempt:
            return
        key = (zone_name, turn)
        self._zone_use[key] = self._zone_use.get(key, 0) + 1

    def can_use_link_during(
        self, zone_from: str, zone_to: str, t_start: int, t_end: int
    ) -> bool:
        """True if link capacity holds each turn in [t_start, t_end)."""
        cap = TimedGraph.link_capacity(self._connections, zone_from, zone_to)
        if cap <= 0:
            return False
        key_bridge = frozenset({zone_from, zone_to})
        for occupancy_turn in range(t_start, t_end):
            if self._link_use.get((key_bridge, occupancy_turn), 0) >= cap:
                return False
        return True

    def can_use_dest_zone_during(
        self, zone_to: str, t_start: int, t_end: int
    ) -> bool:
        """True if destination zone has spare capacity each turn."""
        if zone_to in self._exempt:
            return True
        cap = TimedGraph.zone_max_drones(self._zones, zone_to)
        for occupancy_turn in range(t_start, t_end):
            if self._zone_use.get((zone_to, occupancy_turn), 0) >= cap:
                return False
        return True

    def can_move(
        self, zone_from: str, zone_to: str, t_start: int, t_end: int
    ) -> bool:
        """Whether move zone_from->zone_to over [t_start, t_end) is allowed."""
        return self.can_use_link_during(
            zone_from, zone_to, t_start, t_end
        ) and self.can_use_dest_zone_during(zone_to, t_start, t_end)

    def reserve_move(
        self, zone_from: str, zone_to: str, t_start: int, t_end: int
    ) -> None:
        """Commit link and destination-zone usage for an in-flight move."""
        key_bridge = frozenset({zone_from, zone_to})
        for occupancy_turn in range(t_start, t_end):
            bridge_turn_key = (key_bridge, occupancy_turn)
            self._link_use[bridge_turn_key] = (
                self._link_use.get(bridge_turn_key, 0) + 1
            )
            self.add_zone_turn(zone_to, occupancy_turn)

    def reserve_wait_turn(self, zone_name: str, turn: int) -> None:
        """Record a one-turn wait (hover) in *zone_name* at *turn*."""
        self.add_zone_turn(zone_name, turn)

    def reserve_timed_state_chain(self, states: list[tuple[str, int]]) -> None:
        """Apply reserve_wait_turn and reserve_move along a timed path."""
        for step_index in range(len(states) - 1):
            from_zone, turn_at_from = states[step_index]
            to_zone, turn_at_to = states[step_index + 1]
            if from_zone == to_zone:
                if turn_at_to != turn_at_from + 1:
                    raise ValueError("Invalid wait step in timed chain")
                self.reserve_wait_turn(from_zone, turn_at_from)
            else:
                if turn_at_to <= turn_at_from:
                    raise ValueError("Invalid move step in timed chain")
                self.reserve_move(from_zone, to_zone, turn_at_from, turn_at_to)


class TimedPathfinder:
    """Time-expanded search: zone path with waits + (zone, t) chain."""

    @staticmethod
    def _push(
        open_heap: list[tuple[int, int, str, int]],
        movement: ZoneMovementModel,
        cumulative_cost: int,
        zone_name: str,
        turn_index: int,
    ) -> None:
        """Enqueue a search state with priority zones explored first."""
        priority_rank = 0 if movement.is_priority(zone_name) else 1
        heapq.heappush(
            open_heap,
            (cumulative_cost, priority_rank, zone_name, turn_index),
        )

    @staticmethod
    def find(
        game_world: GameWorld,
        movement: ZoneMovementModel,
        start_zone: str,
        end_zone: str,
        capacity_tracker: TurnCapacityTracker,
        *,
        max_time: int,
    ) -> tuple[list[str], list[tuple[str, int]]] | None:
        """Minimum-cost timed path, or None past *max_time*.

        The heap mostly sorts by “total turns spent so far” (cheapest first).

        """
        zones = game_world.zones
        connections = game_world.connections

        if start_zone not in zones or end_zone not in zones:
            raise PathfindingError("Start or end zone missing")
        try:
            if not movement.is_passable(
                start_zone
            ) or not movement.is_passable(end_zone):
                raise PathfindingError("Start or end blocked")
        except RoutingCostsError as e:
            raise PathfindingError(str(e))

        if start_zone == end_zone:
            return ([start_zone], [(start_zone, 0)])

        open_heap: list[tuple[int, int, str, int]] = []
        best_cost_by_state: dict[tuple[str, int], int] = {}
        came_from: dict[tuple[str, int], tuple[str, int]] = {}

        start_state = (start_zone, 0)
        best_cost_by_state[start_state] = 0
        TimedPathfinder._push(open_heap, movement, 0, start_zone, 0)
        goal_state: tuple[str, int] | None = None

        while open_heap:
            cumulative_cost, _priority_rank, zone_name, turn_index = (
                heapq.heappop(open_heap)
            )
            state = (zone_name, turn_index)
            if state not in best_cost_by_state:
                continue
            if cumulative_cost != best_cost_by_state[state]:
                continue
            if zone_name == end_zone:
                goal_state = state
                break

            if turn_index + 1 <= max_time:
                next_turn = turn_index + 1
                wait_state = (zone_name, next_turn)
                if capacity_tracker.can_occupy_zone_at(zone_name, turn_index):
                    wait_cost = cumulative_cost + 1
                    if wait_cost < best_cost_by_state.get(wait_state, inf):
                        best_cost_by_state[wait_state] = wait_cost
                        came_from[wait_state] = state
                        TimedPathfinder._push(
                            open_heap,
                            movement,
                            wait_cost,
                            zone_name,
                            next_turn,
                        )

            for neighbor_zone in TimedGraph.neighbors(connections, zone_name):
                try:
                    if not movement.is_passable(neighbor_zone):
                        continue
                except RoutingCostsError:
                    continue
                travel_turns = movement.simulation_turn_weight(neighbor_zone)
                if travel_turns <= 0:
                    continue
                turn_at_arrival = turn_index + travel_turns
                if turn_at_arrival > max_time:
                    continue
                if not capacity_tracker.can_move(
                    zone_name,
                    neighbor_zone,
                    turn_index,
                    turn_at_arrival,
                ):
                    continue
                move_state = (neighbor_zone, turn_at_arrival)
                move_cost = cumulative_cost + travel_turns
                if move_cost < best_cost_by_state.get(move_state, inf):
                    best_cost_by_state[move_state] = move_cost
                    came_from[move_state] = state
                    TimedPathfinder._push(
                        open_heap,
                        movement,
                        move_cost,
                        neighbor_zone,
                        turn_at_arrival,
                    )

        if goal_state is None:
            return None

        chain_reversed: list[tuple[str, int]] = []
        walk_state = goal_state
        while True:
            chain_reversed.append(walk_state)
            if walk_state == start_state:
                break
            walk_state = came_from[walk_state]
        timed_states = list(reversed(chain_reversed))
        zone_path = [zone_time[0] for zone_time in timed_states]
        return (zone_path, timed_states)
