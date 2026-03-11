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
    mouse_position: tuple[int, int]


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
    TINT_ALPHA = 190
    RAINBOW_CYCLE_MS = 6000

    def render(self, screen: Surface, context: RenderContext) -> None:
        self._render_bridges(screen, context)
        self._render_zones(screen, context)

    def _resolve_color(
        self,
        color_name: str,
        current_time: int,
    ) -> pygame.Color | None:
        if color_name == "rainbow":
            hue = int(
                (current_time % self.RAINBOW_CYCLE_MS)
                / self.RAINBOW_CYCLE_MS
                * 360
            )
            color = pygame.Color(0, 0, 0)
            color.hsva = (hue, 100, 100, 100)
            return color
        try:
            return pygame.Color(color_name)
        except ValueError:
            print(f"[MapLayer] Unknown color '{color_name}', skipping tint.")
            return None

    def _get_tinted_surface(
        self,
        base_surface: Surface,
        tint_color: pygame.Color,
    ) -> Surface:

        tinted_surface = base_surface.copy()

        tint_overlay = pygame.Surface(base_surface.get_size(), pygame.SRCALPHA)
        tint_overlay.fill((tint_color.r, tint_color.g, tint_color.b, 255))

        alpha_mask = base_surface.copy()
        alpha_mask.fill(
            (255, 255, 255, self.TINT_ALPHA),
            None,
            pygame.BLEND_RGBA_MULT,
        )
        tint_overlay.blit(
            alpha_mask,
            (0, 0),
            special_flags=pygame.BLEND_RGBA_MULT,
        )

        tinted_surface.blit(tint_overlay, (0, 0))
        return tinted_surface

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
            metadata = zone.get("metadata")
            is_blocked = getattr(metadata, "zone", "normal") == "blocked"
            zone_color = getattr(metadata, "color", None)

            base_surface = (
                context.assets.obstacle.surface
                if is_blocked
                else context.assets.island.surface
            )
            tint_color = (
                self._resolve_color(zone_color, context.current_time)
                if zone_color is not None
                else None
            )
            surface_to_draw = (
                self._get_tinted_surface(base_surface, tint_color)
                if tint_color is not None
                else base_surface
            )

            y_offset = -4 if is_blocked else 0
            if is_blocked:
                screen.blit(
                    surface_to_draw,
                    (
                        x * tile_w + context.offset_x,
                        y * tile_w + context.offset_y + y_offset,
                    ),
                )
            else:
                screen.blit(
                    surface_to_draw,
                    (
                        x * tile_w + context.offset_x,
                        y * tile_w + context.offset_y + y_offset,
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
        strict: bool = True,
    ) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.strict = strict

    def render(self, screen: Surface, context: RenderContext) -> None:
        font_frames = context.assets.wood_font.frames
        current_position = self.x
        space_width = font_frames["A"].get_width()
        for char in self.text:
            if char in font_frames:
                char_surface = font_frames[char]
                screen.blit(char_surface, (current_position, self.y))
                current_position += char_surface.get_width() - 1
            else:
                if self.strict and char != " ":
                    raise LayerRenderError(f"No character in the font: {char}")
                current_position += space_width

    def get_text_width(self, context: RenderContext) -> int:
        """Measure pixel width with the same rules as `render()`."""
        font_frames = context.assets.wood_font.frames
        space_width = font_frames["A"].get_width()
        width = 0
        for char in self.text:
            if char in font_frames:
                width += font_frames[char].get_width() - 1
            else:
                if self.strict and char != " ":
                    raise LayerRenderError(f"No character in the font: {char}")
                width += space_width
        return width


class HUDLayer(RenderLayer):
    def render(self, screen: Surface, context: RenderContext) -> None:
        TextLayer("Number of turns: 0", 10, 10).render(screen, context)


class MapLegendLayer(RenderLayer):
    BOARD_SIZE = 3
    ICON_SIZE = 32

    def __init__(
        self,
        x: int,
        y: int,
    ) -> None:
        self.text: TextLayer
        self.x = x
        self.y = y

    def render(self, screen: Surface, context: RenderContext) -> None:
        self._render_board(screen, context)
        self._render_objects(screen, context)
        self._draw_amogus(screen, context)

    def _render_board(self, screen: Surface, context: RenderContext) -> None:
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
        self.text = TextLayer(
            "Map Legend",
            self.x + (self.BOARD_SIZE * context.assets.wood_tile.width) // 4,
            self.y,
        )
        self.text.render(screen, context)

    def _render_objects(self, screen: Surface, context: RenderContext) -> None:
        objects: list[tuple[Surface, str]] = [
            (context.assets.island.surface, "Zone"),
            (
                self.get_current_sprite(
                    current_time=context.current_time,
                    sprite=context.assets.ua_flag,
                ),
                "Start hub",
            ),
            (
                self.get_current_sprite(
                    current_time=context.current_time,
                    sprite=context.assets.russia_flag,
                ),
                "End hub",
            ),
            (context.assets.obstacle.surface, "Obstacle"),
        ]

        tile_w = context.assets.wood_tile.width
        text_x = self.x + self.BOARD_SIZE // 2 * tile_w
        current_y = self.y + tile_w
        for surface, label in objects:
            icon = pygame.transform.scale(
                surface, (self.ICON_SIZE, self.ICON_SIZE)
            )
            screen.blit(icon, (self.x, current_y))
            TextLayer(label, text_x, current_y).render(screen, context)
            current_y += self.ICON_SIZE + 10

    def _draw_amogus(self, screen: Surface, context: RenderContext) -> None:
        amogus = pygame.transform.scale(
            context.assets.amogus.surface, (self.ICON_SIZE, self.ICON_SIZE)
        )
        screen.blit(
            amogus,
            (self.x, self.y),
        )


class ZoneTooltipLayer(RenderLayer):
    PADDING: int = 8
    LINE_SPACING: int = 4
    BG_COLOR: tuple[int, int, int, int] = (30, 20, 10, 210)
    BORDER_COLOR: tuple[int, int, int] = (200, 170, 100)
    CURSOR_OFFSET: int = 1

    def _get_hovered_zone(
        self,
        context: RenderContext,
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the (name, zone) pair the mouse is currently over."""
        tile_w = context.assets.island.width
        mx, my = context.mouse_position

        for name, zone in context.zones.items():
            coords = zone.get("coordinates")
            if not coords or len(coords) < 2:
                continue
            x, y = coords
            rect = pygame.Rect(
                x * tile_w + context.offset_x,
                y * tile_w + context.offset_y,
                tile_w,
                tile_w,
            )
            if rect.collidepoint(mx, my):
                return name, zone

        return None

    def _build_lines(
        self,
        name: str,
        zone: dict[str, Any],
        context: RenderContext,
    ) -> list[str]:
        metadata = zone.get("metadata")
        hub_type = zone.get("hub_type", "hub")
        zone_type = getattr(metadata, "zone", "normal")
        max_drones = getattr(metadata, "max_drones", 1)
        color = getattr(metadata, "color", None)
        zone_conn = context.connections.get(name, {})
        neighbors: set[str] = zone_conn.get("connections", set())
        conn_meta: dict[str, Any] = zone_conn.get("metadata", {})

        lines: list[str] = [
            f"name: {name}",
            f"type: {hub_type}",
            f"zone: {zone_type}",
            f"max drones: {max_drones}",
        ]
        if color is not None:
            lines.append(f"color: {color}")
        if neighbors:
            lines.append(f"connections: {len(neighbors)}")
            for neighbor in sorted(neighbors):
                capacity = getattr(
                    conn_meta.get(neighbor), "max_link_capacity", 1
                )
                lines.append(f"to {neighbor}: capacity {capacity}")
        return lines

    def _get_box_size(
        self,
        lines: list[str],
        context: RenderContext,
    ) -> tuple[int, int, int]:
        """Return (char_height, box_width, box_height) for the tooltip."""
        font_frames = context.assets.wood_font.frames
        char_h = font_frames["A"].get_height()
        max_line_w = max(
            TextLayer(line, 0, 0, strict=False).get_text_width(context)
            for line in lines
        )
        box_w = max_line_w + 2 * self.PADDING
        box_h = (char_h + self.LINE_SPACING) * len(lines) + 2 * self.PADDING
        return char_h, box_w, box_h

    def _get_box_position(
        self,
        context: RenderContext,
        box_w: int,
        box_h: int,
    ) -> tuple[int, int]:
        mx, my = context.mouse_position
        bx = mx + self.CURSOR_OFFSET
        by = my + self.CURSOR_OFFSET
        return bx, by

    def _render_lines(
        self,
        screen: Surface,
        context: RenderContext,
        lines: list[str],
        bx: int,
        by: int,
        char_h: int,
    ) -> None:
        current_y = by + self.PADDING
        for line in lines:
            TextLayer(line, bx + self.PADDING, current_y, strict=False).render(
                screen,
                context,
            )
            current_y += char_h + self.LINE_SPACING

    def render(self, screen: Surface, context: RenderContext) -> None:
        """Render a tooltip with all zone info when hovering over a tile."""
        hovered = self._get_hovered_zone(context)
        if hovered is None:
            return

        name, zone = hovered
        lines = self._build_lines(name, zone, context)
        char_h, box_w, box_h = self._get_box_size(lines, context)
        bx, by = self._get_box_position(context, box_w, box_h)

        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill(self.BG_COLOR)
        screen.blit(bg, (bx, by))
        pygame.draw.rect(screen, self.BORDER_COLOR, (bx, by, box_w, box_h), 2)

        self._render_lines(screen, context, lines, bx, by, char_h)
