"""EGMS adapter (Europe).

Talks to the Copernicus European Ground Motion Service machine-to-machine API to
download Ortho (vertical + horizontal) and Calibrated L2b products, then normalises
them into the canonical schema.

Coverage truth encoded here: Copernicus Participating States only (EU + Norway + UK +
Iceland), rolling ~5-year windows. EGMS data is open under Copernicus terms but
downloads require a free Copernicus account.

Graceful degradation: with no credentials, query_points returns [] and the catalog
falls back to the cached sample source so the hero scene still renders. No hard crash.
"""

from __future__ import annotations

import logging
import os

import httpx
from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    SourceMeta,
    TimeSeries,
)

from lithos_ingest.base import BBox, PointFilters, TimeWindow

log = logging.getLogger("lithos.ingest.egms")

# Copernicus Participating States footprint, as coarse coverage cells. This is the
# honest statement of where EGMS has data; densities are validated mm-grade within.
_EGMS_FOOTPRINT = BBox(min_lon=-25.0, min_lat=34.0, max_lon=45.0, max_lat=72.0)


class EgmsSource:
    """EGMS M2M adapter. Degrades to empty (not error) without credentials."""

    key = "egms"

    def __init__(
        self,
        api_base: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_base = (api_base or os.getenv("EGMS_API_BASE", "https://egms.land.copernicus.eu/api")).rstrip("/")
        self.username = username or os.getenv("EGMS_USERNAME")
        self.password = password or os.getenv("EGMS_PASSWORD")
        self.timeout = timeout
        self._token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password)

    # --- auth --------------------------------------------------------------------
    def _authenticate(self) -> str | None:
        if self._token:
            return self._token
        if not self.configured:
            log.info("EGMS credentials not set; adapter will return no points.")
            return None
        try:
            resp = httpx.post(
                f"{self.api_base}/auth/token",
                data={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            self._token = resp.json().get("access_token")
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            log.warning("EGMS authentication failed: %s", exc)
            self._token = None
        return self._token

    # --- GroundMotionSource ------------------------------------------------------
    def source_metadata(self) -> SourceMeta:
        return SourceMeta(
            key="egms",
            name="European Ground Motion Service (EGMS)",
            license="Copernicus terms; free with a Copernicus account",
            attribution="Contains modified Copernicus data. European Ground Motion Service, Copernicus Land Monitoring Service.",
            citation=(
                "European Environment Agency (Copernicus Land Monitoring Service), "
                "European Ground Motion Service (EGMS)."
            ),
            coverage_description=(
                "EU + Norway + UK + Iceland (Copernicus Participating States). "
                "Validated, mm-grade, rolling ~5-year windows. Not available outside these states."
            ),
            url="https://egms.land.copernicus.eu/",
        )

    def list_coverage(self) -> list[CoverageCell]:
        # The EGMS footprint as one honest coverage cell. The catalog refines density
        # from points actually queried.
        return [
            CoverageCell(
                cell_id="egms-footprint",
                bbox=_EGMS_FOOTPRINT.as_tuple(),
                available=self.configured,
                sources=["egms"],
                newest_window="2019-2023",
                density_class="dense" if self.configured else "none",
                note=(
                    "Copernicus Participating States. Set EGMS_USERNAME/PASSWORD to enable downloads."
                    if not self.configured
                    else "EGMS Ortho/Calibrated products."
                ),
            )
        ]

    def query_points(
        self,
        bbox: BBox,
        time_window: TimeWindow | None = None,
        filters: PointFilters | None = None,
    ) -> list[MeasurementPoint]:
        if not _EGMS_FOOTPRINT.contains(bbox.min_lon, bbox.min_lat):
            return []
        token = self._authenticate()
        if not token:
            return []
        try:  # pragma: no cover - network path, exercised in integration only
            resp = httpx.get(
                f"{self.api_base}/v1/points",
                params={
                    "bbox": ",".join(map(str, bbox.as_tuple())),
                    "product": "ortho",
                    "limit": (filters.max_points if filters and filters.max_points else 5000),
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return [self._normalise(f) for f in resp.json().get("features", [])]
        except httpx.HTTPError as exc:
            log.warning("EGMS query failed (%s); degrading gracefully.", exc)
            return []

    def get_time_series(self, point_id: str) -> TimeSeries | None:  # pragma: no cover
        token = self._authenticate()
        if not token:
            return None
        try:
            resp = httpx.get(
                f"{self.api_base}/v1/points/{point_id}/timeseries",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            from lithos_core.schema import TimeSeriesSample

            samples = [
                TimeSeriesSample(date=s["date"], displacement_mm=s["displacement_mm"])
                for s in resp.json().get("samples", [])
            ]
            return TimeSeries(point_id=point_id, samples=samples)
        except httpx.HTTPError as exc:
            log.warning("EGMS time-series fetch failed: %s", exc)
            return None

    # --- normalisation -----------------------------------------------------------
    @staticmethod
    def _normalise(feature: dict) -> MeasurementPoint:
        """Map one EGMS Ortho feature into the canonical schema."""
        props = feature.get("properties", {})
        lon, lat = feature.get("geometry", {}).get("coordinates", [0.0, 0.0])
        return MeasurementPoint(
            id=str(props.get("pid", props.get("id"))),
            lon=lon,
            lat=lat,
            height_m=props.get("height"),
            vertical_velocity=props.get("vel_v") or props.get("velocity_v"),
            horizontal_velocity=props.get("vel_e") or props.get("velocity_e"),
            los_velocity=props.get("vel_los") or props.get("velocity"),
            velocity_uncertainty=props.get("vel_std") or props.get("velocity_std"),
            coherence=props.get("coherence") or props.get("temporal_coherence"),
            source="egms",
            product=props.get("product", "EGMS-Ortho"),
            processing_window=props.get("window"),
        )
