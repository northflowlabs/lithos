"""Minimal geometry helpers (point-in-polygon, bbox of a ring). Pure Python, no deps."""

from __future__ import annotations


def ring_bbox(ring: list[list[float]]) -> tuple[float, float, float, float]:
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return (min(lons), min(lats), max(lons), max(lats))


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon for a single ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    """GeoJSON Polygon coordinates: [exterior_ring, hole1, hole2, ...]."""
    if not polygon:
        return False
    if not point_in_ring(lon, lat, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(lon, lat, hole):
            return False
    return True
