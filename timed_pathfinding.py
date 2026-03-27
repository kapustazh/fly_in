"""Turn-based planning (VII.2): capacity is per turn, not per route name.

Static overlap counts treat every shared zone as conflict; here, limits apply
only when drones share a zone or link on the *same* turn.
"""

from __future__ import annotations

import heapq
from math import inf
from typing import Any, Dict

from collections.abc import Mapping

from game import GameWorld
from pathfinding import PathfindingError
from routing_costs import RoutingCostsError, ZoneMovementModel


class TimedGraph:
    """Static helpers to read zone graph metadata for timed routing."""

    @staticmethod
    def link_capacity(
        connections: Mapping[str, Dict[str, Any]], a: str, b: str
    ) -> int:
        """Maximum drones that may use the undirected edge *a*–*b* per turn."""
        block = connections.get(a)
        if block is None:
            return 0
        meta = block.get("metadata", {}).get(b)
        if meta is None:
            return 1
        return max(1, getattr(meta, "max_link_capacity", 1))

    @staticmethod
    def zone_max_drones(
        zones: Mapping[str, Dict[str, Any]], zone_name: str
    ) -> int:
        """Max drones that may share *zone_name* on one turn."""
        zone = zones.get(zone_name)
        if zone is None:
            return 1
        meta = zone.get("metadata")
        if meta is None:
            return 1
        return max(1, getattr(meta, "max_drones", 1))

    @staticmethod
    def neighbors(
        connections: Mapping[str, Dict[str, Any]], zone_name: str
    ) -> set[str]:
        """Adjacent zone names reachable from *zone_name* in one step."""
        block = connections.get(zone_name)
        if block is None:
            return set()
        return set(block.get("connections", set()))


class TurnOccupancyLedger:
    """Sparse per-turn usage for zones (capacity) and undirected links."""

    def __init__(
        self,
        zones: Mapping[str, Dict[str, Any]],
        connections: Mapping[str, Dict[str, Any]],
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
        cap = TimedGraph.link_capacity(
            self._connections, zone_from, zone_to
        )
        if cap <= 0:
            return False
        key_edge = frozenset({zone_from, zone_to})
        for tau in range(t_start, t_end):
            if self._link_use.get((key_edge, tau), 0) >= cap:
                return False
        return True

    def can_use_dest_zone_during(
        self, zone_to: str, t_start: int, t_end: int
    ) -> bool:
        """True if destination zone has spare capacity each turn."""
        if zone_to in self._exempt:
            return True
        cap = TimedGraph.zone_max_drones(self._zones, zone_to)
        for tau in range(t_start, t_end):
            if self._zone_use.get((zone_to, tau), 0) >= cap:
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
        key_edge = frozenset[str]({zone_from, zone_to})
        for tau in range(t_start, t_end):
            k = (key_edge, tau)
            self._link_use[k] = self._link_use.get(k, 0) + 1
            self.add_zone_turn(zone_to, tau)

    def reserve_wait_turn(self, zone_name: str, turn: int) -> None:
        """Record a one-turn wait (hover) in *zone_name* at *turn*."""
        self.add_zone_turn(zone_name, turn)

    def reserve_timed_state_chain(
        self, states: list[tuple[str, int]]
    ) -> None:
        """Apply reserve_wait_turn and reserve_move along a timed path."""
        for i in range(len(states) - 1):
            z0, t0 = states[i]
            z1, t1 = states[i + 1]
            if z0 == z1:
                if t1 != t0 + 1:
                    raise ValueError("Invalid wait step in timed chain")
                self.reserve_wait_turn(z0, t0)
            else:
                if t1 <= t0:
                    raise ValueError("Invalid move step in timed chain")
                self.reserve_move(z0, z1, t0, t1)


class TimedPathfinder:
    """Time-expanded search: zone path with waits + (zone, t) chain."""

    @staticmethod
    def _push(
        heap: list[tuple[int, int, str, int]],
        movement: ZoneMovementModel,
        g: int,
        z: str,
        t: int,
    ) -> None:
        """Enqueue a search state with priority zones explored first."""
        pri = 0 if movement.is_priority(z) else 1
        heapq.heappush(heap, (g, pri, z, t))

    @staticmethod
    def find(
        game_world: GameWorld,
        movement: ZoneMovementModel,
        start_zone: str,
        end_zone: str,
        ledger: TurnOccupancyLedger,
        *,
        max_time: int,
    ) -> tuple[list[str], list[tuple[str, int]]] | None:
        """Minimum-cost timed path, or None past *max_time*.

        Returns zone sequence and (zone, time) states for reservations.
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
            raise PathfindingError(str(e)) from e

        if start_zone == end_zone:
            return ([start_zone], [(start_zone, 0)])

        heap: list[tuple[int, int, str, int]] = []
        g_best: dict[tuple[str, int], int] = {}
        came_from: dict[tuple[str, int], tuple[str, int]] = {}

        start_state = (start_zone, 0)
        g_best[start_state] = 0
        TimedPathfinder._push(heap, movement, 0, start_zone, 0)
        goal_state: tuple[str, int] | None = None

        while heap:
            g, _pri, z, t = heapq.heappop(heap)
            state = (z, t)
            if state not in g_best or g != g_best[state]:
                continue
            if z == end_zone:
                goal_state = state
                break

            if t + 1 <= max_time:
                nt = t + 1
                nstate = (z, nt)
                if ledger.can_occupy_zone_at(z, t):
                    ng = g + 1
                    if ng < g_best.get(nstate, inf):
                        g_best[nstate] = ng
                        came_from[nstate] = state
                        TimedPathfinder._push(heap, movement, ng, z, nt)

            for nb in TimedGraph.neighbors(connections, z):
                try:
                    if not movement.is_passable(nb):
                        continue
                except RoutingCostsError:
                    continue
                dt = movement.simulation_turn_weight(nb)
                if dt <= 0:
                    continue
                t_end = t + dt
                if t_end > max_time:
                    continue
                if not ledger.can_move(z, nb, t, t_end):
                    continue
                nstate = (nb, t_end)
                ng = g + dt
                if ng < g_best.get(nstate, inf):
                    g_best[nstate] = ng
                    came_from[nstate] = state
                    TimedPathfinder._push(heap, movement, ng, nb, t_end)

        if goal_state is None:
            return None

        chain_rev: list[tuple[str, int]] = []
        cur = goal_state
        while True:
            chain_rev.append(cur)
            if cur == start_state:
                break
            cur = came_from[cur]
        timed_states = list(reversed(chain_rev))
        zone_path = [zt[0] for zt in timed_states]
        return (zone_path, timed_states)
