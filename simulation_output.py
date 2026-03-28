"""VII.5 simulation text: step-by-step drone movement from start to end hub.

Each non-empty simulation turn is one output line. On a line, list every
drone that moves that turn, space-separated. Tokens:

  * D<ID>-<zone>: drone enters or is reported at that destination zone.
  * D<ID>-<from>-<to>: drone still crossing the edge between two zones
    (multi-turn legs, e.g. restricted zones in this project).

Drones that do not move on a turn are omitted. After a drone reaches the end
zone it is delivered and omitted from later lines. Output stops once every
drone has reached the end zone.
"""

from __future__ import annotations

from drone import Drone
from routing_costs import ZoneMovementModel


def format_simulation_output(
    drones: list[Drone],
    end_zone: str,
    movement_model: ZoneMovementModel,
) -> list[str]:
    """Build VII.5 lines (timed plan if present, else zone-path expansion)."""
    rows = format_simulation_output_by_turn(
        drones,
        end_zone,
        movement_model,
    )
    return [line_text for planner_turn, line_text in rows]


def format_simulation_output_by_turn(
    drones: list[Drone],
    end_zone: str,
    movement_model: ZoneMovementModel,
) -> list[tuple[int, str]]:
    """Like format_simulation_output but keep planner turn index per line."""
    turn_actions: dict[int, list[str]] = {}

    for drone_index, drone in enumerate(drones):
        label = f"D{drone_index + 1}"
        timed_chain = drone.planned_timed_states
        if timed_chain is not None:
            _collect_timed_chain(
                turn_actions,
                label,
                timed_chain,
                end_zone,
                movement_model,
            )
        else:
            _collect_from_zone_path(
                turn_actions,
                label,
                drone.zone_path,
                end_zone,
                movement_model,
            )

    if not turn_actions:
        return []

    max_turn = max(turn_actions)
    entries: list[tuple[int, str]] = []
    for turn_index in range(1, max_turn + 1):
        actions = turn_actions.get(turn_index)
        if actions:
            entries.append((turn_index, " ".join(actions)))
    return entries


def _collect_timed_chain(
    turn_actions: dict[int, list[str]],
    label: str,
    timed_states: list[tuple[str, int]],
    end_zone: str,
    movement_model: ZoneMovementModel,
) -> None:
    """Populate *turn_actions* from (zone_name, turn_index) pairs."""
    for step_index in range(len(timed_states) - 1):
        from_zone, turn_start = timed_states[step_index]
        to_zone, turn_end = timed_states[step_index + 1]
        if from_zone == to_zone:
            continue
        connection = f"{from_zone}-{to_zone}"
        in_flight_toward_slow = (
            movement_model.simulation_turn_weight(
                to_zone,
            )
            > 1
        )
        for mid_turn in range(turn_start + 1, turn_end):
            token = (
                f"{label}-{connection}"
                if in_flight_toward_slow
                else f"{label}-{to_zone}"
            )
            turn_actions.setdefault(mid_turn, []).append(token)
        turn_actions.setdefault(turn_end, []).append(f"{label}-{to_zone}")
        if to_zone == end_zone:
            break


def _collect_from_zone_path(
    turn_actions: dict[int, list[str]],
    label: str,
    zone_path: list[str],
    end_zone: str,
    movement_model: ZoneMovementModel,
) -> None:
    """Expand *zone_path* using per-zone enter weights.

    Used for A* fallback when the drone has no timed state chain.
    """
    turn_cursor = 0
    path_index = 0
    path_len = len(zone_path)
    while path_index < path_len - 1:
        from_zone = zone_path[path_index]
        to_zone = zone_path[path_index + 1]
        if from_zone == to_zone:
            turn_cursor += 1
            path_index += 1
            continue
        travel_turns = movement_model.simulation_turn_weight(to_zone)
        for mid_turn in range(1, travel_turns):
            turn_actions.setdefault(turn_cursor + mid_turn, []).append(
                f"{label}-{from_zone}-{to_zone}",
            )
        turn_actions.setdefault(turn_cursor + travel_turns, []).append(
            f"{label}-{to_zone}",
        )
        turn_cursor += travel_turns
        path_index += 1
        if to_zone == end_zone:
            break
