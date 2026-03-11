import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa E402


class Sprite:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface: pygame.Surface = surface
        self.width: int = surface.get_width()
        self.height: int = surface.get_height()

    def get_upscaled_from_mask(
        self, x: int, y: int, w: int, h: int, factor: float
    ) -> None:
        tile = self.surface.subsurface(pygame.Rect(x, y, w, h))
        new_size = (w * factor, h * factor)
        self.surface = pygame.transform.scale(tile, new_size)
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()

    def upscale(self, scale: float) -> None:
        self.surface = pygame.transform.scale(
            self.surface, (self.width * scale, self.height * scale)
        )
        self.width = self.surface.get_width()
        self.height = self.surface.get_height()


class AnimatedSprite(Sprite):
    def __init__(self, surface: pygame.Surface, num_frames: int) -> None:
        super().__init__(surface)
        self.num_frames: int = num_frames
        self.frames: list[pygame.Surface] = []

    def prepare_frames(self, scale: float = 1.0) -> None:
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
    # characters are laid out left‑to‑right, top‑to‑bottom in the image
    CHAR_SEQUENCE: tuple[str, ...] = tuple(
        "ABCDEFGHIJKL"
        "MNOPQRSTUVWX"
        "YZ1234567890"
        "abcdefghijkl"
        "mnopqrstuvwx"
        "yz:"
    )
    # immutable membership set used elsewhere for sanitization
    SUPPORTED_CHARS: frozenset[str] = frozenset(CHAR_SEQUENCE)

    def __init__(self, surface: pygame.Surface):
        super().__init__(surface)
        self.frames: dict[str, pygame.Surface] = {}

    def prepare_frames(self, scale: float = 1) -> None:
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
