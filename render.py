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
)
from game import GameWorld
from map_layout import ZoneLayout
from pathfinding import RoutePlanner
from drone import DroneArmada, DroneNavigationContext

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
from pygame.surface import Surface  # noqa: E402
import pygame  # noqa: E402


# suppress the pygame startup banner


class Renderer:
    WIDTH = 1920
    HEIGHT = 1080

    def __init__(
        self,
        game_world: GameWorld,
        assets: AssetManager,
    ) -> None:
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
        ]

    def _init_pygame(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Fly-in")
        self.clock = pygame.time.Clock()

    def _compute_offset(self) -> None:
        tile_w = self.assets.island.width
        x = [zone["coordinates"][0] * tile_w for zone in self.zones.values()]
        y = [zone["coordinates"][1] * tile_w for zone in self.zones.values()]
        self.offset_x = self.WIDTH // 2 - (min(x) + max(x)) // 2
        self.offset_y = self.HEIGHT // 2 - (min(y) + max(y)) // 2

    def _build_zone_layout(self) -> None:
        """Pixel target per zone: island tile center in screen space."""
        tile_w = self.assets.island.width
        half_w = self.assets.island.width * 0.5
        half_h = self.assets.island.height * 0.5
        pixel_center_by_zone: dict[str, tuple[float, float]] = {}
        for zone_name, zone in self.zones.items():
            x, y = zone["coordinates"]
            px = float(x * tile_w + self.offset_x + half_w)
            py = float(y * tile_w + self.offset_y + half_h)
            pixel_center_by_zone[zone_name] = (px, py)
        self._zone_layout = ZoneLayout(
            pixel_center_by_zone=pixel_center_by_zone,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
        )

    def _build_context(self) -> RenderContext:
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
        )

    def _spawn_armada(self) -> None:
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

    def _restart_simulation(self) -> None:
        for layer in self.layers:
            if isinstance(layer, DronesLayer):
                layer.reset_frame_clock()
                break
        self._spawn_armada()

    def run(self) -> None:
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
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            self.running = False
                        if event.key == pygame.K_r:
                            self._restart_simulation()
                self.current_time = pygame.time.get_ticks()
                context = self._build_context()
                for layer in self.layers:
                    layer.render(self.screen, context)
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
    def __init__(self) -> None:
        self._zones: Mapping[str, Dict[str, Any]] = {}
        self._connections: Mapping[str, Dict[str, Any]] = {}
        self._num_drones: int = 0

    @property
    def _get_filepath(self) -> Any:
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


if __name__ == "__main__":
    InformationManager().run()
