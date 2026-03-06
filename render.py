import os

from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys
from typing import Dict, Any
from collections.abc import Mapping
from enum import Enum
from sprites import Sprite, AnimatedSprite, Font
from drone import DroneSprite

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

# suppress the pygame startup banner


class Color(Enum):
    SAND = (194, 178, 128)


class RenderError(Exception):
    def __init__(self, detail: str) -> None:
        message = f"Error occurred while rendering: {detail}"
        super().__init__(message)


class MegaSuperUltraSingleton(type):
    __instances: dict[Any, Any] = {}

    def __call__(cls, *args: Dict[Any, Any], **kwargs: Dict[Any, Any]) -> Any:
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        return cls.__instances[cls]


class Renderer(metaclass=MegaSuperUltraSingleton):
    WIDTH = 1920
    HEIGHT = 1080

    def __init__(
        self,
        zones: Mapping[str, Dict[str, Any]],
        connections: Mapping[str, Dict[str, Any]],
    ) -> None:
        self.zones = zones
        self.connections = connections
        self.screen: pygame.Surface
        self.clock: pygame.time.Clock
        self.water: AnimatedSprite
        self.icon: Sprite
        self.island: Sprite
        self.obstacle: Sprite
        self.russia_flag: AnimatedSprite
        self.ua_flag: AnimatedSprite
        self.drone: AnimatedSprite
        self.wood_font: Font
        self.wood_tile: Sprite
        self.running = True
        self.current_time: int

    def _init_pygame(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Fly-in")
        self.clock = pygame.time.Clock()

    def _set_sprites(self) -> None:
        try:
            self.water = AnimatedSprite(
                surface=pygame.image.load(
                    "assets/sprites/water.png"
                ).convert_alpha(),
                num_frames=4,
            )
            self.icon = Sprite(
                surface=pygame.image.load(
                    "assets/sprites/icon.jpg"
                ).convert_alpha()
            )
            self.island = Sprite(
                surface=pygame.image.load(
                    "assets/sprites/grass.png"
                ).convert_alpha(),
            )
            self.obstacle = Sprite(
                surface=pygame.image.load(
                    "assets/sprites/obstacle.png"
                ).convert_alpha()
            )
            self.russia_flag = AnimatedSprite(
                surface=pygame.image.load(
                    "assets/sprites/flag_russia.png"
                ).convert_alpha(),
                num_frames=5,
            )
            self.ua_flag = AnimatedSprite(
                surface=pygame.image.load(
                    "assets/sprites/flag_ua.png"
                ).convert_alpha(),
                num_frames=5,
            )
            self.wood_font = Font(
                surface=pygame.image.load(
                    "assets/fonts/WoodFont.png"
                ).convert_alpha(),
            )
            self.wood_tile = Font(
                surface=pygame.image.load(
                    "assets/sprites/wood_tile.png"
                ).convert_alpha(),
            )
            self.drone = DroneSprite(
                surface=pygame.image.load(
                    "assets/sprites/drone_sprite.png"
                ).convert_alpha(),
            )
        except FileNotFoundError as e:
            raise RenderError(str(e))

    def _prepare_sprites(self) -> None:
        self.water.prepare_frames(scale=2.0)
        self.russia_flag.prepare_frames(scale=1.5)
        self.ua_flag.prepare_frames(scale=1.5)
        self.obstacle.surface = pygame.transform.scale_by(
            self.obstacle.surface, factor=1.5
        )
        self.island.update_upscaled_surface(48, 48, 16, 16, 2.5)
        self.wood_font.prepare_frames()
        self.drone.prepare_frames(scale=0.1)
        pygame.display.set_icon(self.icon.surface)

    def _compute_offset(self) -> None:
        tile_w = self.island.width
        x = [zone["coordinates"][0] * tile_w for zone in self.zones.values()]
        y = [zone["coordinates"][1] * tile_w for zone in self.zones.values()]
        self.offset_x = self.WIDTH // 2 - (min(x) + max(x)) // 2
        self.offset_y = self.HEIGHT // 2 - (min(y) + max(y)) // 2

    def _render_water(self) -> None:
        current_water = self._get_current_sprite(self.water)
        tile_w = current_water.get_width()
        tile_h = current_water.get_height()
        for x in range(0, self.WIDTH, tile_w):
            for y in range(0, self.HEIGHT, tile_h):
                self.screen.blit(current_water, (x, y))

    def _render_bridges(
        self,
    ) -> None:
        drawn: set[frozenset[str]] = set()
        tile_w = self.island.width
        half_w = self.island.width // 2
        half_h = self.island.height // 2
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
        tile_w = self.island.width
        for zone in self.zones.values():
            coords = zone["coordinates"]
            x, y = coords
            is_blocked = zone.get("metadata", {}).zone == "blocked"
            if is_blocked:
                self.screen.blit(
                    self.obstacle.surface,
                    (
                        x * tile_w + self.offset_x,
                        y * tile_w + self.offset_y - 4,
                    ),
                )
            else:
                self.screen.blit(
                    self.island.surface,
                    (x * tile_w + self.offset_x, y * tile_w + self.offset_y),
                )

    def _render_flags(self) -> None:
        tile_w = self.island.width
        current_ua_flag = self._get_current_sprite(self.ua_flag)
        curren_russian_flag = self._get_current_sprite(self.russia_flag)
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
                    curren_russian_flag,
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
        curren_position = x

        for char in text:
            if char in self.wood_font.frames:
                char_surface = self.wood_font.frames[char]

                self.screen.blit(char_surface, (curren_position, y))

                curren_position += char_surface.get_width() - 2
            elif char == " ":
                space_width = self.wood_font.frames["A"].get_width()
                curren_position += space_width
            else:
                raise RenderError(f"No character in the font :{char}")

    def _render_drones(
        self,
    ) -> None:
        tile_w = self.island.width
        for zone in self.zones.values():
            coords = zone["coordinates"]
            x = coords[0] * tile_w
            y = coords[1] * tile_w
            if zone.get("hub_type") == "start_hub":
                drone = self.drone.get_drone_frame(self.current_time)
                self.screen.blit(
                    drone,
                    (x + self.offset_x, y + self.offset_y - 40),
                )

    def run(self) -> None:
        self._init_pygame()
        self._set_sprites()
        self._prepare_sprites()
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

    @property
    def zones(self) -> Mapping[str, Dict[str, Any]]:
        return self._zones

    @zones.setter
    def zones(self, zones: Dict[str, Dict[str, Any]]) -> None:
        self._zones = zones

    @property
    def connections(self) -> Mapping[str, Dict[str, Any]]:
        return self._connections

    @connections.setter
    def connections(self, connections: Dict[str, Dict[str, Any]]) -> None:
        self._connections = connections

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
        Renderer(zones=self._zones, connections=self._connections).run()


if __name__ == "__main__":
    info_manager = InformationManager()
    info_manager.run()
