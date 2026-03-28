"""Phase 6 smoke tests: route planning and fleet timing (no pygame)."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from fleet_planner import FleetRoutePlanner
from game import GameWorld
from parser import InputParser
from pathfinding import RoutePlanner


class TestRoutePlanning(unittest.TestCase):
    def test_planned_route_connects_start_to_end_hub(self) -> None:
        root = Path(__file__).resolve().parent
        parser = InputParser()
        parser.parse_lines(str(root / "unit_tests" / "test_map.txt"))
        parser.parse_input()
        world = GameWorld.from_parsed_map(
            zones=parser.get_zones,
            connections=parser.connections,
            num_drones=parser.number_of_drones,
        )
        planner = RoutePlanner(world)
        route = planner.plan(world.start_zone_name, world.end_zone_name)
        self.assertGreaterEqual(len(route.zone_names), 1)
        self.assertEqual(route.zone_names[0], world.start_zone_name)
        self.assertEqual(route.zone_names[-1], world.end_zone_name)

    def test_fleet_planner_one_route_per_drone(self) -> None:
        root = Path(__file__).resolve().parent
        parser = InputParser()
        parser.parse_lines(str(root / "unit_tests" / "test_map.txt"))
        parser.parse_input()
        world = GameWorld.from_parsed_map(
            zones=parser.get_zones,
            connections=parser.connections,
            num_drones=parser.number_of_drones,
        )
        planner = RoutePlanner(world)
        drone = SimpleNamespace(
            current_zone=world.start_zone_name,
            end_zone=world.end_zone_name,
        )
        result = FleetRoutePlanner.plan_all_drones(
            planner,
            world,
            [drone],
            capacity_exempt_hub_zone_names=frozenset(
                {world.start_zone_name, world.end_zone_name},
            ),
        )
        self.assertEqual(len(result.routes), 1)
        r0 = result.routes[0]
        self.assertEqual(r0.zone_names[0], world.start_zone_name)
        self.assertEqual(r0.zone_names[-1], world.end_zone_name)


if __name__ == "__main__":
    unittest.main()
