"""COMET LiCSAR adapter (global tectonic and volcanic belts, many populated regions).

LICENSING FIREWALL (see docs/licensing.md): the LiCSAR / LiCSBAS toolchain is GPL-3.0.
This adapter treats LiCSAR strictly as a DATA SOURCE accessed over the public HTTP
archive. It does NOT import, vendor, fork, or link any LiCSBAS / licsar_proc code.
Time-series processing is implemented independently in lithos_core under Apache-2.0.

The archive publishes interferograms, not point velocities, so points come from scenes:
measured areas built by lithos_ingest.scene and stored under data/scenes. Coverage comes
from the frame index, a crawl of what the archive really holds.
"""

from __future__ import annotations

import json
import logging
from functools import cached_property
from pathlib import Path

from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    SourceMeta,
    TimeSeries,
    TimeSeriesSample,
)

from lithos_ingest.base import FRAME_INDEX, BBox, PointFilters, TimeWindow, data_dir

log = logging.getLogger("lithos.ingest.licsar")

HERO_SCENE = "bologna"


class LicsarSource:
    """Scenes measured from LiCSAR data. Data over the network only; no GPL code."""

    key = "licsar"

    def __init__(self, scenes_dir: Path | None = None) -> None:
        self._dir = scenes_dir or data_dir() / "scenes"
        self._points: dict[str, MeasurementPoint] = {}
        self._series: dict[str, TimeSeries] = {}
        self._scenes: dict[str, dict] = {}
        self._loaded = False

    # --- loading -----------------------------------------------------------------
    def _load_scene(self, folder: Path) -> None:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        geojson = json.loads((folder / "points.geojson").read_text(encoding="utf-8"))
        blob = json.loads((folder / "timeseries.json").read_text(encoding="utf-8"))
        self._scenes[meta["slug"]] = meta
        dates = blob["dates"]
        for feature in geojson["features"]:
            props = feature["properties"]
            lon, lat = feature["geometry"]["coordinates"]
            pid = props["id"]
            ts = TimeSeries(
                point_id=pid,
                samples=[
                    TimeSeriesSample(date=d, displacement_mm=v)
                    for d, v in zip(dates, blob["series"][pid], strict=True)
                    if v is not None
                ],
            )
            self._series[pid] = ts
            self._points[pid] = MeasurementPoint(
                id=pid,
                lon=lon,
                lat=lat,
                height_m=props.get("height_m"),
                vertical_velocity=props.get("vertical_velocity"),
                horizontal_velocity=props.get("horizontal_velocity"),
                los_velocity=props.get("los_velocity"),
                velocity_uncertainty=props.get("velocity_uncertainty"),
                coherence=props.get("coherence"),
                quality=props.get("quality"),
                source="licsar",
                product=props.get("product", "LiCSAR"),
                processing_window=props.get("processing_window"),
                time_series=ts,
            )

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._dir.is_dir():
            for folder in sorted(p for p in self._dir.iterdir() if (p / "meta.json").exists()):
                self._load_scene(folder)
        if not self._scenes:
            log.warning("No scenes in %s; set LITHOS_DATA_DIR or build one.", self._dir)
        self._loaded = True

    @cached_property
    def frames(self) -> list[dict]:
        """Every published frame, from the committed crawl of the archive."""
        return json.loads(FRAME_INDEX.read_text(encoding="utf-8"))["frames"]

    def frames_over(self, bbox: BBox) -> list[dict]:
        """Frames whose footprint overlaps the box, freshest first."""
        hits = [
            f
            for f in self.frames
            if f["bbox"][0] <= bbox.max_lon
            and f["bbox"][2] >= bbox.min_lon
            and f["bbox"][1] <= bbox.max_lat
            and f["bbox"][3] >= bbox.min_lat
        ]
        return sorted(hits, key=lambda f: f["last_epoch"], reverse=True)

    # --- GroundMotionSource ------------------------------------------------------
    def source_metadata(self) -> SourceMeta:
        return SourceMeta(
            key="licsar",
            name="COMET LiCSAR",
            license=(
                "UK Open Government Licence v3.0, and the Copernicus terms for Sentinel data. "
                "Fetched over the network only."
            ),
            attribution=(
                "LiCSAR contains modified Copernicus Sentinel data analysed by the Centre for "
                "the Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET)."
            ),
            citation=(
                "Lazecky et al. (2020), LiCSAR: An Automatic InSAR Tool for Measuring and "
                "Monitoring Tectonic and Volcanic Activity. Remote Sensing 12(15), 2430."
            ),
            coverage_description=(
                "Sentinel-1 frames over tectonic and volcanic belts and many populated regions. "
                "Not uniform. LITHOS serves points where a scene has been built."
            ),
            url="https://comet.nerc.ac.uk/comet-lics-portal/",
        )

    def list_coverage(self) -> list[CoverageCell]:
        cells = [
            CoverageCell(
                cell_id=f"licsar-{f['id']}",
                bbox=tuple(f["bbox"]),
                available=True,
                sources=["licsar"],
                newest_window=f["last_epoch"],
                density_class="moderate",
                note=f"LiCSAR frame {f['id']}, newest acquisition {f['last_epoch']}.",
            )
            for f in self.frames
        ]
        return cells

    def query_points(
        self,
        bbox: BBox,
        time_window: TimeWindow | None = None,
        filters: PointFilters | None = None,
    ) -> list[MeasurementPoint]:
        self._ensure_loaded()
        out: list[MeasurementPoint] = []
        for p in self._points.values():
            if not bbox.contains(p.lon, p.lat):
                continue
            if filters:
                if filters.min_coherence is not None and (p.coherence or 0) < filters.min_coherence:
                    continue
                if (
                    filters.min_abs_velocity is not None
                    and abs(p.best_velocity or 0) < filters.min_abs_velocity
                ):
                    continue
            out.append(p)
        out.sort(key=lambda p: abs(p.best_velocity or 0), reverse=True)
        if filters and filters.max_points:
            out = out[: filters.max_points]
        return out

    def get_time_series(self, point_id: str) -> TimeSeries | None:
        self._ensure_loaded()
        return self._series.get(point_id)

    def get_point(self, point_id: str) -> MeasurementPoint | None:
        self._ensure_loaded()
        return self._points.get(point_id)

    @property
    def hero(self) -> dict:
        """The scene the map opens on."""
        self._ensure_loaded()
        return self._scenes[HERO_SCENE]
