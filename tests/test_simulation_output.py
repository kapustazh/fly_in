"""Tests for VII.5 simulation output format."""

from __future__ import annotations

import unittest
from typing import Any

from drone import Drone
from game import GameWorld
from parser import (
    ConnectionMetadata,
    ZoneMetadata,
    ZoneTypes,
)
from pathfinding import RoutePlanner
from routing_costs import ZoneMovementModel
from simulation_output import format_simulation_output


def _movement_model(zone_types: dict[str, ZoneTypes]) -> ZoneMovementModel:
    """Minimal zone table: same coords, metadata carries ZoneTypes."""
    zones: dict[str, dict[str, Any]] = {}
    for name, zt in zone_types.items():
        zones[name] = {
            "hub_type": "hub",
            "coordinates": (0, 0),
            "metadata": ZoneMetadata(zone=zt),
        }
    return ZoneMovementModel(zones)


def _make_drone(
    zone_path: list[str],
    end_zone: str,
    *,
    timed_states: list[tuple[str, int]] | None = None,
) -> Drone:
    drone = Drone(
        current_zone=zone_path[0],
        pixel_position=(0.0, 0.0),
        end_zone=end_zone,
    )
    drone.zone_path = list(zone_path)
    drone.planned_timed_states = timed_states
    return drone


