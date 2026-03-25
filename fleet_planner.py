from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from game import GameWorld
from pathfinding import PathfindingError, PlannedRoute, RoutePlanner
from timed_pathfinding import (
    TurnOccupancyLedger,
    find_timed_path,
    planned_total_enter_cost,
)


class DroneRouteEndpoints(Protocol):
    """Minimal drone surface needed for fleet planning (avoids importing pygame)."""

    current_zone: str
    end_zone: str


@dataclass(frozen=True)
class FleetPlanResult:
    """Outcome of fleet-level routing (constrained or fallback)."""

    routes: list[PlannedRoute]
    used_capacity_fallback: bool


class FleetRoutePlanner:
    """Fleet routing with per-turn capacity (subject VII.2), not static route overlap."""

    def __init__(self, route_planner: RoutePlanner, game_world: GameWorld) -> None:
        self._route_planner = route_planner
        self._world = game_world

    def _max_time_budget(self, num_drones: int) -> int:
        nz = max(1, len(self._world.zones))
        return min(15_000, 300 + num_drones * 250 + nz * 80)

    def plan_all_drones(
        self,
        drones: list[DroneRouteEndpoints],
        *,
        capacity_exempt_hub_zone_names: frozenset[str],
    ) -> FleetPlanResult:
        movement = self._route_planner.movement_model
        ledger = TurnOccupancyLedger(
            self._world.zones,
            self._world.connections,
            exempt_zone_capacity=capacity_exempt_hub_zone_names,
        )
        max_time = self._max_time_budget(len(drones))
        planned_routes: list[PlannedRoute] = []

        for drone in drones:
            timed = find_timed_path(
                self._world,
                movement,
                drone.current_zone,
                drone.end_zone,
                ledger,
                max_time=max_time,
            )
            if timed is None:
                return self._plan_all_without_capacity_limits(drones)
            zone_path, timed_states = timed
            ledger.reserve_timed_state_chain(timed_states)
            planned_routes.append(
                PlannedRoute(
                    zone_names=list(zone_path),
                    total_enter_cost=planned_total_enter_cost(
                        movement, zone_path
                    ),
                )
            )

        return FleetPlanResult(routes=planned_routes, used_capacity_fallback=False)

    def _plan_all_without_capacity_limits(
        self,
        drones: list[DroneRouteEndpoints],
    ) -> FleetPlanResult:
        planned_routes = [
            self._route_planner.plan(drone.current_zone, drone.end_zone)
            for drone in drones
        ]
        return FleetPlanResult(routes=planned_routes, used_capacity_fallback=True)
