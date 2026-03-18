from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Literal, Protocol
from pygame.surface import Surface
from sprites import AnimatedSprite
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402


class DroneSprite(AnimatedSprite):
    COLS = 4
    ROWS = 4

    def __init__(self, surface: Surface) -> None:
        super().__init__(surface, num_frames=self.COLS * self.ROWS)
        self.orientation_status = "idle"
        self.frames_right_down: list[Surface] = []
        self.frames_left_down: list[Surface] = []
        self.frames_right_up: list[Surface] = []
        self.frames_left_up: list[Surface] = []

    def prepare_frames(self, scale: float = 1.0) -> None:
        frame_w = self.width // self.COLS
        frame_h = self.height // self.ROWS
        self.frames = []
        for row in range(self.ROWS):
            for col in range(self.COLS):
                sub = self.surface.subsurface(
                    pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
                )
                new_size = (
                    int(sub.get_width() * scale),
                    int(sub.get_height() * scale),
                )
                frame = pygame.transform.scale(sub, new_size)
                self.frames.append(frame)
        self.frames_right = self.frames[8:12]
        self.frames_left = self.frames[12:16]
        self.frames_right_up = [
            pygame.transform.rotate(frame, 90) for frame in self.frames_right
        ]
        self.frames_left_up = [
            pygame.transform.rotate(frame, 90) for frame in self.frames_left
        ]

    def get_drone_frame(
        self, current_time: int, animation: int = 150
    ) -> Surface:
        frames = (
            self.frames_right
            if self.orientation_status == "right"
            else self.frames_left
        )
        if self.orientation_status == "idle":
            frames = self.frames
        return frames[(current_time // animation) % len(frames)]

    def turn_left(self) -> None:
        self.orientation_status = "left"

    def turn_right(self) -> None:
        self.orientation_status = "right"

    def wait_idle(self) -> None:
        self.orientation_status = "idle"


class Drone:
    def __init__(
        self,
        current_zone: str,
        pixel_position: tuple[float, float],
    ) -> None:
        self.current_zone = current_zone
        self.path: list[tuple[float, float]] = []
        self.pixel_position = pixel_position
