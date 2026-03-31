"""Simulation line formatting (drone movement tokens per turn).

Extension: for per-turn capacity text, build a dict[int, str] keyed by
planner turn from GameWorld and planned_timed_states (same rules as
TurnCapacityTracker), then print after each movement line in
Renderer._print_turn_simulation_lines.
"""

from __future__ import annotations

from collections import defaultdict

from .drone import Drone
from .routing_costs import ZoneMovementModel


class SimulationOutput:
    """Step-by-step drone movement from start to end hub.

    Each non-empty simulation turn is one output line. On a line, list every
    drone that moves that turn, space-separated. Tokens:

      D<ID>-<zone>: drone enters or is reported at that destination zone.
      D<ID>-<from>-<to>: drone still crossing the bridge between two zones.

    Drones that do not move on a turn are omitted. After a drone reaches the
    end zone it is delivered and omitted from later lines. Output stops once
    every drone has reached the end zone. If a route has no timed chain, the
    formatter falls back to the zone path only.
    """

    def __init__(
        self,
        drones: list[Drone],
        end_zone: str,
        movement_model: ZoneMovementModel,
    ) -> None:
        self._end_zone = end_zone
        self._movement_model = movement_model
        self._by_turn: defaultdict[int, list[str]] = defaultdict(list)

        for i, drone in enumerate(drones):
            drone_name = f"D{i + 1}"
            if drone.planned_timed_states is not None:
                self._append_timed_chain(
                    drone.planned_timed_states, drone_name
                )
            else:
                self._append_zone_path(drone.zone_path, drone_name)

    def lines_by_turn(self) -> list[tuple[int, str]]:
        """Rows as (planner turn index, line text)."""
        if not self._by_turn:
            return []

        last_turn = max(self._by_turn)
        rows: list[tuple[int, str]] = []
        for t in range(1, last_turn + 1):
            actions = self._by_turn.get(t)
            if actions:
                rows.append((t, " ".join(actions)))
        return rows

    @classmethod
    def format_simulation_output_by_turn(
        cls,
        drones: list[Drone],
        end_zone: str,
        movement_model: ZoneMovementModel,
    ) -> list[tuple[int, str]]:
        """Planner turn index and one movement line per row."""
        return cls(drones, end_zone, movement_model).lines_by_turn()

    def _append_timed_chain(
        self,
        timed_states: list[tuple[str, int]],
        drone_name: str,
    ) -> None:
        """Append tokens from a (zone, planner turn) chain."""
        mm = self._movement_model
        end = self._end_zone
        by = self._by_turn

        for i in range(len(timed_states) - 1):
            z0, t0 = timed_states[i]
            z1, t1 = timed_states[i + 1]
            if z0 == z1:
                continue
            bridge = f"{z0}-{z1}"
            multi_turn = mm.simulation_turn_weight(z1) > 1
            mid_token = (
                f"{drone_name}-{bridge}"
                if multi_turn
                else f"{drone_name}-{z1}"
            )
            for t in range(t0 + 1, t1):
                by[t].append(mid_token)
            by[t1].append(f"{drone_name}-{z1}")
            if z1 == end:
                break

    def _append_zone_path(self, zone_path: list[str], drone_name: str) -> None:
        """Append tokens from zone_path when there is no timed chain."""
        mm = self._movement_model
        end = self._end_zone
        by = self._by_turn

        turn0 = 0
        for j in range(len(zone_path) - 1):
            z0, z1 = zone_path[j], zone_path[j + 1]
            if z0 == z1:
                turn0 += 1
                continue
            w = mm.simulation_turn_weight(z1)
            for k in range(1, w):
                by[turn0 + k].append(f"{drone_name}-{z0}-{z1}")
            by[turn0 + w].append(f"{drone_name}-{z1}")
            turn0 += w
            if z1 == end:
                break
