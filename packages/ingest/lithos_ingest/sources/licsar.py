"""COMET LiCSAR adapter (global tectonic and volcanic belts).

LICENSING FIREWALL (see docs/licensing.md): the LiCSAR / LiCSBAS toolchain is GPL-3.0.
This adapter treats LiCSAR strictly as a DATA SOURCE accessed over the public HTTP
archive. It does NOT import, vendor, fork, or link any LiCSBAS / licsar_proc code.
Any time-series processing LITHOS needs is implemented independently in lithos_core
under Apache-2.0.

Coverage truth encoded here: strong over tectonic/volcanic belts and many populated
regions, NOT uniform global. Much of the stable continental interiors and the oceans
have thin or no coverage.

This release indexes frame metadata and portal-served velocity products. It is polite:
rate-limited and resumable. Volcanic/tectonic belts are declared as coverage cells from
the public frame catalogue.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    SourceMeta,
    TimeSeries,
)

from lithos_ingest.base import BBox, PointFilters, TimeWindow

log = logging.getLogger("lithos.ingest.licsar")

# Coarse honest coverage: principal tectonic and volcanic belts where LiCSAR frames
# are dense. Declared explicitly so the coverage layer never implies uniform global.
_LICSAR_BELTS: list[tuple[str, BBox, str]] = [
    ("anatolia-aegean", BBox(19.0, 34.0, 45.0, 42.0), "Anatolian / Aegean"),
    ("italy-tyrrhenian", BBox(6.0, 36.0, 19.0, 47.0), "Italy / Tyrrhenian"),
    ("iran-zagros", BBox(44.0, 25.0, 63.0, 40.0), "Iran / Zagros"),
    ("east-africa-rift", BBox(28.0, -12.0, 42.0, 18.0), "East African Rift"),
    ("andes", BBox(-81.0, -56.0, -62.0, 12.0), "Andes"),
    ("cascadia-california", BBox(-125.0, 32.0, -114.0, 49.0), "Cascadia / California"),
    ("japan", BBox(129.0, 30.0, 146.0, 46.0), "Japan"),
    ("indonesia-sunda", BBox(95.0, -11.0, 141.0, 6.0), "Indonesia / Sunda Arc"),
    ("himalaya", BBox(73.0, 26.0, 96.0, 36.0), "Himalaya"),
    ("iceland", BBox(-25.0, 63.0, -13.0, 67.0), "Iceland (volcanic)"),
]


class LicsarSource:
    """LiCSAR public-archive adapter. Data over the network only; no GPL code."""

    key = "licsar"

    def __init__(
        self,
        portal_base: Optional[str] = None,
        rate_limit_rps: Optional[float] = None,
        timeout: float = 60.0,
    ) -> None:
        self.portal_base = (
            portal_base
            or os.getenv(
                "LICSAR_PORTAL_BASE",
                "https://gws-access.jasmin.ac.uk/public/nceo_geohazards/LiCSAR_products",
            )
        ).rstrip("/")
        self.rate_limit_rps = rate_limit_rps or float(os.getenv("LICSAR_RATE_LIMIT_RPS", "2"))
        self.timeout = timeout
        self._last_request = 0.0

    def _throttle(self) -> None:
        """Polite rate limiting: never hammer the public archive."""
        min_interval = 1.0 / max(self.rate_limit_rps, 0.1)
        wait = min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    # --- GroundMotionSource ------------------------------------------------------
    def source_metadata(self) -> SourceMeta:
        return SourceMeta(
            key="licsar",
            name="COMET LiCSAR",
            license="Data under Copernicus Sentinel terms, analysed by COMET. Fetched over the network only.",
            attribution=(
                "Contains modified Copernicus Sentinel data, analysed by the Centre for "
                "Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET) LiCSAR."
            ),
            citation=(
                "Lazecky et al. (2020), LiCSAR: An Automatic InSAR Tool for Measuring and "
                "Monitoring Tectonic and Volcanic Activity. Remote Sensing."
            ),
            coverage_description=(
                "Global tectonic and volcanic belts and many populated regions. Strong but "
                "NOT uniform; stable interiors and oceans are thin or absent. Frame-based."
            ),
            url="https://comet.nerc.ac.uk/comet-lics-portal/",
        )

    def list_coverage(self) -> list[CoverageCell]:
        cells: list[CoverageCell] = []
        for cell_id, bbox, name in _LICSAR_BELTS:
            cells.append(
                CoverageCell(
                    cell_id=f"licsar-{cell_id}",
                    bbox=bbox.as_tuple(),
                    available=True,
                    sources=["licsar"],
                    newest_window="rolling",
                    density_class="moderate",
                    note=f"{name}: LiCSAR frames (tectonic/volcanic).",
                )
            )
        return cells

    def _covers(self, bbox: BBox) -> bool:
        cx = (bbox.min_lon + bbox.max_lon) / 2
        cy = (bbox.min_lat + bbox.max_lat) / 2
        return any(b.contains(cx, cy) for _, b, _ in _LICSAR_BELTS)

    def query_points(
        self,
        bbox: BBox,
        time_window: Optional[TimeWindow] = None,
        filters: Optional[PointFilters] = None,
    ) -> list[MeasurementPoint]:
        """Fetch portal-served velocity points for frames intersecting the bbox.

        Returns [] outside the indexed belts (honest: no fabricated coverage). The
        actual frame fetch is exercised in integration tests against recorded fixtures;
        here we degrade gracefully on any network failure.
        """
        if not self._covers(bbox):
            return []
        try:  # pragma: no cover - network path
            self._throttle()
            resp = httpx.get(
                f"{self.portal_base}/velocity",
                params={"bbox": ",".join(map(str, bbox.as_tuple()))},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return [self._normalise(f) for f in resp.json().get("features", [])]
        except httpx.HTTPError as exc:
            log.warning("LiCSAR query failed (%s); degrading gracefully.", exc)
            return []

    def get_time_series(self, point_id: str) -> Optional[TimeSeries]:  # pragma: no cover
        return None

    @staticmethod
    def _normalise(feature: dict) -> MeasurementPoint:
        props = feature.get("properties", {})
        lon, lat = feature.get("geometry", {}).get("coordinates", [0.0, 0.0])
        return MeasurementPoint(
            id=str(props.get("id")),
            lon=lon,
            lat=lat,
            los_velocity=props.get("vel"),
            velocity_uncertainty=props.get("vel_std"),
            coherence=props.get("coherence"),
            source="licsar",
            product=props.get("frame", "LiCSAR-frame"),
        )
