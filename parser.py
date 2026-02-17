import argparse
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re
from pprint import pprint


class FileReaderError(Exception):
    def __init__(self, detail: str = "") -> None:
        # Combine the prefix and the specific error detail into one string
        message = f"Error occurred while reading: {detail}"
        super().__init__(message)


class ZoneTypes(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass
class Metadata:
    zone_type: Optional[str] = None
    color: Optional[str] = None
    max_drones: Optional[int] = None


@dataclass
class Input:
    nb_drones: int
    start_hub: tuple[[int, int], Metadata]
    end_hub: tuple[tuple[int, int], Metadata]
    hubs: dict[str, tuple[tuple[int, int], Metadata]]


class FileReader:

    @classmethod
    def parseinput(cls, name: str) -> Input:
        try:
            with open(file=name, mode="r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(FileReaderError("File not found"))
            exit(1)

        results = defaultdict()
        new_hub = defaultdict(dict)
        # The Regex pattern for the hub lines
        pattern = r"(\w+)\s+(\d+)\s+(\d+)\s+\[(\w+)=(\w+)\]"
        try:
            for line in lines:
                if line.startswith("#") or line is None:
                    continue
                if line.startswith("nb_drones:"):
                    results["nb_drones"] = int(line[len("nb_drones: ") :])
                if line.startswith("start_hub:") or line.startswith(
                    "end_hub:"
                ):
                    key = (
                        "start_hub"
                        if line.startswith("start_hub:")
                        else "end_hub"
                    )

                    match = re.search(pattern, line)
                    if match:
                        _, x, y, type_of_metadata, metadata_val = (
                            match.groups()
                        )
                        results[f"{key}_coordinates"] = (int(x), int(y))
                        results[f"{key}_type"] = type_of_metadata
                        if (
                            not type_of_metadata
                            or type_of_metadata not in Metadata.__annotations__
                        ):
                            raise FileReaderError("No type_of_metadata found")
                        results[f"{key}_metadata"] = metadata_val
                if line.startswith("hub: "):
                    match = re.search(pattern, line)
                    if match:
                        hub_name, x, y, type_of_metadata, metadata_val = (
                            match.groups()
                        )
                        if (
                            not type_of_metadata
                            or type_of_metadata not in Metadata.__annotations__
                        ):
                            raise FileReaderError("No type_of_metadata found")
                        new_hub[hub_name].update(
                            {
                                "coordinates": (int(x), int(y)),
                                "type": type_of_metadata,
                                "metadata": metadata_val,
                            }
                        )
            return Input(
                nb_drones=results["nb_drones"],
                start_hub=(
                    results["start_hub_coordinates"],
                    Metadata(
                        results["start_hub_type"],
                        results["start_hub_metadata"],
                    ),
                ),
                end_hub=(
                    results["end_hub_coordinates"],
                    Metadata(
                        results["end_hub_type"],
                        results["end_hub_metadata"],
                    ),
                ),
                hubs=new_hub,
            )
        except ValueError:
            print(FileReaderError("Invalid input"))
            exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="fly-in")
    parser.parse_args()
    input = FileReader.parseinput("test_map.txt")
    print(input.nb_drones)
    print(input.start_hub)
    print(input.end_hub)
    pprint(input.hubs["roof1"])
    pprint(input.hubs["roof2"])
