from fly_in.render import InformationManager
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

if __name__ == "__main__":
    InformationManager().run()
