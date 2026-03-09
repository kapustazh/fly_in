import os
from .parser import FileReaderError, InputParser, ParsingError

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


__all__ = ["InputParser", "FileReaderError", "ParsingError"]
__version__ = 42.1
__author__ = "matvii"
