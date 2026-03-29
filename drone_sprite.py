"""One big drone image is cut into a 4x4 grid.

We pick a piece and turn it so the drone faces the way it moves.
"""

from __future__ import annotations

import math
import os
from math import hypot

from pygame.surface import Surface

from sprites import AnimatedSprite

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402


class DroneSprite(AnimatedSprite):
    """Drone sprites come from a 4x4 sheet."""

    COLS = ROWS = 4
    NATIVE_RIGHT_DOWN_DEG = 315.0  # 4 чверть
    NATIVE_LEFT_DOWN_DEG = 225.0  # 3 чверть
    HEADING_OFFSET_DEG = 0.0
    PYGAME_ROTATE_SIGN = 1.0

    def __init__(self, surface: Surface) -> None:
        super().__init__(surface, num_frames=self.COLS * self.ROWS)
        self.frames_right_down: list[Surface] = []
        self.frames_left_down: list[Surface] = []

    @staticmethod
    def _norm_deg180(deg: float) -> float:
        """Normalize angle to -180 to 180 degrees."""
        x = (deg + 180.0) % 360.0 - 180.0
        return 180.0 if x == -180.0 else x

    @staticmethod
    def _angular_distance_deg(a: float, b: float) -> float:
        """Smallest angle between two angles in degrees."""
        return abs(DroneSprite._norm_deg180(a - b))

    @staticmethod
    def screen_heading_deg(dx: float, dy: float) -> float:
        """Movement direction in degrees, always in [0, 360]
        0 = right,
        90 = up on the screen,
        180 = left,
        270 = down
        """
        deg = math.degrees(math.atan2(-dy, dx))
        return (deg % 360.0 + 360.0) % 360.0

    @staticmethod
    def bank_key_from_heading(h: float, dx: float) -> str:
        """right_down vs left_down by which native angle
        is closer to h (0 to 360)"""
        d_rd = DroneSprite._angular_distance_deg(
            h, DroneSprite.NATIVE_RIGHT_DOWN_DEG
        )
        d_ld = DroneSprite._angular_distance_deg(
            h, DroneSprite.NATIVE_LEFT_DOWN_DEG
        )
        if d_rd < d_ld:
            return "right_down"
        if d_ld < d_rd:
            return "left_down"
        return "right_down" if dx >= 0.0 else "left_down"

    @staticmethod
    def bank_key_for_velocity(
        dx: float, dy: float, dead_zone: float = 1.5
    ) -> str:
        """idle, or which bank is closest to motion (
        convenience; calls screen_heading once)."""
        if hypot(dx, dy) < dead_zone:
            return "idle"
        h = DroneSprite.screen_heading_deg(dx, dy)
        return DroneSprite.bank_key_from_heading(h, dx)

    def prepare_frames(self, scale: float = 1.0) -> None:
        """Cut the sheet into 16 squares and resize them."""
        fw = self.width // self.COLS
        fh = self.height // self.ROWS
        self.frames = []
        for row in range(self.ROWS):
            for col in range(self.COLS):
                sub = self.surface.subsurface(
                    pygame.Rect(col * fw, row * fh, fw, fh)
                )
                w = int(sub.get_width() * scale)
                h = int(sub.get_height() * scale)
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
        """Return the image for movement (dx, dy);
        time picks the animation frame.

        Idle loops the left bank with no rotation. Moving picks the closer bank
        then rotates from that bank's native heading toward screen_heading_deg
        (0 to 360).
        """
        tick = current_time // animation
        if hypot(dx, dy) < dead_zone:
            bank = self.frames_left_down
            return bank[tick % len(bank)]

        h = DroneSprite.screen_heading_deg(dx, dy)
        key = DroneSprite.bank_key_from_heading(h, dx)
        if key == "right_down":
            bank, native = self.frames_right_down, self.NATIVE_RIGHT_DOWN_DEG
        else:
            bank, native = self.frames_left_down, self.NATIVE_LEFT_DOWN_DEG

        base = bank[tick % len(bank)]
        angle = DroneSprite._norm_deg180(h - native + self.HEADING_OFFSET_DEG)
        return pygame.transform.rotate(base, angle * self.PYGAME_ROTATE_SIGN)
