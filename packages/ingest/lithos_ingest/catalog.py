"""LithosCatalog: the data layer the API serves from.

Composes one or more GroundMotionSource adapters, dispatches queries across them, and
runs the anomaly engine. Coverage is computed from the sources' real declared extents,
never hardcoded. Anomaly verdicts are cached per point for fast repeat serving.
"""

from __future__ import annotations

import logging
import os

from lithos_core.anomaly import AreaScanResult, analyse_point, scan_area
from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    PointVerdict,
    SourceMeta,
    TimeSeries,
)

from lithos_ingest.base import BBox, GroundMotionSource, PointFilters, TimeWindow
from lithos_ingest.registry import get_source

log = logging.getLogger("lithos.ingest.catalog")

# A coarse global grid for the coverage overlay. Each declared source-cell stamps the
# grid cells it overlaps. Cells nobody stamps are honestly reported as "none".
_GLOBAL_GRID_DEG = 5.0


class LithosCatalog:
    def __init__(self, sources: list[GroundMotionSource] | None = None) -> None:
        if sources is None:
            keys = os.getenv("LITHOS_SOURCES", "licsar,egms").split(",")
            sources = [get_source(k.strip()) for k in keys if k.strip()]
        self.sources = sources
        self._verdict_cache: dict[str, PointVerdict] = {}

    # --- metadata ----------------------------------------------------------------
    def source_metas(self) -> list[SourceMeta]:
        return [s.source_metadata() for s in self.sources]

    # --- points ------------------------------------------------------------------
    def query_points(
        self,
        bbox: BBox,
        time_window: TimeWindow | None = None,
        filters: PointFilters | None = None,
    ) -> list[MeasurementPoint]:
        points: list[MeasurementPoint] = []
        for src in self.sources:
            try:
                points.extend(src.query_points(bbox, time_window, filters))
            except Exception as exc:  # noqa: BLE001  one bad source must not crash the query
                log.warning("source %s failed on query_points: %s", getattr(src, "key", "?"), exc)
        if filters and filters.max_points:
            points.sort(key=lambda p: abs(p.best_velocity or 0), reverse=True)
            points = points[: filters.max_points]
        return points

    def get_time_series(self, point_id: str) -> TimeSeries | None:
        for src in self.sources:
            try:
                ts = src.get_time_series(point_id)
                if ts is not None:
                    return ts
            except Exception as exc:  # noqa: BLE001  one bad source must not crash the query
                log.warning("source %s failed on get_time_series: %s", getattr(src, "key", "?"), exc)
        return None

    def get_point(self, point_id: str) -> MeasurementPoint | None:
        """Look up a full measurement point by id across sources that support it."""
        for src in self.sources:
            getter = getattr(src, "get_point", None)
            if getter is None:
                continue
            try:
                p = getter(point_id)
                if p is not None:
                    return p
            except Exception as exc:  # noqa: BLE001  one bad source must not crash the query
                log.warning("source %s failed on get_point: %s", getattr(src, "key", "?"), exc)
        return None

    # --- warm-up -----------------------------------------------------------------
    def warm_hero(self) -> int:
        """Precompute and cache verdicts for the hero scene so the first anomaly
        request is served from cache and the hero view stays under the three-second
        wow gate. Safe to call at startup; returns points warmed."""
        warmed = 0
        for src in self.sources:
            hero = getattr(src, "hero", None)
            if hero is None:
                continue
            try:
                for p in src.query_points(BBox(*hero["bbox"])):
                    self.verdict_for(p)
                    warmed += 1
            except Exception as exc:  # noqa: BLE001  warm-up must never crash the catalogue
                log.warning("hero warm-up skipped: %s", exc)
        return warmed

    # --- anomalies ---------------------------------------------------------------
    def verdict_for(self, point: MeasurementPoint) -> PointVerdict:
        cached = self._verdict_cache.get(point.id)
        if cached is not None:
            return cached
        verdict = analyse_point(point)
        self._verdict_cache[point.id] = verdict
        return verdict

    def anomalies_in_bbox(
        self,
        bbox: BBox,
        time_window: TimeWindow | None = None,
        filters: PointFilters | None = None,
    ) -> list[PointVerdict]:
        points = self.query_points(bbox, time_window, filters)
        verdicts = [self.verdict_for(p) for p in points]
        verdicts.sort(key=lambda v: v.newsworthiness, reverse=True)
        return verdicts

    def scan_aoi(
        self,
        points: list[MeasurementPoint],
        cluster_radius_deg: float = 0.01,
    ) -> AreaScanResult:
        return scan_area(points, cluster_radius_deg=cluster_radius_deg)

    # --- coverage ----------------------------------------------------------------
    def coverage(self) -> list[CoverageCell]:
        """Merge declared source coverage into one honest set of cells."""
        cells: list[CoverageCell] = []
        for src in self.sources:
            try:
                cells.extend(src.list_coverage())
            except Exception as exc:  # noqa: BLE001  one bad source must not crash the query
                log.warning("source %s failed on list_coverage: %s", getattr(src, "key", "?"), exc)
        return cells

    def coverage_grid(self) -> list[CoverageCell]:
        """A coarse global grid for the overlay, stamped from real source extents.

        A cell counts as covered when a source extent overlaps it. Cells with no source
        are returned with available=False and an honest note, so the map can render
        emptiness as a deliberate scientific layer, never a blank.
        """
        source_cells = self.coverage()
        grid: list[CoverageCell] = []
        lon = -180.0
        while lon < 180.0:
            lat = -60.0
            while lat < 80.0:
                cell_bbox = BBox(lon, lat, lon + _GLOBAL_GRID_DEG, lat + _GLOBAL_GRID_DEG)
                cx, cy = lon + _GLOBAL_GRID_DEG / 2, lat + _GLOBAL_GRID_DEG / 2
                overlapping = [
                    c
                    for c in source_cells
                    if c.available
                    and c.bbox[0] < cell_bbox.max_lon
                    and c.bbox[2] > cell_bbox.min_lon
                    and c.bbox[1] < cell_bbox.max_lat
                    and c.bbox[3] > cell_bbox.min_lat
                ]
                if overlapping:
                    sources = sorted({s for c in overlapping for s in c.sources})
                    frames = [c for c in overlapping if "licsar" in c.sources]
                    density = "dense" if len(frames) >= 8 else "moderate"
                    newest = max((c.newest_window or "" for c in frames), default="")
                    parts = []
                    if frames:
                        parts.append(f"{len(frames)} Sentinel-1 frames, newest {newest}")
                    if "egms" in sources:
                        parts.append("EGMS tiles where the service covers this cell")
                    grid.append(
                        CoverageCell(
                            cell_id=f"g{int(cx)}_{int(cy)}",
                            bbox=cell_bbox.as_tuple(),
                            available=True,
                            sources=sources,
                            newest_window=newest or None,
                            density_class=density,
                            note="; ".join(parts) + ".",
                        )
                    )
                else:
                    grid.append(
                        CoverageCell(
                            cell_id=f"g{int(cx)}_{int(cy)}",
                            bbox=cell_bbox.as_tuple(),
                            available=False,
                            sources=[],
                            density_class="none",
                            note="No public InSAR ground-motion product indexed here.",
                        )
                    )
                lat += _GLOBAL_GRID_DEG
            lon += _GLOBAL_GRID_DEG
        return grid
