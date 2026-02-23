import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Union, List, Tuple, Any
import re
from pprint import pprint
import math
from enum import Enum

# Python 3.11 added StrEnum, but mypy/stubs in some environments
# don't know about it.  Define a small back‑compat shim so that
# the rest of the code can subclass StrEnum and remain typed.
# This avoids the `module "enum" has no attribute "StrEnum"`
# and related subclass errors.


class StrEnum(str, Enum):
    """Simple ``str``/``Enum`` hybrid for versions without stdlib support.

    The stdlib version inherits from ``str`` and ``Enum`` in the
    opposite order, but for our use cases the behaviour is identical.
    """

    pass


class ZoneTypes(StrEnum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def cost(self) -> float:
        """Returns the movement cost for the zone."""
        cost_map = {
            ZoneTypes.NORMAL: 1.0,
            ZoneTypes.RESTRICTED: 2.0,
            ZoneTypes.PRIORITY: 1.0,
            ZoneTypes.BLOCKED: math.inf,
        }
        return cost_map[self]

    @property
    def is_passable(self) -> bool:
        return self != ZoneTypes.BLOCKED

    @property
    def is_priority(self) -> bool:
        return self == ZoneTypes.PRIORITY


class AllowedMetadataHubs(StrEnum):
    ZONE = "zone"
    COLOR = "color"
    MAX_DRONES = "max_drones"


class AllowedMetadataConnections(StrEnum):
    MAX_LINK_CAPACITY = "max_link_capacity"


@dataclass
class ZoneMetadata:
    color: str | None = None
    zone: str = ZoneTypes.NORMAL
    max_drones: int = 1


@dataclass
class ConnectionMetadata:
    max_link_capacity: int = 1


MetadataType = ZoneMetadata | ConnectionMetadata


class FileReaderError(Exception):
    def __init__(self, detail: str) -> None:
        message = f"Error occurred while reading: {detail}"
        super().__init__(message)


class ParsingError(Exception):
    def __init__(self, detail: str) -> None:
        message = f"Error occurred while parsing: {detail}"
        super().__init__(message)


class InputParser:

    def __init__(self) -> None:
        self.zones: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.raw_connections: List[Tuple[Tuple[str, str], MetadataType]] = []
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.parsed_lines: list[str] = []
        self.number_of_drones: int = 0

    @property
    def get_zones(self) -> Dict[str, Union[Dict[str, Any], int]]:
        return dict(self.zones)

    @staticmethod
    def _parse_metadata(
        metadata: str, is_connection: bool
    ) -> ZoneMetadata | ConnectionMetadata:
        if not metadata:
            return ConnectionMetadata() if is_connection else ZoneMetadata()

        parsed = dict(metadata.split("=") for metadata in metadata.split())

        if is_connection:
            allowed_keys = {item.value for item in AllowedMetadataConnections}
            positive_int_keys = {"max_link_capacity"}
        else:
            allowed_keys = {item.value for item in AllowedMetadataHubs}
            positive_int_keys = {"max_drones"}

        parsed_clean: dict[str, Any] = {}

        for key, value in parsed.items():
            if key not in allowed_keys:
                raise ValueError(
                    f"Invalid '{key}', allowed are {allowed_keys}"
                )
            if key in positive_int_keys:
                try:
                    val = int(value)
                    if val <= 0:
                        raise ValueError(f"'{key}' must be positive!")
                    parsed_clean[key] = val
                except ValueError:
                    raise ValueError(
                        f"'{key}' must be an integer! Got '{value}'"
                    )
            elif key == "zone":
                parsed_clean[key] = ZoneTypes(value)
            else:
                parsed_clean[key] = value

        if is_connection:
            return ConnectionMetadata(**parsed_clean)
        else:
            return ZoneMetadata(**parsed_clean)

    def parse_lines(self, name: str) -> None:
        try:
            with open(file=name, mode="r") as f:
                self.parsed_lines = f.readlines()
        except FileNotFoundError:
            raise FileReaderError("File not found")

    def parse_input(self) -> None:
        pattern = (
            r"(start_hub|end_hub|hub):\s+"
            r"(\w+)\s+(-?\d+)\s+(-?\d+)"
            r"(?:\s*\[([^\]]+)\])?"
        )
        pattern_connection = r"connection:\s+(\w+)-(\w+)(?:\s*\[([^\]]+)\])?"
        try:
            seen_connections: set[frozenset[str]] = set()
            for line in self.parsed_lines:
                if not line.strip() or line.startswith("#"):
                    continue
                if line.startswith("nb_drones:"):
                    self.number_of_drones = int(line.split(":")[1].strip())
                    if self.number_of_drones < 0:
                        raise ValueError(
                            "Number of drones can not be negative "
                            + f"{self.number_of_drones}"
                        )
                else:
                    match = re.match(pattern, line)
                    if match:
                        hub_type, name, x, y, metadata = match.groups()
                        self.zones[name].update(
                            {
                                "hub_type": hub_type,
                                "coordinates": (int(x), int(y)),
                                "metadata": InputParser._parse_metadata(
                                    metadata=metadata, is_connection=False
                                ),
                            }
                        )
                    else:
                        match = re.match(pattern_connection, line)
                        if match:
                            hub_one, hub_two, metadata = match.groups()
                            pair_key = frozenset({hub_one, hub_two})
                            if hub_one == hub_two:
                                raise ValueError(
                                    f"Self connection '{hub_one}-{hub_two}' "
                                    + "is forbidden"
                                )
                            if pair_key in seen_connections:
                                raise ValueError(
                                    "Duplicate connection "
                                    + f"'{hub_one}-{hub_two}' found"
                                )
                            seen_connections.add(pair_key)
                            self.raw_connections.append(
                                (
                                    (hub_one, hub_two),
                                    InputParser._parse_metadata(
                                        metadata=metadata, is_connection=True
                                    ),
                                ),
                            )
            if self.raw_connections:
                self.parse_connections()

        except ValueError as err:
            raise ParsingError(str(err))

    def parse_connections(self) -> None:
        for (hub_one, hub_two), meta in self.raw_connections:
            if hub_one not in self.connections:
                self.connections[hub_one] = {
                    "connections": set(),
                    "metadata": {},
                }
            if hub_two not in self.connections:
                self.connections[hub_two] = {
                    "connections": set(),
                    "metadata": {},
                }

            self.connections[hub_one]["connections"].add(hub_two)
            self.connections[hub_one]["metadata"][hub_two] = meta

            self.connections[hub_two]["connections"].add(hub_one)
            self.connections[hub_two]["metadata"][hub_one] = meta


if __name__ == "__main__":
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
    except FileReaderError as e:
        print(e)
        sys.exit(1)
    try:
        my_parser.parse_input()
    except ParsingError as e:
        print(e)
        sys.exit(1)
    pprint(my_parser.get_zones)
    pprint(my_parser.number_of_drones)
    pprint(my_parser.connections)
