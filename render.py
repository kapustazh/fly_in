import os
from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys
from typing import Dict, Any
from collections.abc import Mapping

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

# suppress the pygame startup banner


class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance


class Sprite:
    def __init__(self, surface: pygame.Surface, num_frames: int = 0) -> None:
        self.surface = surface
        self.frames: list[pygame.Surface] = []
        self.width = surface.get_width()
        self.height = surface.get_height()
        self.num_frames: int = num_frames

    def update_upscaled_surface(
        self, x: int, y: int, w: int, h: int, factor: int
    ) -> None:
        tile = self.surface.subsurface(pygame.Rect(x, y, w, h))
        new_size = (w * factor, h * factor)
        self.surface = pygame.transform.scale(tile, new_size)

    def prepare_frames(
        self,
        scale: float,
    ) -> None:
        width = self.width // self.num_frames
        height = self.height
        for i in range(self.num_frames):
            rect = pygame.Rect(i * width, 0, width, height)
            frame = self.surface.subsurface(rect)
            frame = pygame.transform.scale(
                frame, (width * scale, height * scale)
            )
            self.frames.append(frame)


class Renderer(Singleton):
    WIDTH = 1920
    HEIGHT = 1080

    def __init__(self):
        self.screen: pygame.Surface
        self.clock: pygame.time.Clock
        self.water_sprite: Sprite
        self.icon_sprite: Sprite
        self.island_sprite: Sprite
        self.obstacle_sprite: Sprite
        self.campfire_sprite: Sprite
        self.ua_flag_sprite: Sprite
        self.running = True

    def _init_pygame(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Fly-in")
        self.clock = pygame.time.Clock()

    def _set_sprites(self) -> None:
        try:
            self.water_sprite = Sprite(
                surface=pygame.image.load("water.png"), num_frames=4
            )
            self.icon_sprite = Sprite(surface=pygame.image.load("icon.jpg"))
            self.island_sprite = Sprite(
                surface=pygame.image.load("grass.png").convert_alpha(),
            )
            self.obstacle_sprite = Sprite(
                surface=pygame.image.load("obstacle.png")
            )
            self.campfire_sprite = Sprite(
                surface=pygame.image.load("campfire.png"), num_frames=6
            )
            self.ua_flag_sprite = Sprite(
                surface=pygame.image.load("flag_ua.png"), num_frames=6
            )
        except FileNotFoundError as e:
            print(e)
            sys.exit()

    def _prepare_sprites(self) -> None:
        self.water_sprite.update_upscaled_surface(48, 48, 16, 16, 2)
        self.water_sprite.prepare_frames(scale=2.0)
        self.campfire_sprite.prepare_frames(scale=1.2)
        self.ua_flag_sprite.prepare_frames(scale=1.2)
        pygame.transform.scale(self.obstacle_sprite.surface, (32, 32))
        pygame.display.set_icon(self.icon_sprite.surface)

    def _render_water(self, water_tile: pygame.Surface) -> None:
        for x in range(0, self.water_sprite.width, self.water_sprite.width):
            for y in range(
                0, self.water_sprite.height, self.water_sprite.height
            ):
                self.screen.blit(water_tile, (x, y))

    def _render_bridges(
        self,
        zones: Mapping[str, Dict[str, Any]],
        connections: Mapping[str, Dict[str, Any]],
    ) -> None:
        drawn_bridges: set[tuple[str, str]] = set()
        tile_w = self.island_sprite.width
        for name, zone in zones.items():
            coords = zone["coordinates"]
            x = coords[0] * tile_w
            y = coords[1] * tile_w

            if zone.get("metadata", {}).zone == "blocked":
                continue

            connections_new = connections[name].get("connections", [])
            for neighbor in connections_new:

                if zones[neighbor].get("metadata", {}).zone == "blocked":
                    continue

                pair = sorted([name, neighbor])
                connection_pair: tuple[str, str] = (pair[0], pair[1])

                if connection_pair not in drawn_bridges:
                    nx, ny = zones[neighbor]["coordinates"]
                    n_draw_x = nx * tile_w
                    n_draw_y = ny * tile_w

                    start_pt = (
                        x + self.WIDTH // 2 + tile_w // 2,
                        y + self.HEIGHT // 2 + tile_w // 2,
                    )
                    end_pt = (
                        n_draw_x + self.WIDTH // 2 + tile_w // 2,
                        n_draw_y + self.HEIGHT // 2 + tile_w // 2,
                    )

                    # Draw a solid, clean line
                    pygame.draw.line(
                        self.screen, (194, 178, 128), start_pt, end_pt, 4
                    )

                    drawn_bridges.add(connection_pair)

    def _get_current_sprite(
        self, sprite: Sprite, animation: int = 150
    ) -> pygame.Surface:
        return sprite.frames[
            (self.current_time // animation) % sprite.num_frames
        ]

    def run(self) -> None:
        self._init_pygame()
        self._set_sprites()
        self._prepare_sprites()
        zones = InformationManager().zones
        connections = InformationManager().connections

        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            self.running = False
                self.current_time = pygame.time.get_ticks()
                current_fire = self._get_current_sprite(self.campfire_sprite)
                current_flag = self._get_current_sprite(self.ua_flag_sprite)
                current_water = self._get_current_sprite(self.water_sprite)
                self._render_water(current_water)
                self._render_bridges(zones, connections)

                for zone in zones.values():
                    coords = zone["coordinates"]
                    tile_w = self.island_sprite.width
                    x = coords[0] * tile_w
                    y = coords[1] * tile_w

                    is_blocked = zone.get("metadata", {}).zone == "blocked"

                    if is_blocked:
                        self.screen.blit(
                            self.obstacle_sprite.surface,
                            (x + self.WIDTH // 2, y + self.HEIGHT // 2 - 4),
                        )
                    else:
                        self.screen.blit(
                            self.island_sprite.surface,
                            (x + self.WIDTH // 2, y + self.HEIGHT // 2),
                        )

                    if zone.get("hub_type") == "end_hub":
                        fire_x = x + self.WIDTH // 2 - 3
                        fire_y = y + self.HEIGHT // 2 - 15
                        # Draw the current frame of the animation
                        self.screen.blit(current_fire, (fire_x, fire_y))
                    if zone.get("hub_type") == "start_hub":
                        flag_x = x + self.WIDTH // 2 + 5
                        flag_y = y + self.HEIGHT // 2 - 50

                        self.screen.blit(current_flag, (flag_x, flag_y))
                pygame.display.flip()
                self.clock.tick(60)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            pygame.quit()


class InformationManager(Singleton):
    def __init__(self):
        self._zones: Mapping[str, Dict[str, Any]] = {}
        self._connections: Mapping[str, Dict[str, Any]] = {}

    @property
    def _get_filepath(self) -> str:
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
    def set_zones(self, zones: Dict[str, Dict[str, Any]]) -> None:
        self._zones = zones

    @property
    def connections(self) -> Mapping[str, Dict[str, Any]]:
        return self._connections

    @connections.setter
    def set_connections(self, connections: Dict[str, Dict[str, Any]]) -> None:
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
        Renderer().run()


if __name__ == "__main__":
    info_manager = InformationManager()
    info_manager.run()
