"""Fleet routing: timed capacity-aware paths."""

from __future__ import annotations

from fly_in.drone import Drone
from fly_in.game import GameWorld
from fly_in.routing_costs import ZoneMovementModel
from fly_in.timed_pathfinding import (
    PlannedRoute,
    TimedPathfinder,
    TurnCapacityTracker,
)


class FleetPlanningError(Exception):
    """No feasible timed route for a drone within the search horizon."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Fleet planning error: {detail}")


class FleetRoutePlanner:
    """Fleet routing with per-turn capacity, not static overlap."""

    @staticmethod
    def _max_time_budget(game_world: GameWorld, num_drones: int) -> int:
        """Upper bound on simulated turns for timed search (map + fleet)."""
        zone_count = max(1, len(game_world.zones))
        return min(15_000, 300 + num_drones * 250 + zone_count * 80)

    @staticmethod
    def plan_all_drones(
        movement_model: ZoneMovementModel,
        game_world: GameWorld,
        drones: list[Drone],
        *,
        capacity_exempt_hub_zone_names: frozenset[str],
    ) -> list[PlannedRoute]:
        """Plan drones in order; reserve capacity on the shared tracker."""
        capacity_tracker = TurnCapacityTracker(
            game_world.zones,
            game_world.connections,
            exempt_zone_capacity=capacity_exempt_hub_zone_names,
        )
        max_time = FleetRoutePlanner._max_time_budget(game_world, len(drones))
        planned_routes: list[PlannedRoute] = []

        for drone in drones:
            timed = TimedPathfinder.find(
                game_world,
                movement_model,
                drone.current_zone,
                drone.end_zone,
                capacity_tracker,
                max_time=max_time,
            )
            if timed is None:
                raise FleetPlanningError(
                    "TimedFleet planning failed: increase max_time budget, "
                    "relax capacities, or change the map."
                )
            zone_path, timed_states = timed
            capacity_tracker.reserve_timed_state_chain(timed_states)
            planned_routes.append(
                PlannedRoute(
                    zone_names=list(zone_path),
                    timed_states=tuple(timed_states),
                )
            )

        return planned_routes
