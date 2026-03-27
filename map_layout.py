"""Map grid to screen pixels: zone centers and global pan offsets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneLayout:
    """Screen-space layout: zone name to pixel center plus map offsets."""

    pixel_center_by_zone: dict[str, tuple[float, float]]
    offset_x: int
    offset_y: int

    def pixel_center_for_zone_name(
        self, zone_name: str
    ) -> tuple[float, float]:
        """Return screen-space center of *zone_name* (raises if unknown)."""
        pixel_center = self.pixel_center_by_zone.get(zone_name)
        if pixel_center is None:
            raise ValueError(f"No pixel position for zone '{zone_name}'")
        return pixel_center
