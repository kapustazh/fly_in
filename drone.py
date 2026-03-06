from __future__ import annotations
from sprites import AnimatedSprite
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402


class DroneSprite(AnimatedSprite):
    COLS = 4
    ROWS = 4

    def __init__(self, surface: pygame.Surface) -> None:
        super().__init__(surface, num_frames=self.COLS * self.ROWS)
        self.orientation_status = "idle"
        self.frames_right: list[pygame.Surface] = []
        self.frames_left: list[pygame.Surface] = []

    def prepare_frames(self, scale: float = 1.0) -> None:
        frame_w = self.width // self.COLS
        frame_h = self.height // self.ROWS
        self.frames = [
            pygame.transform.scale_by(
                self.surface.subsurface(
                    pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
                ),
                scale,
            )
            for row in range(self.ROWS)
            for col in range(self.COLS)
        ]
        self.frames_right = self.frames[8:12]
        self.frames_left = self.frames[12:16]

    def get_drone_frame(
        self, current_time: int, animation: int = 150
    ) -> pygame.Surface:
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
    def __init__(self):
        self.sprite = DroneSprite()


class DronesArmada:
    def __init__(self, num_drones: int) -> None:
        self.drones: list[Drone] = []
        self.num_drones: int = num_drones

    def add_drone(self, drone: Drone) -> None:
        self.drones.append(drone)
