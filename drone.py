from __future__ import annotations
from pygame.surface import Surface
from sprites import AnimatedSprite
from math import hypot
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
        self.frames_right_down = self.frames[8:12]
        self.frames_left_down = self.frames[12:16]
        self.frames_right_up = [
            pygame.transform.rotate(frame, 165)
            for frame in self.frames_right_down
        ]
        self.frames_left_up = [
            pygame.transform.rotate(frame, 255)
            for frame in self.frames_left_down
        ]

    def get_drone_frame(
        self, current_time: int, animation: int = 150
    ) -> Surface:
        frames_by_orientation: dict[str, list[Surface]] = {
            "right": self.frames_right_down,
            "left": self.frames_left_down,
            "right_down": self.frames_right_down,
            "left_down": self.frames_left_down,
            "right_up": self.frames_right_up,
            "left_up": self.frames_left_up,
            "idle": self.frames,
        }
        frames = frames_by_orientation.get(
            self.orientation_status,
            self.frames,
        )
        return frames[(current_time // animation) % len(frames)]

    def turn_left(self) -> None:
        self.orientation_status = "left_down"

    def turn_right(self) -> None:
        self.orientation_status = "right_down"

    def wait_idle(self) -> None:
        self.orientation_status = "idle"

    def turn_left_up(self) -> None:
        self.orientation_status = "left_up"

    def turn_right_up(self) -> None:
        self.orientation_status = "right_up"

    def turn_left_down(self) -> None:
        self.orientation_status = "left_down"

    def turn_right_down(self) -> None:
        self.orientation_status = "right_down"

    def set_orientation_from_delta(
        self,
        dx: float,
        dy: float,
        dead_zone: float = 0.01,
    ) -> None:
        """Pick one of 4 directional animations from movement vector."""
        if abs(dx) < dead_zone and abs(dy) < dead_zone:
            self.wait_idle()
            return

        if dy < 0:
            if dx >= 0:
                self.turn_right_up()
            else:
                self.turn_left_up()
            return

        if dx >= 0:
            self.turn_right_down()
        else:
            self.turn_left_down()


class Drone:
    def __init__(
        self,
        current_zone: str,
        pixel_position: tuple[float, float],
    ) -> None:
        self.current_zone = current_zone
        self.path: list[tuple[float, float]] = []
        self.pixel_position = pixel_position

    def move_towards(
        self,
        target_position: tuple[float, float],
        speed_px_per_sec: float,
        delta_seconds: float,
    ) -> bool:
        """Move toward a target position
        and return True if reached the goal.
        """
        current_x, current_y = self.pixel_position
        target_x, target_y = target_position

        dx = target_x - current_x
        dy = target_y - current_y
        distance = hypot(dx, dy)

        if distance == 0.0:
            return True

        step = speed_px_per_sec * delta_seconds
        if step >= distance:
            self.pixel_position = (target_x, target_y)
            return True

        ratio = step / distance
        self.pixel_position = (
            current_x + dx * ratio,
            current_y + dy * ratio,
        )
        return False


# hell yea, back to the armada
class DroneArmada:
    def __init__(self, context: RenderContext) -> None:
        self.context = context
        self.drones: list[Drone]

    def create_drone(self, start_zone_name: str = "start") -> Drone:
        pixel_position = self.context.zones_pixel_pos.get(start_zone_name)
        if pixel_position is None:
            raise ValueError(f"No pixel position for zone '{start_zone_name}'")

        drone = Drone(
            current_zone=start_zone_name,
            pixel_position=pixel_position,
        )
        return drone

    def create_an_armada(self, count: int) -> None:
        self.drones = [self.create_drone() for _ in range(count)]
