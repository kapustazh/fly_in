from sprites import Sprite, AnimatedSprite, Font
from drone_sprite import DroneSprite
from pathlib import Path
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
from pygame.surface import Surface  # noqa: E402
import pygame  # noqa: E402


class AssetError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Asset loading error: {detail}")


# Added pathlib instead of the old os.path.join why not
class AssetManager:
    def __init__(self) -> None:
        self.water: AnimatedSprite
        self.icon: Sprite
        self.island: Sprite
        self.obstacle: Sprite
        self.campfire: AnimatedSprite
        self.ua_flag: AnimatedSprite
        self.drone_sprite: DroneSprite
        self.wood_font: Font
        self.wood_tile: Sprite
        self.amogus: Sprite

    def load(self) -> None:
        assets_root = Path(__file__).parent / "assets"

        def load_image(*parts: str) -> Surface:
            return pygame.image.load(
                assets_root.joinpath(*parts)
            ).convert_alpha()

        try:
            self.water = AnimatedSprite(
                surface=load_image("sprites", "water.png"),
                num_frames=4,
            )
            self.icon = Sprite(surface=load_image("sprites", "icon.jpg"))
            self.island = Sprite(surface=load_image("sprites", "grass.png"))
            self.obstacle = Sprite(
                surface=load_image("sprites", "obstacle.png")
            )
            self.campfire = AnimatedSprite(
                surface=load_image("sprites", "campfire.png"),
                num_frames=6,
            )
            self.ua_flag = AnimatedSprite(
                surface=load_image("sprites", "flag_ua.png"),
                num_frames=5,
            )
            self.wood_font = Font(surface=load_image("fonts", "WoodFont.png"))
            self.wood_tile = Font(
                surface=load_image("sprites", "birch-plank.png")
            )
            self.drone_sprite = DroneSprite(
                surface=load_image("sprites", "drone_sprite.png"),
            )
            self.amogus = Sprite(surface=load_image("sprites", "amogus.png"))
        except FileNotFoundError as e:
            raise AssetError(str(e))

        self._prepare_sprites()

    def _prepare_sprites(self) -> None:
        self.water.prepare_frames(scale=2.0)
        self.campfire.prepare_frames(scale=1.4)
        self.ua_flag.prepare_frames(scale=1.5)
        self.obstacle.upscale(scale=1.5)
        self.island.get_upscaled_from_mask(48, 48, 16, 16, factor=2.5)
        self.wood_font.prepare_frames()
        self.drone_sprite.prepare_frames(scale=0.082)
        self.wood_tile.upscale(scale=0.3)
        self.amogus.upscale(scale=0.3)
        pygame.display.set_icon(self.icon.surface)
