from __future__ import annotations

from dataclasses import dataclass
import math
from math import hypot

from game import GameWorld
from map_layout import ZoneLayout
from pathfinding import PlannedRoute, RoutePlanner
from routing_costs import ZoneMovementModel


@dataclass(frozen=True)
class DroneNavigationContext:
    """Pixel layout plus movement costs for simulation (no pathfinder)."""

    layout: ZoneLayout
    movement_model: ZoneMovementModel


class Drone:
    """Follows a planned zone path; moves in pixel space between zone
    centers."""

    def __init__(
        self,
        current_zone: str,
        pixel_position: tuple[float, float],
        end_zone: str,
        *,
        render_offset_x: float = 0.0,
        render_offset_y: float = 0.0,
    ) -> None:
        self.current_zone = current_zone
        self.end_zone = end_zone
        self.pixel_position = pixel_position
        self.render_offset_x = render_offset_x
        self.render_offset_y = render_offset_y
        self.zone_path: list[str] = []
        self.cumulative_simulation_turns = 0
        self._next_zone_index = 0
        self._wait_remaining = 0.0
        self._arrived = False

    def apply_planned_route(
        self,
        navigation_context: DroneNavigationContext,
        planned_route: PlannedRoute,
    ) -> None:
        """Start following a path from armada (capacity-aware planning)."""
        self.zone_path = planned_route.zone_names
        layout = navigation_context.layout
        self.pixel_position = layout.pixel_center_for_zone_name(
            self.zone_path[0]
        )
        self._wait_remaining = 0.0
        self.cumulative_simulation_turns = 0
        self._next_zone_index = 1
        self._arrived = self._next_zone_index >= len(self.zone_path)

    def sprite_render_movement_delta(
        self,
        navigation_context: DroneNavigationContext,
    ) -> tuple[float, float]:
        """Stable screen-space direction for sprite facing along path leg.

        Zone-center to zone-center, skipping repeated ``current_zone`` for
        1-turn waits, so heading does not drop to (0,0) while waiting.
        """
        return self._facing_leg_screen_delta(navigation_context)

    def _facing_leg_screen_delta(
        self,
        navigation_context: DroneNavigationContext,
    ) -> tuple[float, float]:
        if self._arrived or not self.zone_path:
            return (0.0, 0.0)
        i = self._next_zone_index
        while (
            i < len(self.zone_path) and self.zone_path[i] == self.current_zone
        ):
            i += 1
        if i >= len(self.zone_path):
            if len(self.zone_path) >= 2:
                a = navigation_context.layout.pixel_center_for_zone_name(
                    self.zone_path[-2]
                )
                b = navigation_context.layout.pixel_center_for_zone_name(
                    self.zone_path[-1]
                )
                return (b[0] - a[0], b[1] - a[1])
            return (1.0, 0.0)
        dest = navigation_context.layout.pixel_center_for_zone_name(
            self.zone_path[i]
        )
        origin = navigation_context.layout.pixel_center_for_zone_name(
            self.current_zone
        )
        return (dest[0] - origin[0], dest[1] - origin[1])

    def update(
        self,
        navigation_context: DroneNavigationContext,
        delta_seconds: float,
        speed_px_per_sec: float,
        wait_at_node_sec: float,
    ) -> None:
        if not self._has_unfinished_path():
            return
        if self._apply_node_delay(delta_seconds):
            return
        self._step_toward_next_path_zone(
            navigation_context,
            delta_seconds,
            speed_px_per_sec,
            wait_at_node_sec,
        )

    def _has_unfinished_path(self) -> bool:
        if not self.zone_path or self._arrived:
            return False
        if self._next_zone_index >= len(self.zone_path):
            self._arrived = True
            return False
        return True

    def _apply_node_delay(self, delta_seconds: float) -> bool:
        """Return True if this frame is spent waiting at a node."""
        if self._wait_remaining <= 0:
            return False
        self._wait_remaining = max(0.0, self._wait_remaining - delta_seconds)
        return True

    def _step_toward_next_path_zone(
        self,
        navigation_context: DroneNavigationContext,
        delta_seconds: float,
        speed_px_per_sec: float,
        wait_at_node_sec: float,
    ) -> None:
        next_zone_on_path = self.zone_path[self._next_zone_index]
        # Repeated zone name = one-turn "stay" (timed fleet planning).
        if next_zone_on_path == self.current_zone:
            self.cumulative_simulation_turns += 1
            self._next_zone_index += 1
            self._wait_remaining = wait_at_node_sec * 1.0
            if self._next_zone_index >= len(self.zone_path):
                self._arrived = True
            return

        goal_pixel = navigation_context.layout.pixel_center_for_zone_name(
            next_zone_on_path
        )
        reached = self.move_towards(
            goal_pixel, speed_px_per_sec, delta_seconds
        )
        if not reached:
            return
        self.current_zone = next_zone_on_path
        mm = navigation_context.movement_model
        enter_turn_weight = mm.simulation_turn_weight(next_zone_on_path)
        self.cumulative_simulation_turns += enter_turn_weight
        self._next_zone_index += 1
        if self._next_zone_index >= len(self.zone_path):
            self._arrived = True
        else:
            self._wait_remaining = wait_at_node_sec * float(enter_turn_weight)

    def move_towards(
        self,
        target_position: tuple[float, float],
        speed_px_per_sec: float,
        delta_seconds: float,
    ) -> bool:
        """Move toward the target position; True when the goal is reached."""
        current_x, current_y = self.pixel_position
        target_x, target_y = target_position

        dx = target_x - current_x
        dy = target_y - current_y
        distance = hypot(dx, dy)

        if distance == 0.0:
            return True

        step = speed_px_per_sec * delta_seconds
        if step >= distance:
            self.pixel_position = (target_x, target_y)
            return True

        ratio = step / distance
        self.pixel_position = (
            current_x + dx * ratio,
            current_y + dy * ratio,
        )
        return False

    @property
    def has_arrived(self) -> bool:
        return self._arrived


