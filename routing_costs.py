from __future__ import annotations

import math
from math import inf
from typing import Any, Dict
from collections.abc import Mapping

from parser import ZoneTypes


class RoutingCostsError(Exception):
    """Invalid zone name or metadata when resolving movement costs."""


def _zone_type_for_zone(
    zones: Mapping[str, Dict[str, Any]],
    zone_name: str,
) -> ZoneTypes:
    zone = zones.get(zone_name)
    if zone is None:
        raise RoutingCostsError(f"Unknown zone '{zone_name}'")

    metadata = zone.get("metadata")
    if metadata is None:
        return ZoneTypes.NORMAL

    raw_zone = getattr(metadata, "zone", ZoneTypes.NORMAL)
    if isinstance(raw_zone, ZoneTypes):
        return raw_zone
    return ZoneTypes(str(raw_zone))


class ZoneMovementModel:

    def __init__(self, zones: Mapping[str, Dict[str, Any]]) -> None:
        self._zones = zones

    def enter_cost(self, zone_name: str) -> float:
        zone_type = _zone_type_for_zone(self._zones, zone_name)
        if zone_type == ZoneTypes.BLOCKED:
            return inf
        return zone_type.cost

    def simulation_turn_weight(self, zone_name: str) -> int:
        cost = self.enter_cost(zone_name)
        if not math.isfinite(cost):
            return 1
        weight = int(round(cost))
        return max(1, weight)

    def is_passable(self, zone_name: str) -> bool:
        zone_type = _zone_type_for_zone(self._zones, zone_name)
        return zone_type.is_passable

    def is_priority(self, zone_name: str) -> bool:
        zone_type = _zone_type_for_zone(self._zones, zone_name)
        return zone_type.is_priority
