"""Layers: water, map, drones, HUD, and shared render context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping
import pygame
from assets import AssetManager
from enum import Enum

from drone import (
    DroneArmada,
    DroneNavigationContext,
    SECONDS_PER_DISCRETE_TURN,
)
from sprites import AnimatedSprite
from map_layout import ZoneLayout
from pygame.surface import Surface


# :D
class Colors(Enum):
    """Named colors shared by map drawing (e.g. bridge lines)."""

    SAND_COLOR = (194, 178, 128)


class LayerRenderError(Exception):
    """Raised when a layer cannot render (e.g. missing glyph)."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Layer render error: {detail}")


@dataclass
class RenderContext:
    """Drawing state: map graph, pixel layout, and simulation (armada)."""

    zones: Mapping[str, dict[str, Any]]
    connections: Mapping[str, dict[str, Any]]
    layout: ZoneLayout
    drone_armada: DroneArmada
    navigation_context: DroneNavigationContext
    assets: AssetManager
    current_time: int
    width: int
    height: int
    mouse_position: tuple[int, int]
    show_help: bool = False
    paused: bool = False


class RenderLayer(ABC):
    """One drawable slice of the frame (background, map, actors, UI)."""

    @abstractmethod
    def render(self, screen: Surface, context: RenderContext) -> None:
        """Paint this layer onto *screen* using *context*."""
        pass

    def get_current_sprite(
        self,
        current_time: int,
        sprite: AnimatedSprite,
        animation: int = 150,
    ) -> Surface:
        """Pick *sprite* frame from *current_time* and *animation* (ms)."""
        frame_index = (current_time // animation) % sprite.num_frames
        return sprite.frames[frame_index]


class WaterLayer(RenderLayer):
    """Tiled animated water filling the window behind the map."""

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
    """Islands, obstacles, tinted zones, and sand bridges between neighbors."""

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
        """Resolve a named or rainbow color to pygame.Color, or None."""
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
        """Copy *base_surface* multiplied by *tint_color* (see TINT_ALPHA)."""

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
        """Draw each zone link once as a sand line between tile centers."""
        drawn: set[frozenset[str]] = set[frozenset[str]]()
        tile_w = context.assets.island.width
        half_w = context.assets.island.width // 2
        half_h = context.assets.island.height // 2

        for name, zone in context.zones.items():
            if zone.get("metadata", {}).zone == "blocked":
                continue

            x, y = zone["coordinates"]
            for neighbor in context.connections.get(name, {}).get(
                "connections", {}
            ):
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
                bridge = frozenset[str | Any]((name, neighbor))
                if bridge in drawn:
                    continue

                nx, ny = context.zones[neighbor]["coordinates"]
                start = (
                    x * tile_w + context.layout.offset_x + half_w,
                    y * tile_w + context.layout.offset_y + half_h,
                )
                end = (
                    nx * tile_w + context.layout.offset_x + half_w,
                    ny * tile_w + context.layout.offset_y + half_h,
                )
                pygame.draw.line(
                    screen, Colors.SAND_COLOR.value, start, end, 4
                )
                drawn.add(bridge)

    def _render_zones(
        self,
        screen: Surface,
        context: RenderContext,
    ) -> None:
        """Blit island/obstacle tiles at grid positions; optional tint."""
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
            screen.blit(
                surface_to_draw,
                (
                    x * tile_w + context.layout.offset_x,
                    y * tile_w + context.layout.offset_y + y_offset,
                ),
            )


class FlagsLayer(RenderLayer):
    """Start-hub flag and end-hub campfire markers above relevant zones."""

    def render(self, screen: Surface, context: RenderContext) -> None:
        tile_w = context.assets.island.width
        current_ua_flag = self.get_current_sprite(
            current_time=context.current_time,
            sprite=context.assets.ua_flag,
        )
        current_campfire = self.get_current_sprite(
            current_time=context.current_time,
            sprite=context.assets.campfire,
        )

        for zone in context.zones.values():
            x, y = zone["coordinates"]
            if zone.get("hub_type") == "start_hub":
                screen.blit(
                    current_ua_flag,
                    (
                        x * tile_w + context.layout.offset_x + 7,
                        y * tile_w + context.layout.offset_y - 65,
                    ),
                )
            if zone.get("hub_type") == "end_hub":
                screen.blit(
                    current_campfire,
                    (
                        x * tile_w + context.layout.offset_x - 1,
                        y * tile_w + context.layout.offset_y - 60,
                    ),
                )


class DronesLayer(RenderLayer):
    """Advances drone simulation each frame and draws each drone sprite."""

    DRONE_SPEED_PX_PER_SEC = 180
    WAIT_AT_NODE_SEC = SECONDS_PER_DISCRETE_TURN
    DRONE_BLIT_ANCHOR_DOWN_PX = 0
    DRONE_DRAW_OFFSET_X = 0

    def __init__(self) -> None:
        """Create a layer; frame delta starts unset until the first render."""
        self.last_time_ms: int | None = None

    def reset_frame_clock(self) -> None:
        """Clear delta-time state (e.g. after restarting the simulation)."""
        self.last_time_ms = None

    def render(self, screen: Surface, context: RenderContext) -> None:
        """Advance drones from elapsed time; blit rotated frames."""
        prev_ms = self.last_time_ms
        if prev_ms is None:
            delta_seconds = 0.0
        else:
            delta_seconds = (context.current_time - prev_ms) / 1000.0
        self.last_time_ms = context.current_time

        drone_armada = context.drone_armada
        if not context.paused:
            drone_armada.update_all(
                delta_seconds,
                self.DRONE_SPEED_PX_PER_SEC,
                self.WAIT_AT_NODE_SEC,
            )

        sprite = context.assets.drone_sprite
        for drone in drone_armada.drones:
            movement_delta_x, movement_delta_y = (
                drone.sprite_render_movement_delta(context.navigation_context)
            )
            frame = sprite.frame_for_vector(
                movement_delta_x,
                movement_delta_y,
                context.current_time,
            )
            px, py = drone.pixel_position
            draw_x = (
                px
                + context.layout.offset_x
                + drone.render_offset_x
                + self.DRONE_DRAW_OFFSET_X
            )
            draw_y = (
                py
                + context.layout.offset_y
                + drone.render_offset_y
                + self.DRONE_BLIT_ANCHOR_DOWN_PX
            )
            screen.blit(
                frame,
                (
                    int(draw_x - frame.get_width() // 2),
                    int(draw_y - frame.get_height() // 2),
                ),
            )


class TextLayer(RenderLayer):
    """Bitmap font string at a fixed position (wood font glyph atlas)."""

    def __init__(
        self,
        text: str,
        x: int,
        y: int,
        strict: bool = True,
    ) -> None:
        """Place *text* at (*x*, *y*); *strict* errors on missing glyphs."""
        self.text = text
        self.x = x
        self.y = y
        self.strict = strict

    def render(self, screen: Surface, context: RenderContext) -> None:
        """Draw *self.text* left to right; unknown chars error if *strict*."""
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
        """Measure pixel width with the same rules as render()."""
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
    """Turn counter and restart hint aligned with the map legend panel."""

    def __init__(self, legend_x: int, legend_y: int) -> None:
        """Align HUD with MapLegendLayer using *legend_x* and *legend_y*."""
        self.legend_x = legend_x
        self.legend_y = legend_y

    def render(self, screen: Surface, context: RenderContext) -> None:
        """Turns, win, pause, and help lines under the legend."""
        synchronized_turn_count = (
            context.drone_armada.synchronized_turn_count()
        )
        if not context.drone_armada.all_finished():
            TextLayer(
                f"Number of turns: {synchronized_turn_count}",
                10,
                10,
            ).render(screen, context)
        else:
            TextLayer(
                f"YOU WIN WITH {synchronized_turn_count} TURNS",
                10,
                10,
            ).render(screen, context)
        if context.paused:
            TextLayer("PAUSED", 10, 34).render(screen, context)

        base_y = MapLegendLayer.content_bottom_y(context, self.legend_y)
        TextLayer(
            "PRESS H FOR HELP",
            self.legend_x,
            base_y,
            strict=False,
        ).render(screen, context)


class HelpOverlayLayer(RenderLayer):
    """Full-screen help overlay toggled by H."""

    PADDING = 24
    BG_COLOR = (0, 0, 0, 180)

    def render(self, screen: Surface, context: RenderContext) -> None:
        if not context.show_help:
            return

        overlay = pygame.Surface(
            (context.width, context.height),
            pygame.SRCALPHA,
        )
        overlay.fill(self.BG_COLOR)
        screen.blit(overlay, (0, 0))

        line_h = context.assets.wood_font.frames["A"].get_height() + 6

        lines = [
            "FLY-IN HELP",
            "",
            "GOAL: GET ALL DRONES FROM START HUB TO END HUB",
            "THE MAP IS A GRAPH OF ZONES AND CONNECTIONS",
            "",
            "WASD and arrow keys: move camera",
            "SPACE: pause or resume",
            "R: restart",
            "Q: quit",
            "H: toggle help",
            "",
            "POINT THE MOUSE TO A ZONE TO SEE INFO",
        ]

        non_empty_lines = [line for line in lines if line]
        max_text_width = max(
            TextLayer(line, 0, 0, strict=False).get_text_width(context)
            for line in non_empty_lines
        )
        total_text_height = line_h * len(lines)

        center_x = (context.width - max_text_width) // 2
        x = center_x if center_x >= self.PADDING else self.PADDING
        center_y = (context.height - total_text_height) // 2
        y = center_y if center_y >= self.PADDING else self.PADDING

        for line in lines:
            if line == "":
                y += line_h
                continue
            TextLayer(line, x, y, strict=False).render(screen, context)
            y += line_h


class MapLegendLayer(RenderLayer):
    """Wood-tile legend: zone, hubs, obstacle icons, and easter egg."""

    BOARD_SIZE = 3
    ICON_SIZE = 36
    OBJECT_ROW_COUNT = 4

    @staticmethod
    def content_bottom_y(context: RenderContext, legend_y: int) -> int:
        """Y just below legend icons."""
        tile_w = context.assets.wood_tile.width
        return (
            legend_y
            + tile_w
            + MapLegendLayer.OBJECT_ROW_COUNT * (MapLegendLayer.ICON_SIZE + 10)
            + 8
        )

    def __init__(
        self,
        x: int,
        y: int,
    ) -> None:
        """Top-left corner of the legend panel in screen pixels."""
        self.x = x
        self.y = y

    def render(self, screen: Surface, context: RenderContext) -> None:
        """Draw the legend board, labeled icons, and corner decoration."""
        self._render_board(screen, context)
        self._render_objects(screen, context)
        self._draw_amogus(screen, context, (self.x, self.y))

    def _render_board(self, screen: Surface, context: RenderContext) -> None:
        """Tile the wood background and title MAP LEGEND."""
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
        TextLayer(
            "MAP LEGEND",
            self.x + (self.BOARD_SIZE * context.assets.wood_tile.width) // 4,
            self.y,
        ).render(screen, context)

    def _render_objects(self, screen: Surface, context: RenderContext) -> None:
        """Rows of scaled icons with text labels for map symbology."""
        objects: list[tuple[Surface, str]] = [
            (context.assets.island.surface, "ZONE"),
            (
                self.get_current_sprite(
                    current_time=context.current_time,
                    sprite=context.assets.ua_flag,
                ),
                "START HUB",
            ),
            (
                self.get_current_sprite(
                    current_time=context.current_time,
                    sprite=context.assets.campfire,
                ),
                "END HUB",
            ),
            (context.assets.obstacle.surface, "OBSTACLE"),
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

    def _draw_amogus(
        self,
        screen: Surface,
        context: RenderContext,
        coordinates: tuple[int, int],
    ) -> None:
        """Place the small amogus icon on the legend panel."""
        amogus = pygame.transform.scale(
            context.assets.amogus.surface, (self.ICON_SIZE, self.ICON_SIZE)
        )
        screen.blit(
            amogus,
            coordinates,
        )


class ZoneTooltipLayer(RenderLayer):
    """Hover tooltip: zone name, hub type, limits, neighbor capacities."""

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
                x * tile_w + context.layout.offset_x,
                y * tile_w + context.layout.offset_y,
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
        neighbors: set[str] = zone_conn.get("connections", set[Any]())
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
    ) -> tuple[int, int]:
        """Top-left for the tooltip box, offset slightly from the cursor."""
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
        """Draw each *lines* entry with TextLayer inside the padded box."""
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
        bx, by = self._get_box_position(context)

        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg.fill(self.BG_COLOR)
        screen.blit(bg, (bx, by))
        pygame.draw.rect(screen, self.BORDER_COLOR, (bx, by, box_w, box_h), 2)

        self._render_lines(screen, context, lines, bx, by, char_h)
