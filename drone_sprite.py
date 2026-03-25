"""Drone 4×4 atlas: slice banks, pick frame by path direction, rotate to match velocity."""

from __future__ import annotations

import math
import os
from math import hypot

from pygame.surface import Surface

from sprites import AnimatedSprite

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

COLS = ROWS = 4
_ATLAS_CELLS = COLS * ROWS

# Rows 0–1 and 3: nose bottom-left (~-135°). Row 2: nose bottom-right (~-45°).
# Degrees CCW from +x, pygame convention (+y down): ``degrees(atan2(-dy, dx))``.
_NATIVE_RIGHT_DOWN = -45.0
_NATIVE_LEFT_DOWN = -135.0

# Optional tweaks if art drifts vs velocity.
HEADING_OFFSET_DEG = 0.0
PYGAME_ROTATE_SIGN = 1.0


def _norm_deg180(deg: float) -> float:
    x = (deg + 180.0) % 360.0 - 180.0
    return 180.0 if x == -180.0 else x


def _angular_distance_deg(a: float, b: float) -> float:
    return abs(_norm_deg180(a - b))


def screen_heading_deg(dx: float, dy: float) -> float:
    """Motion direction in degrees CCW from +x (matches ``pygame.transform.rotate``)."""
    return math.degrees(math.atan2(-dy, dx))


def bank_key_for_velocity(
    dx: float, dy: float, dead_zone: float = 1.5
) -> str:
    """``idle`` | ``right_down`` (atlas row 2) | ``left_down`` (rows 0–1 + 3)."""
    if hypot(dx, dy) < dead_zone:
        return "idle"
    h = screen_heading_deg(dx, dy)
    d_rd = _angular_distance_deg(h, _NATIVE_RIGHT_DOWN)
    d_ld = _angular_distance_deg(h, _NATIVE_LEFT_DOWN)
    if d_rd < d_ld:
        return "right_down"
    if d_ld < d_rd:
        return "left_down"
    return "right_down" if dx >= 0.0 else "left_down"


class DroneSprite(AnimatedSprite):
    def __init__(self, surface: Surface) -> None:
        super().__init__(surface, num_frames=_ATLAS_CELLS)
        self.frames_right_down: list[Surface] = []
        self.frames_left_down: list[Surface] = []

    def prepare_frames(self, scale: float = 1.0) -> None:
        fw = self.width // COLS
        fh = self.height // ROWS
        self.frames = []
        for row in range(ROWS):
            for col in range(COLS):
                sub = self.surface.subsurface(
                    pygame.Rect(col * fw, row * fh, fw, fh)
                )
                w = max(1, int(sub.get_width() * scale))
                h = max(1, int(sub.get_height() * scale))
                self.frames.append(pygame.transform.scale(sub, (w, h)))
        self.frames_right_down = self.frames[8:12]
        self.frames_left_down = self.frames[0:8] + self.frames[12:16]

    def frame_for_vector(
        self,
        dx: float,
        dy: float,
        current_time: int,
        animation: int = 150,
        dead_zone: float = 1.5,
    ) -> Surface:
        if not self.frames_left_down:
            n = max(1, len(self.frames))
            return self.frames[(current_time // animation) % n]

        tick = current_time // animation
        key = bank_key_for_velocity(dx, dy, dead_zone)
        if key == "idle":
            bank = self.frames_left_down
            return bank[tick % len(bank)]

        if key == "right_down":
            bank, native = self.frames_right_down, _NATIVE_RIGHT_DOWN
        else:
            bank, native = self.frames_left_down, _NATIVE_LEFT_DOWN

        base = bank[tick % len(bank)]
        angle = _norm_deg180(
            screen_heading_deg(dx, dy) - native + HEADING_OFFSET_DEG
        )
        return pygame.transform.rotate(base, angle * PYGAME_ROTATE_SIGN)
