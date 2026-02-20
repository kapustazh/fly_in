import argparse
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Union, List, Tuple, Any
import re
from pprint import pprint


class ZoneTypes(str, Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


class AllowedMetadataHubs(str, Enum):
    ZONE = "zone"
    COLOR = "color"
    MAX_DRONES = "max_drones"


class AllowedMetadataConnections(str, Enum):
    MAX_LINK_CAPACITY = "max_link_capacity"


class FileReaderError(Exception):
    def __init__(self, detail: str) -> None:
        message = f"Error occurred while reading: {detail}"
        super().__init__(message)


class InputParser:

    def __init__(self) -> None:
        self.zones: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.raw_connections: List[
            Tuple[Tuple[str, str], Optional[Dict[str, str]]]
        ] = []
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.parsed_lines: list[str] = []
        self.number_of_drones: int = 0

    @property
    def get_zones(self) -> Dict[str, Union[Dict, int]]:
        return dict(self.zones)

    @staticmethod
    def _parse_metadata(
        metadata: str, connections: bool
    ) -> Optional[dict[str, str]]:
        if not metadata:
            return None
        parsed = dict(metadata.split("=") for metadata in metadata.split())
        if connections:
            allowed_keys = {item.value for item in AllowedMetadataConnections}
            positive_int_keys = {"max_link_capacity"}
        else:
            allowed_keys = {item.value for item in AllowedMetadataHubs}
            positive_int_keys = {"max_drones"}
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
                except ValueError:
                    raise ValueError(
                        f"'{key}' must be an integer!. Got '{value}'"
                    )
        return parsed

    def parse_lines(self, name: str) -> None:
        try:
            with open(file=name, mode="r") as f:
                self.parsed_lines = f.readlines()
        except FileNotFoundError:
            print(FileReaderError("File not found"))
            exit(1)

    def parse_input(self) -> None:
        pattern = r"(start_hub|end_hub|hub):\s+(\w+)\s+(-?\d+)\s+(-?\d+)(?:\s*\[([^\]]+)\])?"
        pattern_connection = r"connection:\s+(\w+)-(\w+)(?:\s*\[([^\]]+)\])?"
        try:
            for line in self.parsed_lines:
                if line.startswith("#") or line is None:
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
                                    metadata=metadata, connections=False
                                ),
                            }
                        )
                    else:
                        match = re.match(pattern_connection, line)
                        if match:
                            hub_one, hub_two, metadata = match.groups()
                            if hub_one == hub_two:
                                raise ValueError(
                                    f"Self-connection '{hub_one}-{hub_two}' "
                                    + "is not allowed"
                                )
                            self.raw_connections.append(
                                (
                                    (hub_one, hub_two),
                                    InputParser._parse_metadata(
                                        metadata=metadata, connections=True
                                    ),
                                ),
                            )

            if self.raw_connections:
                self.parse_connections()

        except ValueError as e:
            print("Error accused while parsing:", e)
            exit(1)

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
    # parser = argparse.ArgumentParser(prog="fly-in")
    # parser.parse_args()
    my_parser = InputParser()
    my_parser.parse_lines("test_map.txt")
    my_parser.parse_input()
    # pprint(my_parser.get_zones)
    # pprint(my_parser.number_of_drones)
    # pprint(my_parser.connections)
