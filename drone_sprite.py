"""Drone 4×4 atlas: slice banks, pick frame by path, rotate for velocity."""

from __future__ import annotations

import math
import os
from math import hypot

from pygame.surface import Surface

from sprites import AnimatedSprite

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402


class DroneSprite(AnimatedSprite):
    COLS = ROWS = 4
    _NATIVE_RIGHT_DOWN = -45.0
    _NATIVE_LEFT_DOWN = -135.0
    HEADING_OFFSET_DEG = 0.0
    PYGAME_ROTATE_SIGN = 1.0

    @staticmethod
    def _norm_deg180(deg: float) -> float:
        """Map *deg* to (-180, 180] so rotation deltas stay on the short arc.

        Collapses -180 and +180 to a single representation (180).
        """
        x = (deg + 180.0) % 360.0 - 180.0
        return 180.0 if x == -180.0 else x

    @staticmethod
    def _angular_distance_deg(a: float, b: float) -> float:
        """Smallest absolute difference between two headings in degrees."""
        return abs(DroneSprite._norm_deg180(a - b))

    @staticmethod
    def screen_heading_deg(dx: float, dy: float) -> float:
        """Heading of screen-space motion in degrees CCW from +x.

        Uses ``atan2(-dy, dx)`` so +y down (Pygame) matches
        ``pygame.transform.rotate`` convention.
        """
        return math.degrees(math.atan2(-dy, dx))

    @staticmethod
    def bank_key_for_velocity(
        dx: float, dy: float, dead_zone: float = 1.5
    ) -> str:
        """Pick bank: idle, right_down (row 2), or left_down.

        Below *dead_zone* → ``idle``. Else nearest native nose (-45° vs -135°);
        ties use *dx* sign.
        """
        if hypot(dx, dy) < dead_zone:
            return "idle"
        h = DroneSprite.screen_heading_deg(dx, dy)
        d_rd = DroneSprite._angular_distance_deg(
            h, DroneSprite._NATIVE_RIGHT_DOWN
        )
        d_ld = DroneSprite._angular_distance_deg(
            h, DroneSprite._NATIVE_LEFT_DOWN
        )
        if d_rd < d_ld:
            return "right_down"
        if d_ld < d_rd:
            return "left_down"
        return "right_down" if dx >= 0.0 else "left_down"

    def __init__(self, surface: Surface) -> None:
        """Load a 4×4 atlas; frame banks are filled in ``prepare_frames``."""
        super().__init__(surface, num_frames=self.COLS * self.ROWS)
        self.frames_right_down: list[Surface] = []
        self.frames_left_down: list[Surface] = []

    def prepare_frames(self, scale: float = 1.0) -> None:
        """Slice atlas into 16 cells, scale, split left/right banks."""
        fw = self.width // self.COLS
        fh = self.height // self.ROWS
        self.frames = []
        for row in range(self.ROWS):
            for col in range(self.COLS):
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
        """Surface for path direction (*dx*, *dy*); animates by *current_time*.

        Idle cycles the left bank; moving picks a bank, then rotates the cel
        so the drone nose matches ``screen_heading_deg(dx, dy)``.
        """
        if not self.frames_left_down:
            n = max(1, len(self.frames))
            return self.frames[(current_time // animation) % n]

        tick = current_time // animation
        key = DroneSprite.bank_key_for_velocity(dx, dy, dead_zone)
        if key == "idle":
            bank = self.frames_left_down
            return bank[tick % len(bank)]

        if key == "right_down":
            bank, native = self.frames_right_down, self._NATIVE_RIGHT_DOWN
        else:
            bank, native = self.frames_left_down, self._NATIVE_LEFT_DOWN

        base = bank[tick % len(bank)]
        angle = DroneSprite._norm_deg180(
            DroneSprite.screen_heading_deg(dx, dy)
            - native
            + self.HEADING_OFFSET_DEG
        )
        return pygame.transform.rotate(
            base, angle * self.PYGAME_ROTATE_SIGN
        )