class DroneArmada:
    """Builds drones from GameWorld; launch_armada once, then update_all."""

    def __init__(self) -> None:
        self.drones: list[Drone] = []
        self._navigation_context: DroneNavigationContext | None = None
        self._launched = False

    def create_an_armada(
        self,
        drone_count: int,
        game_world: GameWorld,
        navigation_context: DroneNavigationContext,
    ) -> None:
        self._navigation_context = navigation_context
        self._launched = False
        start_hub_pixel = navigation_context.layout.pixel_center_for_zone_name(
            game_world.start_zone_name
        )
        self.drones = []
        for drone_index in range(drone_count):
            if drone_count <= 1:
                formation_offset_x = 0.0
                formation_offset_y = 0.0
            else:
                formation_angle = 2.0 * math.pi * drone_index / drone_count
                formation_offset_x = math.cos(formation_angle) * 12.0
                formation_offset_y = math.sin(formation_angle) * 12.0
            self.drones.append(
                Drone(
                    current_zone=game_world.start_zone_name,
                    pixel_position=start_hub_pixel,
                    end_zone=game_world.end_zone_name,
                    render_offset_x=formation_offset_x,
                    render_offset_y=formation_offset_y,
                )
            )

    def launch_armada(
        self, game_world: GameWorld, route_planner: RoutePlanner
    ) -> None:
        if self._navigation_context is None or self._launched:
            return
        from fleet_planner import FleetRoutePlanner

        capacity_exempt_hub_zone_names = frozenset(
            {
                game_world.start_zone_name,
                game_world.end_zone_name,
            }
        )
        result = FleetRoutePlanner.plan_all_drones(
            route_planner,
            game_world,
            self.drones,
            capacity_exempt_hub_zone_names=capacity_exempt_hub_zone_names,
        )
        if result.used_capacity_fallback:
            print(
                "[DroneArmada] The fleet cannot all be routed under "
                "link and zone limits (often a single narrow exit). "
                "Replanning every drone without those limits; "
                "paths may overlap."
            )

        for drone, planned_route in zip(self.drones, result.routes):
            drone.apply_planned_route(
                self._navigation_context,
                planned_route,
            )
        self._launched = True

    def update_all(
        self,
        delta_seconds: float,
        speed_px_per_sec: float,
        wait_at_node_sec: float,
    ) -> None:
        if self._navigation_context is None:
            return
        for drone in self.drones:
            drone.update(
                self._navigation_context,
                delta_seconds,
                speed_px_per_sec,
                wait_at_node_sec,
            )

    def synchronized_turn_count(self) -> int:
        """Min cumulative turns among active drones (weighted zone costs)."""
        if not self.drones:
            return 0
        active = [d for d in self.drones if not d.has_arrived]
        if active:
            return min(d.cumulative_simulation_turns for d in active)
        return max(d.cumulative_simulation_turns for d in self.drones)
