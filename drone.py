import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
from sprites import AnimatedSprite


class Drone(AnimatedSprite):
    COLS = 4
    ROWS = 4

    def __init__(self, surface: pygame.Surface) -> None:
        super().__init__(surface, num_frames=self.COLS * self.ROWS)

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
