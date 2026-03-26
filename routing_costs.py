from __future__ import annotations

import math
from math import inf
from typing import Any, Dict

from collections.abc import Mapping

from parser import ZoneTypes


class RoutingCostsError(Exception):
    """Invalid zone name or metadata when resolving movement costs."""


class ZoneMovementModel:
    def __init__(self, zones: Mapping[str, Dict[str, Any]]) -> None:
        self._zones = zones

    @staticmethod
    def _zone_type(
        zones: Mapping[str, Dict[str, Any]], zone_name: str
    ) -> ZoneTypes:
        zone = zones.get(zone_name)
        if zone is None:
            raise RoutingCostsError(f"Unknown zone '{zone_name}'")
        metadata = zone.get("metadata")
        if metadata is None:
            return ZoneTypes.NORMAL
        raw = getattr(metadata, "zone", ZoneTypes.NORMAL)
        if isinstance(raw, ZoneTypes):
            return raw
        return ZoneTypes(str(raw))

    def enter_cost(self, zone_name: str) -> float:
        zt = ZoneMovementModel._zone_type(self._zones, zone_name)
        if zt == ZoneTypes.BLOCKED:
            return inf
        return zt.cost

    def simulation_turn_weight(self, zone_name: str) -> int:
        cost = self.enter_cost(zone_name)
        if not math.isfinite(cost):
            return 1
        return max(1, int(round(cost)))

    def is_passable(self, zone_name: str) -> bool:
        return ZoneMovementModel._zone_type(
            self._zones, zone_name
        ).is_passable

    def is_priority(self, zone_name: str) -> bool:
        return ZoneMovementModel._zone_type(
            self._zones, zone_name
        ).is_priority
