"""Movement costs and passability derived from per-zone ZoneTypes metadata."""

from __future__ import annotations

import math
from math import inf
from typing import Any

from collections.abc import Mapping

from parser import ZoneTypes


class RoutingCostsError(Exception):
    """Invalid zone name or metadata when resolving movement costs."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Routing loading error: {detail}")


class ZoneMovementModel:
    """Read-only view of zone types for routing.

    Sets enter cost, passability, and A* tie-break priority from metadata.
    """

    def __init__(self, zones: Mapping[str, dict[str, Any]]) -> None:
        """Store the zone table used to resolve ZoneTypes for any name."""
        self._zones = zones

    @staticmethod
    def _zone_type(
        zones: Mapping[str, dict[str, Any]], zone_name: str
    ) -> ZoneTypes:
        """Normalize metadata (or defaults) to a ZoneTypes enum value."""
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
        """Cost to enter *zone_name* (infinity if blocked)."""
        zone_type = ZoneMovementModel._zone_type(self._zones, zone_name)
        if zone_type == ZoneTypes.BLOCKED:
            return inf
        return zone_type.cost

    def simulation_turn_weight(self, zone_name: str) -> int:
        """Integer turns spent entering *zone_name* (at least 1 if finite)."""
        cost = self.enter_cost(zone_name)
        if not math.isfinite(cost):
            return 1
        weight = int(round(cost))
        if weight < 1:
            return 1
        return weight

    def is_passable(self, zone_name: str) -> bool:
        """False for blocked zones."""
        return ZoneMovementModel._zone_type(self._zones, zone_name).is_passable

    def is_priority(self, zone_name: str) -> bool:
        """Priority zones sort earlier in open heaps (pathfinder tie-break)."""
        return ZoneMovementModel._zone_type(self._zones, zone_name).is_priority
