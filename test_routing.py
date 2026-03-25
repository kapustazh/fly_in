"""Phase 6 smoke tests: routing costs and PlannedRoute totals (no pygame)."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from fleet_planner import FleetRoutePlanner
from game import GameWorld
from parser import InputParser
from pathfinding import RoutePlanner
from routing_costs import ZoneMovementModel


class TestPlannedRouteCost(unittest.TestCase):
    def test_total_enter_cost_matches_zone_sum(self) -> None:
        root = Path(__file__).resolve().parent
        parser = InputParser()
        parser.parse_lines(str(root / "test_map.txt"))
        parser.parse_input()
        world = GameWorld.from_parsed_map(
            zones=parser.get_zones,
            connections=parser.connections,
            num_drones=parser.number_of_drones,
        )
        planner = RoutePlanner(world)
        route = planner.plan(world.start_zone_name, world.end_zone_name)
        model = ZoneMovementModel(world.zones)
        expected = sum(model.enter_cost(z) for z in route.zone_names[1:])
        self.assertAlmostEqual(route.total_enter_cost, expected)

    def test_timed_fleet_planning_no_false_fallback(self) -> None:
        root = Path(__file__).resolve().parent
        parser = InputParser()
        parser.parse_lines(str(root / "test_map.txt"))
        parser.parse_input()
        world = GameWorld.from_parsed_map(
            zones=parser.get_zones,
            connections=parser.connections,
            num_drones=parser.number_of_drones,
        )
        planner = RoutePlanner(world)
        fleet = FleetRoutePlanner(planner, world)
        drone = SimpleNamespace(
            current_zone=world.start_zone_name,
            end_zone=world.end_zone_name,
        )
        hubs = frozenset({world.start_zone_name, world.end_zone_name})
        result = fleet.plan_all_drones(
            [drone],
            capacity_exempt_hub_zone_names=hubs,
        )
        self.assertFalse(result.used_capacity_fallback)
        self.assertEqual(len(result.routes), 1)


if __name__ == "__main__":
    unittest.main()
