"""Lightweight pygame wrappers: static sprites, filmstrips, and bitmap fonts."""

import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
from pygame.surface import Surface  # noqa E402
import pygame  # noqa E402


class Sprite:
    """Single image with cached width and height."""

    def __init__(self, surface: Surface) -> None:
        self.surface: Surface = surface
        self.width: int = surface.get_width()
        self.height: int = surface.get_height()

    def get_upscaled_from_mask(
        self, x: int, y: int, w: int, h: int, factor: float
    ) -> None:
        """Replace the surface with a scaled crop (x, y, w, h) × *factor*."""
        tile = self.surface.subsurface(pygame.Rect(x, y, w, h))
        new_size = (w * factor, h * factor)
        self.surface = pygame.transform.scale(tile, new_size)
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()

    def upscale(self, scale: float) -> None:
        """Uniform scale of the whole surface; updates width and height."""
        self.surface = pygame.transform.scale(
            self.surface, (self.width * scale, self.height * scale)
        )
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()


class AnimatedSprite(Sprite):
    """Horizontal filmstrip: *num_frames* equal slices become frames."""

    def __init__(self, surface: Surface, num_frames: int) -> None:
        super().__init__(surface)
        self.num_frames: int = num_frames
        self.frames: list[Surface] = []

    def prepare_frames(self, scale: float = 1.0) -> None:
        """Slice the strip into frames and optionally scale each cell."""
        width = self.width // self.num_frames
        for i in range(self.num_frames):
            rect = pygame.Rect(i * width, 0, width, self.height)
            frame = self.surface.subsurface(rect)
            new_size = (
                frame.get_width() * scale,
                frame.get_height() * scale,
            )
            frame = pygame.transform.scale(frame, new_size)
            self.frames.append(frame)


class Font(Sprite):
    """Glyph atlas: CHAR_SEQUENCE order matches rows×columns in the image."""

    # characters are laid out left‑to‑right, top‑to‑bottom in the image
    CHAR_SEQUENCE: tuple[str, ...] = tuple(
        "ABCDEFGHIJKL"
        "MNOPQRSTUVWX"
        "YZ1234567890"
        "abcdefghijkl"
        "mnopqrstuvwx"
        "yz:"
    )

    def __init__(self, surface: Surface):
        """Create an empty glyph map; call prepare_frames before drawing text."""
        super().__init__(surface)
        self.frames: dict[str, Surface] = {}

    def prepare_frames(self, scale: float = 1) -> None:
        """Fill frames with one subsurface per character in CHAR_SEQUENCE."""
        columns = 12
        rows = 6
        cell_width = self.width // columns
        cell_height = self.height // rows

        char_index = 0
        for row in range(rows):
            for col in range(columns):
                if char_index >= len(self.CHAR_SEQUENCE):
                    break
                char = self.CHAR_SEQUENCE[char_index]
                rect = pygame.Rect(
                    col * cell_width,
                    row * cell_height,
                    cell_width,
                    cell_height,
                )
                frame = self.surface.subsurface(rect)
                new_size = (
                    int(frame.get_width() * scale),
                    int(frame.get_height() * scale),
                )
                frame = pygame.transform.scale(frame, new_size)
                self.frames[char] = frame
                char_index += 1
