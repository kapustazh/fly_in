"""Pygame loop: load assets, build world, run layered rendering."""

from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys
import os
from typing import Any
from collections.abc import Mapping
from assets import AssetManager, AssetError
from layers import (
    RenderContext,
    RenderLayer,
    WaterLayer,
    MapLayer,
    FlagsLayer,
    DronesLayer,
    LayerRenderError,
    MapLegendLayer,
    HUDLayer,
    ZoneTooltipLayer,
    HelpOverlayLayer,
)
from game import GameWorld, GameWorldError
from map_layout import ZoneLayout
from pathfinding import RoutePlanner
from fleet_planner import FleetPlanningError
from drone import DroneArmada, DroneNavigationContext
from simulation_output import SimulationOutput

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
from pygame.surface import Surface  # noqa: E402
import pygame  # noqa: E402


# suppress the pygame startup banner


class Renderer:
    """Window, layer stack, and simulation wiring for the Fly-in demo."""

    WIDTH = 1920
    HEIGHT = 1080

    def __init__(
        self,
        game_world: GameWorld,
        assets: AssetManager,
    ) -> None:
        """Center the map on screen, prepare layers (water through tooltip),
        empty armada."""
        self._game_world = game_world
        self.zones = game_world.zones
        self.connections = game_world.connections
        self.assets = assets
        self.drone_armada: DroneArmada
        self._zone_layout: ZoneLayout
        self._drone_navigation_context: DroneNavigationContext
        self.screen: Surface
        self.clock: pygame.time.Clock
        self.running = True
        self.current_time: int
        self.offset_x: int
        self.offset_y: int
        self._offset_x_f: float = 0.0
        self._offset_y_f: float = 0.0
        self.show_help: bool = False
        self.paused: bool = False
        self._simulation_output_by_turn: list[tuple[int, str]] = []
        self._simulation_output_turn_index: int = 0
        legend_x = self.WIDTH // 32
        legend_y = self.HEIGHT // 4
        self.layers: list[RenderLayer] = [
            WaterLayer(),
            MapLayer(),
            FlagsLayer(),
            DronesLayer(),
            MapLegendLayer(legend_x, legend_y),
            HUDLayer(legend_x, legend_y),
            ZoneTooltipLayer(),
            HelpOverlayLayer(),
        ]

    def _init_pygame(self) -> None:
        """Create the display, title, and clock."""
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Fly-in")
        self.clock = pygame.time.Clock()

    def _compute_offset(self) -> None:
        """Set camera so world origin starts at screen center.

        Draw uses tile top-left at x * tile_w + offset_x;
        choosing offset_x/y like this places the center of the (0,0) zone at
        (WIDTH/2, HEIGHT/2).
        """
        half_w = self.assets.island.width // 2
        half_h = self.assets.island.height // 2
        self.offset_x = self.WIDTH // 2 - half_w
        self.offset_y = self.HEIGHT // 2 - half_h
        self._offset_x_f = float(self.offset_x)
        self._offset_y_f = float(self.offset_y)

    def _move_camera(
        self,
        camera_delta_x: float,
        camera_delta_y: float,
    ) -> None:
        """Move the camera by the given offset in screen pixels."""
        self._offset_x_f += camera_delta_x
        self._offset_y_f += camera_delta_y
        new_off_x = int(round(self._offset_x_f))
        new_off_y = int(round(self._offset_y_f))
        delta_x = new_off_x - self.offset_x
        delta_y = new_off_y - self.offset_y
        if delta_x == 0 and delta_y == 0:
            return

        self.offset_x = new_off_x
        self.offset_y = new_off_y

        # Update render offsets; drones stay in world-space pixels.
        self._zone_layout = ZoneLayout(
            pixel_center_by_zone=self._zone_layout.pixel_center_by_zone,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
        )
        if self._drone_navigation_context is not None:
            self._drone_navigation_context = DroneNavigationContext(
                layout=self._zone_layout,
                movement_model=self._drone_navigation_context.movement_model,
                reference_bridge_pixels=(
                    self._drone_navigation_context.reference_bridge_pixels
                ),
            )

    def _build_zone_layout(self) -> None:
        """World-space pixel target per zone plus current render offsets."""
        tile_w = self.assets.island.width
        half_w = self.assets.island.width // 2
        half_h = self.assets.island.height // 2
        pixel_center_by_zone: dict[str, tuple[float, float]] = {}
        for zone_name, zone in self.zones.items():
            tile_x, tile_y = zone["coordinates"]
            center_x = float(tile_x * tile_w + half_w)
            center_y = float(tile_y * tile_w + half_h)
            pixel_center_by_zone[zone_name] = (center_x, center_y)
        self._zone_layout = ZoneLayout(
            pixel_center_by_zone=pixel_center_by_zone,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
        )

    def _build_context(self) -> RenderContext:
        """Per-frame snapshot for layers (time, mouse, armada, etc.)."""
        return RenderContext(
            zones=self.zones,
            connections=self.connections,
            layout=self._zone_layout,
            assets=self.assets,
            current_time=self.current_time,
            width=self.WIDTH,
            height=self.HEIGHT,
            mouse_position=pygame.mouse.get_pos(),
            drone_armada=self.drone_armada,
            navigation_context=self._drone_navigation_context,
            start_zone_name=self._game_world.start_zone_name,
            end_zone_name=self._game_world.end_zone_name,
            show_help=self.show_help,
            paused=self.paused,
        )

    def _spawn_armada(self) -> None:
        """Plan timed fleet routes and spawn drones."""
        route_planner = RoutePlanner(self._game_world)
        self._drone_navigation_context = DroneNavigationContext(
            layout=self._zone_layout,
            movement_model=route_planner.movement_model,
            reference_bridge_pixels=self.assets.island.width,
        )
        self.drone_armada = DroneArmada()
        self.drone_armada.create_an_armada(
            drone_count=self._game_world.num_drones,
            game_world=self._game_world,
            navigation_context=self._drone_navigation_context,
        )
        try:
            self.drone_armada.launch_armada(self._game_world, route_planner)
        except FleetPlanningError as e:
            print(e)
            pygame.quit()
            sys.exit(1)
        self._simulation_output_by_turn = (
            SimulationOutput.format_simulation_output_by_turn(
                self.drone_armada.drones,
                self._game_world.end_zone_name,
                self._drone_navigation_context.movement_model,
            )
        )
        self._simulation_output_turn_index = 0

    def _restart_simulation(self) -> None:
        """Replan and reset drone motion timing (e.g. after pressing R)."""
        for layer in self.layers:
            if isinstance(layer, DronesLayer):
                layer.reset_frame_clock()
                break
        self._spawn_armada()

    def _handle_events(self) -> None:
        """Handle discrete events (quit/restart)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self.running = False
                if event.key == pygame.K_r:
                    self._restart_simulation()
                if event.key == pygame.K_h:
                    self.show_help = not self.show_help
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused

    def _handle_camera_keys(self, dt_seconds: float) -> None:
        """Smooth camera movement while arrow/WASD keys are held."""
        keys = pygame.key.get_pressed()
        camera_speed = 800.0
        camera_delta_x = 0.0
        camera_delta_y = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            camera_delta_x += camera_speed * dt_seconds
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            camera_delta_x -= camera_speed * dt_seconds
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            camera_delta_y += camera_speed * dt_seconds
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            camera_delta_y -= camera_speed * dt_seconds
        if camera_delta_x != 0.0 or camera_delta_y != 0.0:
            self._move_camera(camera_delta_x, camera_delta_y)

    def _print_turn_simulation_lines(self) -> None:
        """Print simulation lines for turns up to the current planner clock."""
        if self.paused:
            return
        turn_floor = int(self.drone_armada.planner_turn_time)
        while (
            self._simulation_output_turn_index
            < len(self._simulation_output_by_turn)
            and self._simulation_output_by_turn[
                self._simulation_output_turn_index
            ][0]
            <= turn_floor
        ):
            print(
                self._simulation_output_by_turn[
                    self._simulation_output_turn_index
                ][1]
            )
            self._simulation_output_turn_index += 1

    def run(self) -> None:
        """Load assets, enter the event/render loop at 60 FPS until quit."""
        self._init_pygame()
        try:
            self.assets.load()  # load after pygame.init
        except AssetError as e:
            print(e)
            sys.exit(1)
        self._compute_offset()
        self._build_zone_layout()
        self._spawn_armada()
        try:
            while self.running:
                dt_seconds = self.clock.tick(60) / 1000.0
                self._handle_events()
                self._handle_camera_keys(dt_seconds)

                self.current_time = pygame.time.get_ticks()
                context = self._build_context()
                for layer in self.layers:
                    layer.render(self.screen, context)
                self._print_turn_simulation_lines()
                pygame.display.flip()
        except LayerRenderError as e:
            print(f"Render error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            pygame.quit()


class InformationManager:
    """CLI entry: parse map file, build GameWorld, start the Renderer."""

    def __init__(self) -> None:
        self._zones: Mapping[str, dict[str, Any]] = {}
        self._connections: Mapping[str, dict[str, Any]] = {}
        self._num_drones: int = 0

    @property
    def _get_filepath(self) -> Any:
        """Path argument from argparse (first positional)."""
        parser = argparse.ArgumentParser(
            prog="fly-in",
            description=(
                "Parses drone flight/zone/data/connections from a file"
            ),
        )
        parser.add_argument(
            "filepath",
            type=str,
            help="Path to the .txt file with the data",
        )
        args = parser.parse_args()
        return args.filepath

    def parse_input(self) -> None:
        """Parse the map file into zones, connections, and drone count."""
        try:
            map_parser = InputParser()
            map_parser.parse_lines(self._get_filepath)
            map_parser.parse_input()
            if not map_parser.get_zones:
                raise ParsingError("No zones provided")
            self._zones = map_parser.get_zones
            self._connections = map_parser.connections
            self._num_drones = map_parser.number_of_drones
        except (FileReaderError, ParsingError, Exception) as e:
            print(e)
            sys.exit(1)

    def run(self) -> None:
        """Parse input, construct the world, and run the game window."""
        self.parse_input()
        assets = AssetManager()
        try:
            game_world = GameWorld.from_parsed_map(
                zones=self._zones,
                connections=self._connections,
                num_drones=self._num_drones,
            )
        except GameWorldError as e:
            print(e)
            sys.exit(1)
        Renderer(game_world=game_world, assets=assets).run()
