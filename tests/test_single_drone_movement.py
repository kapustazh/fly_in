from __future__ import annotations

import unittest
from math import inf
from typing import Any

from drone import Drone
from game import GameWorld
from parser import ConnectionMetadata, ZoneMetadata, ZoneTypes
from pathfinding import AStar


class TestSingleDroneMovement(unittest.TestCase):
    def test_one_drone_moves_hub_to_hub_and_reaches_end_zone(self) -> None:
        """Integration test from graph to hub-by-hub movement."""
        zones: dict[str, dict[str, Any]] = {
            "alpha": {
                "hub_type": "start_hub",
                "coordinates": (0, 0),
                "metadata": ZoneMetadata(zone=ZoneTypes.NORMAL),
            },
            "bravo": {
                "hub_type": "hub",
                "coordinates": (2, 0),
                "metadata": ZoneMetadata(zone=ZoneTypes.NORMAL),
            },
            "charlie": {
                "hub_type": "hub",
                "coordinates": (1, 1),
                "metadata": ZoneMetadata(zone=ZoneTypes.BLOCKED),
            },
            "delta": {
                "hub_type": "end_hub",
                "coordinates": (4, 0),
                "metadata": ZoneMetadata(zone=ZoneTypes.NORMAL),
            },
        }

        # alpha -> delta has two options:
        # - alpha -> charlie -> delta (blocked, must be rejected)
        # - alpha -> bravo -> delta (valid)
        connections: dict[str, dict[str, Any]] = {
            "alpha": {
                "connections": {"bravo", "charlie"},
                "metadata": {
                    "bravo": ConnectionMetadata(max_link_capacity=1),
                    "charlie": ConnectionMetadata(max_link_capacity=1),
                },
            },
            "bravo": {
                "connections": {"alpha", "delta"},
                "metadata": {
                    "alpha": ConnectionMetadata(max_link_capacity=1),
                    "delta": ConnectionMetadata(max_link_capacity=1),
                },
            },
            "charlie": {
                "connections": {"alpha", "delta"},
                "metadata": {
                    "alpha": ConnectionMetadata(max_link_capacity=1),
                    "delta": ConnectionMetadata(max_link_capacity=1),
                },
            },
            "delta": {
                "connections": {"bravo", "charlie"},
                "metadata": {
                    "bravo": ConnectionMetadata(max_link_capacity=1),
                    "charlie": ConnectionMetadata(max_link_capacity=1),
                },
            },
        }

        world = GameWorld(zones=zones, connections=connections, num_drones=1)
        pathfinder = AStar(world)
        path = pathfinder.find_path(start_zone="alpha", end_zone="delta")

        # Path quality checks
        self.assertEqual(path[0], "alpha")
        self.assertEqual(path[-1], "delta")
        self.assertNotIn("charlie", path)  # blocked zone must never be used

        # Build a one-drone movement simulation over waypoints.
        # We use graph coordinates as pixel targets for deterministic tests.
        def to_point(zone_name: str) -> tuple[float, float]:
            x, y = zones[zone_name]["coordinates"]
            return float(x), float(y)

        drone = Drone(current_zone=path[0], pixel_position=to_point(path[0]))
        speed = 1.0
        delta_seconds = 0.25

        visited_hubs = [drone.current_zone]

        for next_zone in path[1:]:
            # Ensure path transition follows declared edge.
            self.assertIn(
                next_zone,
                connections[drone.current_zone]["connections"],
            )

            target = to_point(next_zone)
            reached = False
            for _ in range(200):
                reached = drone.move_towards(
                    target_position=target,
                    speed_px_per_sec=speed,
                    delta_seconds=delta_seconds,
                )
                if reached:
                    drone.current_zone = next_zone
                    visited_hubs.append(next_zone)
                    break

            self.assertTrue(
                reached,
                f"Drone did not reach waypoint '{next_zone}'",
            )

        # Final acceptance criteria
        self.assertEqual(drone.current_zone, "delta")
        self.assertEqual(visited_hubs, path)

        # Optional extra safety: ensure no infinite costs on visited zones
        for zone_name in visited_hubs:
            metadata = zones[zone_name]["metadata"]
            zone_type = metadata.zone
            self.assertNotEqual(zone_type.cost, inf)


if __name__ == "__main__":
    unittest.main()
