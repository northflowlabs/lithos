"""Shared dependencies: the catalog singleton and request parsing helpers."""

from __future__ import annotations

import functools
from datetime import date

from fastapi import HTTPException
from lithos_ingest.base import BBox, PointFilters, TimeWindow
from lithos_ingest.catalog import LithosCatalog

# A bbox larger than this (in square degrees) is rejected to protect the service.
MAX_BBOX_AREA = 30.0


@functools.lru_cache(maxsize=1)
def get_catalog() -> LithosCatalog:
    """Process-wide catalog. Loads sources once; the sample source caches the hero."""
    return LithosCatalog()


def parse_bbox(bbox: str) -> BBox:
    try:
        parts = [float(x) for x in bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(400, "bbox must be 'minlon,minlat,maxlon,maxlat'") from exc
    if len(parts) != 4:
        raise HTTPException(400, "bbox must have exactly four comma-separated numbers")
    b = BBox(*parts)
    if b.min_lon >= b.max_lon or b.min_lat >= b.max_lat:
        raise HTTPException(400, "bbox min must be less than max")
    area = (b.max_lon - b.min_lon) * (b.max_lat - b.min_lat)
    if area > MAX_BBOX_AREA:
        raise HTTPException(
            413, f"bbox too large ({area:.1f} deg^2 > {MAX_BBOX_AREA}); zoom in or draw an AOI"
        )
    return b


def parse_time_window(start: str | None, end: str | None) -> TimeWindow | None:
    if not start and not end:
        return None
    s = date.fromisoformat(start) if start else None
    e = date.fromisoformat(end) if end else None
    return TimeWindow(start=s, end=e)


def build_filters(
    min_coherence: float | None,
    min_velocity: float | None,
    limit: int | None,
) -> PointFilters:
    return PointFilters(
        min_coherence=min_coherence,
        min_abs_velocity=min_velocity,
        max_points=limit,
    )
