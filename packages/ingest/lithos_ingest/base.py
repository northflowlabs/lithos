"""The source-adapter contract.

Every data source implements `GroundMotionSource`. The rest of LITHOS depends only on
this protocol and on the canonical schema, never on a source's native format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol, runtime_checkable

from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    SourceMeta,
    TimeSeries,
)


@dataclass(frozen=True)
class BBox:
    """Geographic bounding box in WGS84 decimal degrees."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def contains(self, lon: float, lat: float) -> bool:
        return self.min_lon <= lon <= self.max_lon and self.min_lat <= lat <= self.max_lat

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)

    @classmethod
    def from_tuple(cls, t: tuple[float, float, float, float]) -> "BBox":
        return cls(*t)


@dataclass(frozen=True)
class TimeWindow:
    """Inclusive date range. Either bound may be None for open-ended."""

    start: Optional[date] = None
    end: Optional[date] = None

    def contains(self, d: date) -> bool:
        if self.start and d < self.start:
            return False
        if self.end and d > self.end:
            return False
        return True


@dataclass(frozen=True)
class PointFilters:
    """Optional query filters applied during point retrieval."""

    min_coherence: Optional[float] = None
    min_abs_velocity: Optional[float] = None
    max_points: Optional[int] = None


@runtime_checkable
class GroundMotionSource(Protocol):
    """The single interface every data source implements."""

    def source_metadata(self) -> SourceMeta:
        """License, attribution, citation, and honest coverage description."""
        ...

    def list_coverage(self) -> list[CoverageCell]:
        """Coarse global cells describing where this source actually has data."""
        ...

    def query_points(
        self,
        bbox: BBox,
        time_window: Optional[TimeWindow] = None,
        filters: Optional[PointFilters] = None,
    ) -> list[MeasurementPoint]:
        """Measurement points within the bbox (and optional window/filters)."""
        ...

    def get_time_series(self, point_id: str) -> Optional[TimeSeries]:
        """Full displacement history for a single point."""
        ...
