from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys
import os
from typing import Dict, Any
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
        self.zones = game_world.zones
        self.connections = game_world.connections
        self.game_world = game_world
        self.assets = assets
        self.zones_pixel_pos: dict[str, tuple[float, float]] = {}
        self.screen: Surface
        self.clock: pygame.time.Clock
        self.running = True
        self.current_time: int
        self.offset_x: int
        self.offset_y: int
        self.layers: list[RenderLayer] = [
            WaterLayer(),
            MapLayer(),
            FlagsLayer(),
            DronesLayer(),
            MapLegendLayer(self.WIDTH // 32, self.HEIGHT // 4),
            HUDLayer(),
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

    # 40 - offeset to make it a bit heigher
    def _compute_zones_pixel_pos(self) -> None:
        """Pre-compute pixel positions for all zones."""
        tile_w = self.assets.island.width
        for zone_name, zone in self.zones.items():
            x, y = zone["coordinates"]
            px = float(x * tile_w + self.offset_x)
            py = float(y * tile_w + self.offset_y - 40)
            self.zones_pixel_pos[zone_name] = (px, py)

    def _build_context(self) -> RenderContext:
        return RenderContext(
            zones=self.zones,
            connections=self.connections,
            zones_pixel_pos=self.zones_pixel_pos,
            assets=self.assets,
            current_time=self.current_time,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
            width=self.WIDTH,
            height=self.HEIGHT,
            mouse_position=pygame.mouse.get_pos(),
        )

    def run(self) -> None:
        self._init_pygame()
        try:
            self.assets.load()  # load after pygame.init
        except AssetError as e:
            print(e)
            sys.exit(1)
        self._compute_offset()
        self._compute_zones_pixel_pos()
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            self.running = False
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
        game_word = GameWorld(
            zones=self._zones,
            connections=self._connections,
            num_drones=self._num_drones,
        )
        Renderer(game_world=game_word, assets=assets).run()


if __name__ == "__main__":
    info_manager = InformationManager()
    info_manager.run()
