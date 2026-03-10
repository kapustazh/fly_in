from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Protocol
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
        self.frames_right: list[Surface] = []
        self.frames_left: list[Surface] = []

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


class SupportsDroneSprite(Protocol):
    drone_sprite: DroneSprite


class Drone:
    def __init__(
        self,
        sprite: DroneSprite,
        current_zone: str,
        pixel_position: tuple[float, float],
    ) -> None:
        self.sprite = sprite
        self.current_zone = current_zone
        self.path: list[tuple[float, float]] = []
        self.pixel_position = pixel_position

    def update(self, animation: float) -> None:
        """Update hook for future movement/pathfinding logic."""
        _ = animation
        if not self.path:
            self.sprite.wait_idle()
            return
        self.sprite.wait_idle()


class DronesArmada:
    def __init__(
        self,
        num_drones: int,
        assets: SupportsDroneSprite,
        zones: Mapping[str, dict[str, Any]],
        tile_size: float,
    ) -> None:
        self.drones: list[Drone] = []
        self.num_drones = num_drones
        self._assets = assets
        self._spawn_on_start_hubs(zones=zones, tile_size=tile_size)

    def _spawn_on_start_hubs(
        self,
        zones: Mapping[str, dict[str, Any]],
        tile_size: float,
    ) -> None:
        start_hubs = [
            (name, zone)
            for name, zone in zones.items()
            if zone.get("hub_type") == "start_hub"
        ]
        if not start_hubs:
            return

        for i in range(self.num_drones):
            start_name, start_zone = start_hubs[i % len(start_hubs)]
            x, y = start_zone["coordinates"]
            drone = Drone(
                sprite=self._assets.drone_sprite,
                current_zone=start_name,
                pixel_position=(float(x) * tile_size, float(y) * tile_size),
            )
            self.drones.append(drone)

    def add_drone(self, drone: Drone) -> None:
        self.drones.append(drone)

    def update(self, animation: float) -> None:
        for drone in self.drones:
            drone.update(animation)
