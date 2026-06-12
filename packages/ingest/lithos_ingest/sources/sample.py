"""Sample source: serves the cached hero scene and fixtures from data/samples.

This adapter needs no credentials and no network, so the default view always renders.
It is the offline fallback and the thing tests run against.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    SourceMeta,
    TimeSeries,
    TimeSeriesSample,
)

from lithos_ingest.base import BBox, PointFilters, TimeWindow


def _default_samples_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "samples"


class SampleSource:
    """Serves cached GeoJSON points + time series from disk."""

    key = "sample"

    def __init__(self, samples_dir: Optional[Path] = None) -> None:
        self._dir = samples_dir or _default_samples_dir()
        self._points: dict[str, MeasurementPoint] = {}
        self._series: dict[str, TimeSeries] = {}
        self._meta: dict = {}
        self._loaded = False

    # --- loading -----------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        points_path = self._dir / "hero_points.geojson"
        series_path = self._dir / "hero_timeseries.json"
        if not points_path.exists():
            # Generate on demand so a fresh checkout still has a hero scene.
            from lithos_ingest import hero

            hero.write(hero.generate(), self._dir)

        geojson = json.loads(points_path.read_text(encoding="utf-8"))
        self._meta = geojson.get("metadata", {})
        ts_blob = json.loads(series_path.read_text(encoding="utf-8"))
        dates = ts_blob["dates"]

        for feat in geojson["features"]:
            props = feat["properties"]
            lon, lat = feat["geometry"]["coordinates"]
            pid = props["id"]
            disp = ts_blob["series"].get(pid)
            ts = None
            if disp is not None:
                ts = TimeSeries(
                    point_id=pid,
                    samples=[
                        TimeSeriesSample(date=d, displacement_mm=v)
                        for d, v in zip(dates, disp)
                    ],
                )
                self._series[pid] = ts
            self._points[pid] = MeasurementPoint(
                id=pid,
                lon=lon,
                lat=lat,
                vertical_velocity=props.get("vertical_velocity"),
                los_velocity=props.get("los_velocity"),
                velocity_uncertainty=props.get("velocity_uncertainty"),
                coherence=props.get("coherence"),
                quality=props.get("quality"),
                source=props.get("source", "sample-demo"),
                product=props.get("product", "sample"),
                processing_window=props.get("processing_window"),
                time_series=ts,
            )
        self._loaded = True

    # --- GroundMotionSource ------------------------------------------------------
    def source_metadata(self) -> SourceMeta:
        return SourceMeta(
            key="sample",
            name="LITHOS sample (hero scene)",
            license="Synthetic demonstration data, released with LITHOS under Apache-2.0",
            attribution="LITHOS sample scene, modelled on Bologna EGMS subsidence",
            citation="Northflow Technologies (2026). LITHOS sample hero scene.",
            coverage_description=(
                "A single cached demonstration tile over Bologna. Synthetic stand-in for "
                "a real EGMS tile so the app renders offline."
            ),
        )

    def list_coverage(self) -> list[CoverageCell]:
        self._ensure_loaded()
        bbox = self._meta.get("bbox", [11.27, 44.43, 11.47, 44.57])
        return [
            CoverageCell(
                cell_id="sample-bologna",
                bbox=tuple(bbox),  # type: ignore[arg-type]
                available=True,
                sources=["sample"],
                newest_window=self._meta.get("window", "2019-2023"),
                density_class="dense",
                note="Cached hero scene (synthetic demonstration data).",
            )
        ]

    def query_points(
        self,
        bbox: BBox,
        time_window: Optional[TimeWindow] = None,
        filters: Optional[PointFilters] = None,
    ) -> list[MeasurementPoint]:
        self._ensure_loaded()
        out: list[MeasurementPoint] = []
        for p in self._points.values():
            if not bbox.contains(p.lon, p.lat):
                continue
            if filters:
                if filters.min_coherence is not None and (p.coherence or 0) < filters.min_coherence:
                    continue
                if filters.min_abs_velocity is not None and abs(p.best_velocity or 0) < filters.min_abs_velocity:
                    continue
            out.append(p)
        out.sort(key=lambda p: abs(p.best_velocity or 0), reverse=True)
        if filters and filters.max_points:
            out = out[: filters.max_points]
        return out

    def get_time_series(self, point_id: str) -> Optional[TimeSeries]:
        self._ensure_loaded()
        return self._series.get(point_id)

    def get_point(self, point_id: str) -> Optional[MeasurementPoint]:
        self._ensure_loaded()
        return self._points.get(point_id)

    @property
    def meta_dict(self) -> dict:
        self._ensure_loaded()
        return self._meta
