import os
from parser import InputParser, FileReaderError, ParsingError
import argparse
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

# from pprint import pprint

# suppress the pygame startup banner


def main() -> None:
    # parsing
    parser = argparse.ArgumentParser(
        prog="fly-in",
        description=(
            "Parses drone flight zone data and connections from a text file."
        ),
    )
    parser.add_argument(
        "filepath",
        type=str,
        help="Path to the .txt file containing the zone and connection data.",
    )
    args = parser.parse_args()
    my_parser = InputParser()
    try:
        my_parser.parse_lines(args.filepath)
        my_parser.parse_input()

        if not my_parser.get_zones or not my_parser.connections:
            raise ParsingError("No zones or connections provided")
    except (FileReaderError, ParsingError) as e:
        print(e)
        sys.exit(1)

    zones = my_parser.get_zones
    connections = my_parser.connections

    WIDTH = 1280
    HEIGHT = 720
    pygame.init()
    pygame.image.load
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fly-in")
    clock = pygame.time.Clock()
    running = True
    try:
        bg_image = pygame.image.load("bg.png")
        icon_image = pygame.image.load("icon.jpg")
    except FileNotFoundError as e:
        print(e)
        sys.exit()

    pygame.display.set_icon(icon_image)
    bg_image = pygame.transform.scale(bg_image, (WIDTH, HEIGHT))
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False

        screen.blit(bg_image, (0, 0))
        for name, zone in zones.items():
            coords = zone.get("coordinates")
            x, y = coords
            x *= 25
            y *= 25
            pygame.draw.circle(
                screen,
                ("white"),
                (x + WIDTH // 2 - 120, y + HEIGHT // 2),
                radius=5,
            )
        # for name, zone in connections()
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
