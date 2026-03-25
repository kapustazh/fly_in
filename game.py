from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from collections.abc import Mapping


class GameWorldError(Exception):
    """Invalid or incomplete world data (zones, hubs, graph)."""


class HubZoneResolver:
    """OOP entry for resolving zone names from parsed ``hub_type`` markers."""

    @staticmethod
    def zone_for_hub_type(
        zones: Mapping[str, Dict[str, Any]],
        hub_type: str,
    ) -> str:
        for name, zone in zones.items():
            if zone.get("hub_type") == hub_type:
                return name
        raise GameWorldError(f"Hub type '{hub_type}' was not found")


@dataclass
class GameWorld:
    """Parsed simulation state: graph, drone count, and resolved hub zones."""

    zones: Mapping[str, Dict[str, Any]]
    connections: Mapping[str, Dict[str, Any]]
    num_drones: int
    start_zone_name: str
    end_zone_name: str

    @classmethod
    def from_parsed_map(
        cls,
        zones: Mapping[str, Dict[str, Any]],
        connections: Mapping[str, Dict[str, Any]],
        num_drones: int,
    ) -> GameWorld:
        start = HubZoneResolver.zone_for_hub_type(zones, "start_hub")
        end = HubZoneResolver.zone_for_hub_type(zones, "end_hub")
        return cls(
            zones=zones,
            connections=connections,
            num_drones=num_drones,
            start_zone_name=start,
            end_zone_name=end,
        )
