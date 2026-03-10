from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, cast
from collections.abc import Mapping
import pygame
from assets import AssetManager
from pygame.surface import Surface


SAND_COLOR = (194, 178, 128)


class LayerRenderError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Layer render error: {detail}")


@dataclass
class RenderContext:
    zones: Mapping[str, dict[str, Any]]
    connections: Mapping[str, dict[str, Any]]
    assets: AssetManager
    current_time: int
    offset_x: int
    offset_y: int
    width: int
    height: int


class RenderLayer(ABC):
    @abstractmethod
    def render(self, screen: Surface, context: RenderContext) -> None:
        pass

    def get_current_sprite(
        self,
        current_time: int,
        sprite: Any,
        animation: int = 150,
    ) -> Surface:
        return cast(
            Surface,
            sprite.frames[(current_time // animation) % sprite.num_frames],
        )


class WaterLayer(RenderLayer):
    def render(self, screen: Surface, context: RenderContext) -> None:
        current_water = self.get_current_sprite(
            current_time=context.current_time,
            sprite=context.assets.water,
        )
        tile_w = current_water.get_width()
        tile_h = current_water.get_height()
        for x in range(0, context.width, tile_w):
            for y in range(0, context.height, tile_h):
                screen.blit(current_water, (x, y))


class MapLayer(RenderLayer):
    def render(self, screen: Surface, context: RenderContext) -> None:
        self._render_bridges(screen, context)
        self._render_zones(screen, context)

    def _render_bridges(
        self,
        screen: Surface,
        context: RenderContext,
    ) -> None:
        drawn: set[frozenset[str]] = set()
        tile_w = context.assets.island.width
        half_w = context.assets.island.width // 2
        half_h = context.assets.island.height // 2

        for name, zone in context.zones.items():
            if zone.get("metadata", {}).zone == "blocked":
                continue

            x, y = zone["coordinates"]
            for neighbor in context.connections[name].get("connections", {}):
                if neighbor not in context.zones:
                    raise LayerRenderError(
                        f"Neighbor '{neighbor}' referenced in connections but"
                        + " not found in zones"
                    )
                if (
                    context.zones[neighbor].get("metadata", {}).zone
                    == "blocked"
                ):
                    continue
                bridge = frozenset((name, neighbor))
                if bridge in drawn:
                    continue

                nx, ny = context.zones[neighbor]["coordinates"]
                start = (
                    x * tile_w + context.offset_x + half_w,
                    y * tile_w + context.offset_y + half_h,
                )
                end = (
                    nx * tile_w + context.offset_x + half_w,
                    ny * tile_w + context.offset_y + half_h,
                )
                pygame.draw.line(screen, SAND_COLOR, start, end, 4)
                drawn.add(bridge)

    def _render_zones(
        self,
        screen: Surface,
        context: RenderContext,
    ) -> None:
        tile_w = context.assets.island.width
        for zone in context.zones.values():
            x, y = zone["coordinates"]
            is_blocked = zone.get("metadata", {}).zone == "blocked"
            if is_blocked:
                screen.blit(
                    context.assets.obstacle.surface,
                    (
                        x * tile_w + context.offset_x,
                        y * tile_w + context.offset_y - 4,
                    ),
                )
            else:
                screen.blit(
                    context.assets.island.surface,
                    (
                        x * tile_w + context.offset_x,
                        y * tile_w + context.offset_y,
                    ),
                )


class FlagsLayer(RenderLayer):
    def render(self, screen: Surface, context: RenderContext) -> None:
        tile_w = context.assets.island.width
        current_ua_flag = self.get_current_sprite(
            current_time=context.current_time,
            sprite=context.assets.ua_flag,
        )
        current_russian_flag = self.get_current_sprite(
            current_time=context.current_time,
            sprite=context.assets.russia_flag,
        )

        for zone in context.zones.values():
            x, y = zone["coordinates"]
            if zone.get("hub_type") == "start_hub":
                screen.blit(
                    current_ua_flag,
                    (
                        x * tile_w + context.offset_x + 7,
                        y * tile_w + context.offset_y - 65,
                    ),
                )
            if zone.get("hub_type") == "end_hub":
                screen.blit(
                    current_russian_flag,
                    (
                        x * tile_w + context.offset_x + 7,
                        y * tile_w + context.offset_y - 65,
                    ),
                )


class DronesLayer(RenderLayer):
    def render(self, screen: Surface, context: RenderContext) -> None:
        tile_w = context.assets.island.width
        for zone in context.zones.values():
            x = zone["coordinates"][0] * tile_w
            y = zone["coordinates"][1] * tile_w
            if zone.get("hub_type") == "start_hub":
                drone = context.assets.drone_sprite.get_drone_frame(
                    context.current_time
                )
                screen.blit(
                    drone,
                    (x + context.offset_x, y + context.offset_y - 40),
                )


class TextLayer(RenderLayer):
    def __init__(
        self,
        text: str,
        x: int,
        y: int,
    ) -> None:
        self.text = text
        self.x = x
        self.y = y

    def render(self, screen: Surface, context: RenderContext) -> None:
        current_position = self.x
        for char in self.text:
            if char in context.assets.wood_font.frames:
                char_surface = context.assets.wood_font.frames[char]
                screen.blit(char_surface, (current_position, self.y))
                current_position += char_surface.get_width() - 2
            elif char == " ":
                space_width = context.assets.wood_font.frames["A"].get_width()
                current_position += space_width
            else:
                raise LayerRenderError(f"No character in the font: {char}")


class HUDLayer(RenderLayer):
    pass


class MapLegendLayer(RenderLayer):
    BOARD_SIZE = 3

    def __init__(
        self,
        x: int,
        y: int,
    ) -> None:
        self.text: TextLayer
        self.x = x
        self.y = y

    def render(self, screen: Surface, context: RenderContext) -> None:
        tile_w = context.assets.wood_tile.width
        current_x = self.x
        for _ in range(self.BOARD_SIZE):
            current_y = self.y
            for _ in range(self.BOARD_SIZE):
                screen.blit(
                    context.assets.wood_tile.surface, (current_x, current_y)
                )
                current_y += tile_w
            current_x += tile_w
        self.text = TextLayer("Map Legend", self.x + tile_w, self.y)
        self.text.render(screen, context)
