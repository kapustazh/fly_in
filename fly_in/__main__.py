"""Package entrypoint for `python -m fly_in`."""

from .render import InformationManager


def main() -> None:
    """Run the Fly-in CLI application."""
    InformationManager().run()


if __name__ == "__main__":
    main()
