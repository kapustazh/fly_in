from sprites import Sprite, AnimatedSprite, Font
from drone import DroneSprite
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402


class AssetError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Asset loading error: {detail}")


class AssetManager:
    def __init__(self) -> None:
        self.water: AnimatedSprite
        self.icon: Sprite
        self.island: Sprite
        self.obstacle: Sprite
        self.russia_flag: AnimatedSprite
        self.ua_flag: AnimatedSprite
        self.drone_sprite: DroneSprite
        self.wood_font: Font
        self.wood_tile: Sprite

    def load(self) -> None:
        assets_root = os.path.join(os.path.dirname(__file__), "assets")

        def asset_path(*parts: str) -> str:
            return os.path.join(assets_root, *parts)

        try:
            self.water = AnimatedSprite(
                surface=pygame.image.load(
                    asset_path("sprites", "water.png")
                ).convert_alpha(),
                num_frames=4,
            )
            self.icon = Sprite(
                surface=pygame.image.load(
                    asset_path("sprites", "icon.jpg")
                ).convert_alpha()
            )
            self.island = Sprite(
                surface=pygame.image.load(
                    asset_path("sprites", "grass.png")
                ).convert_alpha(),
            )
            self.obstacle = Sprite(
                surface=pygame.image.load(
                    asset_path("sprites", "obstacle.png")
                ).convert_alpha()
            )
            self.russia_flag = AnimatedSprite(
                surface=pygame.image.load(
                    asset_path("sprites", "flag_russia.png")
                ).convert_alpha(),
                num_frames=5,
            )
            self.ua_flag = AnimatedSprite(
                surface=pygame.image.load(
                    asset_path("sprites", "flag_ua.png")
                ).convert_alpha(),
                num_frames=5,
            )
            self.wood_font = Font(
                surface=pygame.image.load(
                    asset_path("fonts", "WoodFont.png")
                ).convert_alpha(),
            )
            self.wood_tile = Font(
                surface=pygame.image.load(
                    asset_path("sprites", "wood_tile.png")
                ).convert_alpha(),
            )
            self.drone_sprite = DroneSprite(
                surface=pygame.image.load(
                    asset_path("sprites", "drone_sprite.png")
                ).convert_alpha(),
            )
        except FileNotFoundError as e:
            raise AssetError(str(e))

        self._prepare_sprites()

    def _prepare_sprites(self) -> None:
        self.water.prepare_frames(scale=2.0)
        self.russia_flag.prepare_frames(scale=1.5)
        self.ua_flag.prepare_frames(scale=1.5)
        size = self.obstacle.surface
        rescaled = (
            size.get_width() * 1.5,
            size.get_height() * 1.5,
        )
        self.obstacle.surface = pygame.transform.scale(size, rescaled)
        self.island.update_upscaled_surface(48, 48, 16, 16, factor=2.5)
        self.wood_font.prepare_frames()
        self.drone_sprite.prepare_frames(scale=0.1)
        pygame.display.set_icon(self.icon.surface)
