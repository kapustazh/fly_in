"""Drones and fleet: pixel motion along routes and armada setup."""

from __future__ import annotations

from dataclasses import dataclass
import math
from math import hypot

from game import GameWorld
from map_layout import ZoneLayout
from pathfinding import PlannedRoute, RoutePlanner
from routing_costs import ZoneMovementModel

# Real seconds for one discrete simulation turn. Used for planner_turn_time,
# node waits, and timed-route speed budgets. Raise for slower pacing; keep
# DronesLayer.WAIT_AT_NODE_SEC equal to this value.
SECONDS_PER_DISCRETE_TURN: float = 0.75


@dataclass(frozen=True)
class DroneNavigationContext:
    """Read-only world helpers passed into Drone update and render logic.

    layout maps zone names to pixel centers, and movement_model provides
    per-zone movement weights used when updating cumulative simulation turns.
    """

    layout: ZoneLayout
    movement_model: ZoneMovementModel


class Drone:
    """Follows a planned zone path; moves in pixel space between zone
    centers.
    """

    def __init__(
        self,
        current_zone: str,
        pixel_position: tuple[float, float],
        end_zone: str,
        *,
        render_offset_x: float = 0.0,
        render_offset_y: float = 0.0,
    ) -> None:
        """Start at pixel_position in current_zone, aiming for end_zone."""
        self.current_zone = current_zone
        self.end_zone = end_zone
        self.pixel_position = pixel_position
        self.render_offset_x = render_offset_x
        self.render_offset_y = render_offset_y
        self.zone_path: list[str] = []
        self.planned_timed_states: list[tuple[str, int]] | None = None
        self.cumulative_simulation_turns = 0
        self._next_zone_index = 0
        self._wait_remaining = 0.0
        self._arrived = False

    def apply_planned_route(
        self,
        navigation_context: DroneNavigationContext,
        planned_route: PlannedRoute,
    ) -> None:
        """Start following a path from the armada."""
        self.zone_path = planned_route.zone_names
        timed_states_tuple = planned_route.timed_states
        if timed_states_tuple is not None:
            if len(timed_states_tuple) != len(self.zone_path):
                raise ValueError("timed_states and zone_path length mismatch")
            self.planned_timed_states = list(timed_states_tuple)
        else:
            self.planned_timed_states = None
        self.pixel_position = (
            navigation_context.layout.pixel_center_for_zone_name(
                self.zone_path[0]
            )
        )
        self._wait_remaining = 0.0
        self.cumulative_simulation_turns = 0
        self._next_zone_index = 1
        self._arrived = self._next_zone_index >= len(self.zone_path)

    def sprite_render_movement_delta(
        self,
        navigation_context: DroneNavigationContext,
    ) -> tuple[float, float]:
        """Stable screen-space direction for the sprite

        From zone center toward the next zone on the path; skips repeated
        current_zone entries used for 1-turn waits so heading stays non-zero.
        """
        return self._facing_screen_delta(navigation_context)

    def _facing_screen_delta(
        self,
        navigation_context: DroneNavigationContext,
    ) -> tuple[float, float]:
        """Vector used only for sprite facing (not movement state).

        From current zone center toward the next distinct zone on the path.
        Skips repeated current_zone entries (wait steps) using a local index so
        we do not mutate _next_zone_index. If arrived or no path, (0, 0).
        """
        path = self.zone_path
        if self._arrived or not path:
            return (0.0, 0.0)
        path_index = self._next_zone_index
        while path_index < len(path) and path[path_index] == self.current_zone:
            path_index += 1

        layout = navigation_context.layout
        pixel_center = layout.pixel_center_for_zone_name

        if path_index >= len(path):
            if len(path) >= 2:
                previous_center = pixel_center(path[-2])
                last_center = pixel_center(path[-1])
                return (
                    last_center[0] - previous_center[0],
                    last_center[1] - previous_center[1],
                )
            return (1.0, 0.0)

        destination_center = pixel_center(path[path_index])
        origin_center = pixel_center(self.current_zone)
        return (
            destination_center[0] - origin_center[0],
            destination_center[1] - origin_center[1],
        )

    def update(
        self,
        navigation_context: DroneNavigationContext,
        delta_seconds: float,
        speed_px_per_sec: float,
        wait_at_node_sec: float,
        planner_turn_time: float,
    ) -> None:
        """Advance position along the path
        (waits, same-zone turns, then motion)"""
        if not self._has_unfinished_path():
            return
        if self._apply_node_delay(delta_seconds):
            return
        self._step_toward_next_path_zone(
            navigation_context,
            delta_seconds,
            speed_px_per_sec,
            wait_at_node_sec,
            planner_turn_time,
        )

    def _has_unfinished_path(self) -> bool:
        """True while the drone still has path segments to execute."""
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
        self._wait_remaining -= delta_seconds
        if self._wait_remaining < 0.0:
            self._wait_remaining = 0.0
        return True

    def _step_toward_next_path_zone(
        self,
        navigation_context: DroneNavigationContext,
        delta_seconds: float,
        speed_px_per_sec: float,
        wait_at_node_sec: float,
        planner_turn_time: float,
    ) -> None:
        """Handle wait-in-place, or move toward the next zone on the path."""
        if not self._can_start_timed_step(planner_turn_time):
            return
        next_zone_on_path = self.zone_path[self._next_zone_index]
        if next_zone_on_path == self.current_zone:
            self.cumulative_simulation_turns += 1
            self._next_zone_index += 1
            self._wait_remaining = wait_at_node_sec
            if self._next_zone_index >= len(self.zone_path):
                self._arrived = True
            return

        goal_pixel = navigation_context.layout.pixel_center_for_zone_name(
            next_zone_on_path
        )
        effective_speed_px_per_sec = self._effective_move_speed(
            goal_pixel,
            speed_px_per_sec,
            wait_at_node_sec,
        )
        reached = self.move_towards(
            goal_pixel, effective_speed_px_per_sec, delta_seconds
        )
        if not reached:
            return
        self._finish_zone_entry(
            navigation_context,
            next_zone_on_path,
            wait_at_node_sec,
        )

    def _can_start_timed_step(self, planner_turn_time: float) -> bool:
        """Gate simulation by planner turn when timed states are present."""
        timed_states = self.planned_timed_states
        if timed_states is None:
            return True
        step_index = self._next_zone_index
        reserved_start_turn = timed_states[step_index - 1][1]
        return planner_turn_time >= reserved_start_turn

    def _effective_move_speed(
        self,
        goal_pixel: tuple[float, float],
        speed_px_per_sec: float,
        wait_at_node_sec: float,
    ) -> float:
        """Minimum speed needed to finish inside the reserved timed window."""
        timed_states = self.planned_timed_states
        if timed_states is None:
            return speed_px_per_sec
        step_index = self._next_zone_index
        turn_at_arrival = timed_states[step_index][1]
        turn_at_step_start = timed_states[step_index - 1][1]
        turn_span = turn_at_arrival - turn_at_step_start
        if turn_span < 1:
            turn_span = 1
        sec_budget = turn_span * wait_at_node_sec
        if sec_budget <= 0.0:
            return speed_px_per_sec
        cur_x, cur_y = self.pixel_position
        gx, gy = goal_pixel
        distance = hypot(gx - cur_x, gy - cur_y)
        min_required_speed = distance / sec_budget
        return max(speed_px_per_sec, min_required_speed)

    def _finish_zone_entry(
        self,
        navigation_context: DroneNavigationContext,
        next_zone_on_path: str,
        wait_at_node_sec: float,
    ) -> None:
        """Apply simulation bookkeeping after reaching the next zone."""
        self.current_zone = next_zone_on_path
        movement_model = navigation_context.movement_model
        enter_turn_weight = movement_model.simulation_turn_weight(
            next_zone_on_path
        )
        self.cumulative_simulation_turns += enter_turn_weight
        self._next_zone_index += 1
        if self._next_zone_index >= len(self.zone_path):
            self._arrived = True
            return
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

        delta_x = target_x - current_x
        delta_y = target_y - current_y
        distance = hypot(delta_x, delta_y)

        if distance == 0.0:
            return True

        travel_this_frame = speed_px_per_sec * delta_seconds
        if travel_this_frame >= distance:
            self.pixel_position = (target_x, target_y)
            return True

        fraction = travel_this_frame / distance
        self.pixel_position = (
            current_x + delta_x * fraction,
            current_y + delta_y * fraction,
        )
        return False

    @property
    def has_arrived(self) -> bool:
        """True when the drone finished the last segment of its route."""
        return self._arrived


