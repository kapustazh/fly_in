from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from collections.abc import Mapping


class GameWorldError(Exception):
    """Invalid or incomplete world data (e.g. missing start or end hub)."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Game world error: {detail}")


@dataclass
class GameWorld:
    """Parsed simulation state: graph, drone count, and resolved hub zones."""

    zones: Mapping[str, Dict[str, Any]]
    connections: Mapping[str, Dict[str, Any]]
    num_drones: int
    start_zone_name: str
    end_zone_name: str

    @staticmethod
    def _zone_for_hub_type(
        zones: Mapping[str, Dict[str, Any]], hub_type: str
    ) -> str:
        """Return the unique zone name whose hub_type matches *hub_type*."""
        for name, zone in zones.items():
            if zone.get("hub_type") == hub_type:
                return name
        raise GameWorldError(f"Hub type '{hub_type}' was not found")

    @classmethod
    def from_parsed_map(
        cls,
        zones: Mapping[str, Dict[str, Any]],
        connections: Mapping[str, Dict[str, Any]],
        num_drones: int,
    ) -> GameWorld:
        """Build world from hub_type (start/end) and drone count."""
        start = GameWorld._zone_for_hub_type(zones, "start_hub")
        end = GameWorld._zone_for_hub_type(zones, "end_hub")
        return cls(
            zones=zones,
            connections=connections,
            num_drones=num_drones,
            start_zone_name=start,
            end_zone_name=end,
        )
