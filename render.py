import os

from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys
from typing import Dict, Any
from collections.abc import Mapping
from enum import Enum
from sprites import Sprite, AnimatedSprite, Font
from drone import DroneSprite
from assets import AssetManager, AssetError


os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

# suppress the pygame startup banner


class Color(Enum):
    SAND = (194, 178, 128)


class RenderError(Exception):
    def __init__(self, detail: str) -> None:
        message = f"Error occurred while rendering: {detail}"
        super().__init__(message)


class Renderer:
    WIDTH = 1920
    HEIGHT = 1080

    def __init__(
        self,
        zones: Mapping[str, Dict[str, Any]],
        connections: Mapping[str, Dict[str, Any]],
        assets: AssetManager,
    ) -> None:
        self.zones = zones
        self.connections = connections
        self.assets = assets
        self.screen: pygame.Surface
        self.clock: pygame.time.Clock
        self.running = True
        self.current_time: int
        self.offset_x: int
        self.offset_y: int

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

    def _render_water(self) -> None:
        assets = self.assets
        current_water = self._get_current_sprite(assets.water)
        tile_w = current_water.get_width()
        tile_h = current_water.get_height()
        for x in range(0, self.WIDTH, tile_w):
            for y in range(0, self.HEIGHT, tile_h):
                self.screen.blit(current_water, (x, y))

    def _render_bridges(
        self,
    ) -> None:
        assets = self.assets
        drawn: set[frozenset[str]] = set()
        tile_w = assets.island.width
        half_w = assets.island.width // 2
        half_h = assets.island.height // 2
        for name, zone in self.zones.items():
            if zone.get("metadata", {}).zone == "blocked":
                continue

            x, y = zone["coordinates"]
            for neighbor in self.connections[name].get("connections", {}):
                if neighbor not in self.zones:
                    raise RenderError(
                        f"Neighbor '{neighbor}' referenced in connections but"
                        + " not found in zones"
                    )
                if self.zones[neighbor].get("metadata", {}).zone == "blocked":
                    continue
                bridge = frozenset((name, neighbor))
                if bridge in drawn:
                    continue

                nx, ny = self.zones[neighbor]["coordinates"]
                start = (
                    x * tile_w + self.offset_x + half_w,
                    y * tile_w + self.offset_y + half_h,
                )
                end = (
                    nx * tile_w + self.offset_x + half_w,
                    ny * tile_w + self.offset_y + half_h,
                )
                pygame.draw.line(self.screen, Color.SAND.value, start, end, 4)
                drawn.add(bridge)

    def _render_zones(
        self,
    ) -> None:
        assets = self.assets
        tile_w = assets.island.width
        for zone in self.zones.values():
            coords = zone["coordinates"]
            x, y = coords
            is_blocked = zone.get("metadata", {}).zone == "blocked"
            if is_blocked:
                self.screen.blit(
                    assets.obstacle.surface,
                    (
                        x * tile_w + self.offset_x,
                        y * tile_w + self.offset_y - 4,
                    ),
                )
            else:
                self.screen.blit(
                    assets.island.surface,
                    (x * tile_w + self.offset_x, y * tile_w + self.offset_y),
                )

    def _render_flags(self) -> None:
        assets = self.assets
        tile_w = assets.island.width
        current_ua_flag = self._get_current_sprite(assets.ua_flag)
        current_russian_flag = self._get_current_sprite(assets.russia_flag)
        for zone in self.zones.values():
            coords = zone["coordinates"]
            x, y = coords
            if zone.get("hub_type") == "start_hub":
                self.screen.blit(
                    current_ua_flag,
                    (
                        x * tile_w + self.offset_x + 7,
                        y * tile_w + self.offset_y - 65,
                    ),
                )
            if zone.get("hub_type") == "end_hub":
                self.screen.blit(
                    current_russian_flag,
                    (
                        x * tile_w + self.offset_x + 7,
                        y * tile_w + self.offset_y - 65,
                    ),
                )

    def _get_current_sprite(
        self, sprite: AnimatedSprite, animation: int = 150
    ) -> pygame.Surface:
        return sprite.frames[
            (self.current_time // animation) % sprite.num_frames
        ]

    def _render_text(
        self,
        text: str,
        x: int,
        y: int,
    ) -> None:
        assets = self.assets
        curren_position = x

        for char in text:
            if char in assets.wood_font.frames:
                char_surface = assets.wood_font.frames[char]

                self.screen.blit(char_surface, (curren_position, y))

                curren_position += char_surface.get_width() - 2
            elif char == " ":
                space_width = assets.wood_font.frames["A"].get_width()
                curren_position += space_width
            else:
                raise RenderError(f"No character in the font :{char}")

    def _render_drones(
        self,
    ) -> None:
        assets = self.assets
        tile_w = assets.island.width
        for zone in self.zones.values():
            coords = zone["coordinates"]
            x = coords[0] * tile_w
            y = coords[1] * tile_w
            if zone.get("hub_type") == "start_hub":
                drone = assets.drone_sprite.get_drone_frame(self.current_time)
                self.screen.blit(
                    drone,
                    (x + self.offset_x, y + self.offset_y - 40),
                )

    def run(self) -> None:
        self._init_pygame()
        try:
            self.assets.load()  # load after pygame.init
        except AssetError as e:
            print(e)
            sys.exit(1)
        self._compute_offset()
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            self.running = False
                self.current_time = pygame.time.get_ticks()
                self._render_water()
                self._render_bridges()
                self._render_zones()
                self._render_flags()
                self._render_drones()
                self._render_text(
                    "Map Legend", self.WIDTH // 2 - 800, self.HEIGHT // 4
                )
                pygame.display.flip()
                self.clock.tick(60)
        except RenderError as e:
            print(f"Render error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            pygame.quit()


class InformationManager:
    def __init__(self) -> None:
        if hasattr(self, "__initialized"):
            return
        self._zones: Mapping[str, Dict[str, Any]] = {}
        self._connections: Mapping[str, Dict[str, Any]] = {}

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
        except (FileReaderError, ParsingError, Exception) as e:
            print(e)
            sys.exit(1)

    def run(self) -> None:
        self.parse_input()
        # build asset manager once and inject
        assets = AssetManager()
        Renderer(
            zones=self._zones, connections=self._connections, assets=assets
        ).run()


if __name__ == "__main__":
    info_manager = InformationManager().run()
