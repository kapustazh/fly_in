"""Pygame loop: load assets, build world, run layered rendering."""

from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys
import os
from typing import Any, Dict
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
from game import GameWorld
from map_layout import ZoneLayout
from pathfinding import RoutePlanner
from drone import DroneArmada, DroneNavigationContext
from simulation_output import format_simulation_output_by_turn

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
        self.drone_armada = DroneArmada()
        self._zone_layout: ZoneLayout | None = None
        self._drone_navigation_context: DroneNavigationContext | None = None
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
        self._simulation_output_emit_index: int = 0
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

    def _move_camera(self, dx: float, dy: float) -> None:
        """Move the camera by (dx, dy) screen pixels."""
        self._offset_x_f += dx
        self._offset_y_f += dy
        new_off_x = int(round(self._offset_x_f))
        new_off_y = int(round(self._offset_y_f))
        delta_x = new_off_x - self.offset_x
        delta_y = new_off_y - self.offset_y
        if delta_x == 0 and delta_y == 0:
            return

        self.offset_x = new_off_x
        self.offset_y = new_off_y

        # Update render offsets; drones stay in world-space pixels.
        assert self._zone_layout is not None
        self._zone_layout = ZoneLayout(
            pixel_center_by_zone=self._zone_layout.pixel_center_by_zone,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
        )

    def _build_zone_layout(self) -> None:
        """World-space pixel target per zone plus current render offsets."""
        tile_w = self.assets.island.width
        half_w = self.assets.island.width // 2
        half_h = self.assets.island.height // 2
        pixel_center_by_zone: dict[str, tuple[float, float]] = {}
        for zone_name, zone in self.zones.items():
            x, y = zone["coordinates"]
            # World-space (no screen offset baked in).
            px = float(x * tile_w + half_w)
            py = float(y * tile_w + half_h)
            pixel_center_by_zone[zone_name] = (px, py)
        self._zone_layout = ZoneLayout(
            pixel_center_by_zone=pixel_center_by_zone,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
        )

    def _build_context(self) -> RenderContext:
        """Per-frame snapshot for layers (time, mouse, armada, etc.)."""
        assert self._zone_layout is not None
        assert self._drone_navigation_context is not None
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
            show_help=self.show_help,
            paused=self.paused,
        )

    def _spawn_armada(self) -> None:
        """Plan routes and spawn drones (fleet planner + fallback)."""
        assert self._zone_layout is not None
        route_planner = RoutePlanner(self._game_world)
        self._drone_navigation_context = DroneNavigationContext(
            layout=self._zone_layout,
            movement_model=route_planner.movement_model,
        )
        self.drone_armada = DroneArmada()
        self.drone_armada.create_an_armada(
            drone_count=self._game_world.num_drones,
            game_world=self._game_world,
            navigation_context=self._drone_navigation_context,
        )
        self.drone_armada.launch_armada(self._game_world, route_planner)
        assert self._drone_navigation_context is not None
        self._simulation_output_by_turn = format_simulation_output_by_turn(
            self.drone_armada.drones,
            self._game_world.end_zone_name,
            self._drone_navigation_context.movement_model,
        )
        self._simulation_output_emit_index = 0

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
        dx = 0.0
        dy = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx += camera_speed * dt_seconds
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx -= camera_speed * dt_seconds
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy += camera_speed * dt_seconds
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy -= camera_speed * dt_seconds
        if dx != 0.0 or dy != 0.0:
            self._move_camera(dx, dy)

    def _emit_due_simulation_lines(self) -> None:
        """Print VII.5 lines for turns up to the current planner clock."""
        if self.paused:
            return
        turn_floor = int(self.drone_armada.planner_turn_time)
        entries = self._simulation_output_by_turn
        idx = self._simulation_output_emit_index
        while idx < len(entries) and entries[idx][0] <= turn_floor:
            print(entries[idx][1])
            idx += 1
        self._simulation_output_emit_index = idx

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
                dt_seconds = self.clock.get_time() / 1000.0
                self._handle_events()
                self._handle_camera_keys(dt_seconds)

                self.current_time = pygame.time.get_ticks()
                context = self._build_context()
                for layer in self.layers:
                    layer.render(self.screen, context)
                self._emit_due_simulation_lines()
                pygame.display.flip()
                self.clock.tick(60)
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
        self._zones: Mapping[str, Dict[str, Any]] = {}
        self._connections: Mapping[str, Dict[str, Any]] = {}
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
            my_parser = InputParser()
            my_parser.parse_lines(self._get_filepath)
            my_parser.parse_input()
            if not my_parser.get_zones or not my_parser.connections:
                raise ParsingError("No zones or connections provided")
            self._zones = my_parser.get_zones
            self._connections = my_parser.connections
            self._num_drones = my_parser.number_of_drones
        except (FileReaderError, ParsingError, Exception) as e:
            print(e)
            sys.exit(1)

    def run(self) -> None:
        """Parse input, construct the world, and run the game window."""
        self.parse_input()
        assets = AssetManager()
        # import pprint

        # pprint.pprint(self._zones)
        # pprint.pprint(self._connections)
        # pprint.pprint(self._num_drones)
        game_world = GameWorld.from_parsed_map(
            zones=self._zones,
            connections=self._connections,
            num_drones=self._num_drones,
        )
        Renderer(game_world=game_world, assets=assets).run()