class DroneArmada:
    """Builds drones from GameWorld; launch_armada once, then update_all."""

    def __init__(self) -> None:
        """Create an empty fleet; call create_an_armada then launch_armada."""
        self.drones: list[Drone] = []
        self._navigation_context: DroneNavigationContext | None = None
        self._launched = False
        self.planner_turn_time: float = 0.0

    def create_an_armada(
        self,
        drone_count: int,
        game_world: GameWorld,
        navigation_context: DroneNavigationContext,
    ) -> None:
        """Spawn *drone_count* drones at the start hub with a small formation
        offset."""
        self._navigation_context = navigation_context
        self._launched = False
        self.planner_turn_time = 0.0
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
        """Assign timed fleet routes (or fallback A*) and mark the
        armada launched."""
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
        """Step each drone for this frame (shared speed and node wait)."""
        if self._navigation_context is None:
            return
        if wait_at_node_sec <= 0.0:
            raise ValueError("wait_at_node_sec must be positive")
        self.planner_turn_time += delta_seconds / wait_at_node_sec
        for drone in self.drones:
            drone.update(
                self._navigation_context,
                delta_seconds,
                speed_px_per_sec,
                wait_at_node_sec,
                self.planner_turn_time,
            )

    def synchronized_turn_count(self) -> int:
        """Min cumulative turns among active drones (weighted zone costs)."""
        if not self.drones:
            return 0
        active_drones = [
            drone for drone in self.drones if not drone.has_arrived
        ]
        if active_drones:
            return min(
                drone.cumulative_simulation_turns for drone in active_drones
            )
        return max(drone.cumulative_simulation_turns for drone in self.drones)

    def all_finished(self) -> bool:
        """True when all drones have arrived at the end zone."""
        return all(drone.has_arrived for drone in self.drones)