class TestSimulationOutput(unittest.TestCase):

    def test_timed_chain_used_when_present(self) -> None:
        """Fleet timed plan drives VII.5 lines (ignores movement_model)."""
        mm = _movement_model(
            {
                "hub": ZoneTypes.NORMAL,
                "roof1": ZoneTypes.NORMAL,
                "goal": ZoneTypes.NORMAL,
            }
        )
        drone = _make_drone(
            ["hub", "roof1", "goal"],
            "goal",
            timed_states=[("hub", 0), ("roof1", 1), ("goal", 2)],
        )
        lines = format_simulation_output([drone], "goal", mm)
        self.assertEqual(lines, ["D1-roof1", "D1-goal"])

    def test_single_drone_simple_path(self) -> None:
        mm = _movement_model(
            {
                "alpha": ZoneTypes.NORMAL,
                "bravo": ZoneTypes.NORMAL,
                "charlie": ZoneTypes.NORMAL,
            }
        )
        d = _make_drone(["alpha", "bravo", "charlie"], "charlie")
        lines = format_simulation_output([d], "charlie", mm)
        self.assertEqual(lines, ["D1-bravo", "D1-charlie"])

    def test_two_drones_parallel(self) -> None:
        mm = _movement_model(
            {
                "hub": ZoneTypes.NORMAL,
                "roof1": ZoneTypes.NORMAL,
                "corridorA": ZoneTypes.NORMAL,
                "goal": ZoneTypes.NORMAL,
            }
        )
        d1 = _make_drone(["hub", "roof1", "goal"], "goal")
        d2 = _make_drone(["hub", "corridorA", "goal"], "goal")
        lines = format_simulation_output([d1, d2], "goal", mm)
        self.assertEqual(
            lines,
            ["D1-roof1 D2-corridorA", "D1-goal D2-goal"],
        )

    def test_wait_steps_in_path_emit_no_tokens(self) -> None:
        """Repeated zone in path advances time with no movement line."""
        mm = _movement_model(
            {
                "a": ZoneTypes.NORMAL,
                "b": ZoneTypes.NORMAL,
                "c": ZoneTypes.NORMAL,
            }
        )
        d = _make_drone(["a", "a", "b", "c"], "c")
        lines = format_simulation_output([d], "c", mm)
        self.assertEqual(lines, ["D1-b", "D1-c"])

    def test_multi_turn_restricted_connection(self) -> None:
        mm = _movement_model(
            {
                "hub": ZoneTypes.NORMAL,
                "restricted": ZoneTypes.RESTRICTED,
                "goal": ZoneTypes.NORMAL,
            }
        )
        d = _make_drone(["hub", "restricted", "goal"], "goal")
        lines = format_simulation_output([d], "goal", mm)
        self.assertEqual(
            lines,
            [
                "D1-hub-restricted",
                "D1-restricted",
                "D1-goal",
            ],
        )

    def test_timed_chain_restricted_connection_tokens(self) -> None:
        """Use connection-style tokens in transit toward a restricted zone."""
        mm = _movement_model(
            {
                "hub": ZoneTypes.NORMAL,
                "restricted": ZoneTypes.RESTRICTED,
                "goal": ZoneTypes.NORMAL,
            }
        )
        d = _make_drone(
            ["hub", "restricted", "goal"],
            "goal",
            timed_states=[("hub", 0), ("restricted", 2), ("goal", 3)],
        )
        lines = format_simulation_output([d], "goal", mm)
        self.assertEqual(
            lines,
            [
                "D1-hub-restricted",
                "D1-restricted",
                "D1-goal",
            ],
        )

    def test_drone_stops_after_end_zone(self) -> None:
        mm = _movement_model(
            {
                "a": ZoneTypes.NORMAL,
                "b": ZoneTypes.NORMAL,
                "goal": ZoneTypes.NORMAL,
                "extra": ZoneTypes.NORMAL,
            }
        )
        d = _make_drone(["a", "b", "goal", "extra"], "goal")
        lines = format_simulation_output([d], "goal", mm)
        self.assertEqual(lines, ["D1-b", "D1-goal"])

    def test_empty_drone_list(self) -> None:
        mm = _movement_model({"goal": ZoneTypes.NORMAL})
        self.assertEqual(format_simulation_output([], "goal", mm), [])

    def test_single_zone_path(self) -> None:
        mm = _movement_model({"goal": ZoneTypes.NORMAL})
        d = _make_drone(["goal"], "goal")
        self.assertEqual(format_simulation_output([d], "goal", mm), [])

    def test_integration_with_planner(self) -> None:
        zones: dict[str, dict[str, Any]] = {
            "hub": {
                "hub_type": "start_hub",
                "coordinates": (0, 0),
                "metadata": ZoneMetadata(zone=ZoneTypes.NORMAL),
            },
            "mid": {
                "hub_type": "hub",
                "coordinates": (2, 0),
                "metadata": ZoneMetadata(zone=ZoneTypes.NORMAL),
            },
            "goal": {
                "hub_type": "end_hub",
                "coordinates": (4, 0),
                "metadata": ZoneMetadata(zone=ZoneTypes.NORMAL),
            },
        }
        connections: dict[str, dict[str, Any]] = {
            "hub": {
                "connections": {"mid"},
                "metadata": {"mid": ConnectionMetadata()},
            },
            "mid": {
                "connections": {"hub", "goal"},
                "metadata": {
                    "hub": ConnectionMetadata(),
                    "goal": ConnectionMetadata(),
                },
            },
            "goal": {
                "connections": {"mid"},
                "metadata": {"mid": ConnectionMetadata()},
            },
        }
        world = GameWorld.from_parsed_map(
            zones=zones,
            connections=connections,
            num_drones=1,
        )
        planner = RoutePlanner(world)
        route = planner.plan("hub", "goal")
        drone = Drone(
            current_zone="hub",
            pixel_position=(0.0, 0.0),
            end_zone="goal",
        )
        drone.zone_path = route.zone_names
        lines = format_simulation_output(
            [drone],
            "goal",
            planner.movement_model,
        )
        self.assertTrue(len(lines) >= 1)
        self.assertTrue(lines[-1].endswith("-goal"))
        for line in lines:
            self.assertRegex(line, r"^D1-\w+")

    def test_staggered_arrivals(self) -> None:
        mm = _movement_model(
            {
                "a": ZoneTypes.NORMAL,
                "b": ZoneTypes.NORMAL,
                "goal": ZoneTypes.NORMAL,
            }
        )
        d1 = _make_drone(["a", "goal"], "goal")
        d2 = _make_drone(["a", "b", "goal"], "goal")
        lines = format_simulation_output([d1, d2], "goal", mm)
        self.assertEqual(lines, ["D1-goal D2-b", "D2-goal"])


if __name__ == "__main__":
    unittest.main()
