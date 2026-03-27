"""Fleet routing: timed capacity-aware paths; optional A* fallback."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from game import GameWorld
from pathfinding import PlannedRoute, RoutePlanner
from timed_pathfinding import TimedPathfinder, TurnOccupancyLedger


class DroneRouteEndpoints(Protocol):
    """Anything with *current_zone* and *end_zone* (used by fleet routing)."""

    current_zone: str
    end_zone: str


@dataclass(frozen=True)
class FleetPlanResult:
    """Outcome of fleet-level routing (constrained or fallback)."""

    routes: list[PlannedRoute]
    used_capacity_fallback: bool


class FleetRoutePlanner:
    """Fleet routing with per-turn capacity (VII.2), not static overlap."""

    @staticmethod
    def _max_time_budget(game_world: GameWorld, num_drones: int) -> int:
        """Upper bound on simulated turns for timed search (map + fleet)."""
        nz = max(1, len(game_world.zones))
        return min(15_000, 300 + num_drones * 250 + nz * 80)

    @staticmethod
    def plan_all_drones(
        route_planner: RoutePlanner,
        game_world: GameWorld,
        drones: Sequence[DroneRouteEndpoints],
        *,
        capacity_exempt_hub_zone_names: frozenset[str],
    ) -> FleetPlanResult:
        """Plan drones in order; reserve capacity or use per-drone A*."""
        movement = route_planner.movement_model
        ledger = TurnOccupancyLedger(
            game_world.zones,
            game_world.connections,
            exempt_zone_capacity=capacity_exempt_hub_zone_names,
        )
        max_time = FleetRoutePlanner._max_time_budget(game_world, len(drones))
        planned_routes: list[PlannedRoute] = []

        for drone in drones:
            timed = TimedPathfinder.find(
                game_world,
                movement,
                drone.current_zone,
                drone.end_zone,
                ledger,
                max_time=max_time,
            )
            if timed is None:
                return FleetRoutePlanner._fallback(route_planner, drones)
            zone_path, timed_states = timed
            ledger.reserve_timed_state_chain(timed_states)
            planned_routes.append(
                PlannedRoute(
                    zone_names=list(zone_path),
                    timed_states=tuple(timed_states),
                )
            )

        return FleetPlanResult(
            routes=planned_routes, used_capacity_fallback=False
        )

    @staticmethod
    def _fallback(
        route_planner: RoutePlanner, drones: Sequence[DroneRouteEndpoints]
    ) -> FleetPlanResult:
        """Plan each drone alone; ignore shared capacity (overlap ok)."""
        routes = [
            route_planner.plan(d.current_zone, d.end_zone) for d in drones
        ]
        return FleetPlanResult(routes=routes, used_capacity_fallback=True)
