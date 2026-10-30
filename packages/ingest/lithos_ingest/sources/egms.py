"""EGMS adapter (Europe).

Talks to the Copernicus European Ground Motion Service archive API, as documented in
https://github.com/copernicus-land/egms-api, downloads Ortho (Level 3) tiles and normalises
them into the canonical schema.

Access needs a personal CLMS API key: register at https://land.copernicus.eu, create an
API token in your profile, and point CLMS_SERVICE_KEY_FILE at the JSON file you receive
(or put its contents in CLMS_SERVICE_KEY). The key signs a short-lived grant, so it needs
the `egms` extra (PyJWT, cryptography, pyproj). Without a key the adapter returns no
points and reports its coverage as unavailable.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import time
import zipfile
from datetime import date
from pathlib import Path

import httpx
from lithos_core.schema import (
    CoverageCell,
    MeasurementPoint,
    SourceMeta,
    TimeSeries,
    TimeSeriesSample,
)

from lithos_ingest.base import BBox, PointFilters, TimeWindow, data_dir

log = logging.getLogger("lithos.ingest.egms")

API_BASE = "https://egms.land.copernicus.eu/insar-api/archive"

# The Copernicus Participating States as one coarse box. The service does not cover the
# whole box; the search endpoint decides, per query, which tiles exist.
_EGMS_FOOTPRINT = BBox(min_lon=-25.0, min_lat=34.0, max_lon=45.0, max_lat=72.0)

# The API refuses a bounding box wider than this in either direction.
MAX_QUERY_DEG = 5.0
_DATE_COLUMN = re.compile(r"^\d{8}$")


def parse_ortho_csv(text: str) -> tuple[list[dict], list[date]]:
    """Rows and epoch dates of one Ortho tile CSV. Epochs are columns named YYYYMMDD."""
    delimiter = ";" if ";" in text.split("\n", 1)[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    columns = [c for c in (reader.fieldnames or []) if _DATE_COLUMN.match(c)]
    dates = [date(int(c[:4]), int(c[4:6]), int(c[6:8])) for c in columns]
    rows = []
    for row in reader:
        row["_series"] = [float(row[c]) for c in columns]
        rows.append(row)
    return rows, dates


class EgmsSource:
    """EGMS archive API adapter. Returns nothing, and says so, without a key."""

    key = "egms"

    def __init__(
        self,
        api_base: str | None = None,
        service_key: dict | None = None,
        timeout: float = 120.0,
        cache_dir: Path | None = None,
    ) -> None:
        self.api_base = (api_base or os.getenv("EGMS_API_BASE", API_BASE)).rstrip("/")
        self.service_key = service_key or self._key_from_env()
        self.timeout = timeout
        self.cache_dir = cache_dir or data_dir() / "cache" / "egms"
        self._token: str | None = None
        self._token_expires = 0.0
        self._series: dict[str, TimeSeries] = {}

    @staticmethod
    def _key_from_env() -> dict | None:
        path = os.getenv("CLMS_SERVICE_KEY_FILE")
        if path:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        inline = os.getenv("CLMS_SERVICE_KEY")
        return json.loads(inline) if inline else None

    @property
    def configured(self) -> bool:
        return self.service_key is not None

    # --- auth --------------------------------------------------------------------
    def _access_token(self) -> str:
        """Exchange the service key for a short-lived access token (RFC 7523 grant)."""
        if self._token and time.time() < self._token_expires:
            return self._token
        import jwt

        assert self.service_key is not None
        now = int(time.time())
        key = self.service_key
        grant = jwt.encode(
            {
                "iss": key["client_id"],
                "sub": key["user_id"],
                "aud": key["token_uri"],
                "iat": now,
                "exp": now + 3600,
            },
            key["private_key"],
            algorithm="RS256",
        )
        resp = httpx.post(
            key["token_uri"],
            headers={"Accept": "application/json"},
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": grant},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        token: str = resp.json()["access_token"]
        self._token = token
        self._token_expires = now + 3000
        return token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token()}", "Accept": "application/json"}

    # --- archive API -------------------------------------------------------------
    def _latest_release(self) -> str:
        resp = httpx.get(f"{self.api_base}/releases", headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return max(resp.json())

    def _search(self, bbox: BBox, release: str, product_type: str) -> tuple[list[dict], str]:
        resp = httpx.post(
            f"{self.api_base}/search",
            headers=self._headers(),
            json={
                "id": None,
                "bbox": [[bbox.min_lon, bbox.min_lat], [bbox.max_lon, bbox.max_lat]],
                "levels": ["L3"],
                "releases": [release],
                "productType": product_type,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("status", True):
            raise RuntimeError(f"EGMS search refused: {body.get('message')}")
        return body.get("hits", []), body.get("id", "")

    def _tile_text(self, filename: str, query_id: str) -> str:
        """A tile's CSV, downloaded once and kept in the cache."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / filename
        if not path.exists():
            with httpx.stream(
                "GET",
                f"{self.api_base}/download/{filename}",
                params={"id": query_id},
                headers=self._headers(),
                timeout=self.timeout,
                follow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                partial = path.with_suffix(".part")
                with partial.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
            partial.replace(path)
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
            return archive.read(name).decode("utf-8")

    # --- GroundMotionSource ------------------------------------------------------
    def source_metadata(self) -> SourceMeta:
        return SourceMeta(
            key="egms",
            name="European Ground Motion Service (EGMS)",
            license="Free and open under the Copernicus data policy; downloads need a CLMS API key",
            attribution=(
                "Contains modified Copernicus data. European Ground Motion Service, "
                "Copernicus Land Monitoring Service."
            ),
            citation=(
                "European Environment Agency (Copernicus Land Monitoring Service), "
                "European Ground Motion Service (EGMS)."
            ),
            coverage_description=(
                "Copernicus Participating States. Validated, rolling five-year releases. "
                "Not available elsewhere. Active only when a CLMS API key is configured."
            ),
            url="https://egms.land.copernicus.eu/",
        )

    def list_coverage(self) -> list[CoverageCell]:
        return [
            CoverageCell(
                cell_id="egms-footprint",
                bbox=_EGMS_FOOTPRINT.as_tuple(),
                available=self.configured,
                sources=["egms"],
                density_class="dense" if self.configured else "none",
                note=(
                    "EGMS Ortho tiles, Copernicus Participating States."
                    if self.configured
                    else "EGMS needs a CLMS API key, which this deployment does not have."
                ),
            )
        ]

    def query_points(
        self,
        bbox: BBox,
        time_window: TimeWindow | None = None,
        filters: PointFilters | None = None,
    ) -> list[MeasurementPoint]:
        if not self.configured:
            return []
        overlaps = (
            bbox.min_lon <= _EGMS_FOOTPRINT.max_lon
            and bbox.max_lon >= _EGMS_FOOTPRINT.min_lon
            and bbox.min_lat <= _EGMS_FOOTPRINT.max_lat
            and bbox.max_lat >= _EGMS_FOOTPRINT.min_lat
        )
        too_wide = (
            bbox.max_lon - bbox.min_lon > MAX_QUERY_DEG
            or bbox.max_lat - bbox.min_lat > MAX_QUERY_DEG
        )
        if not overlaps or too_wide:
            return []
        try:
            return self._fetch_points(bbox, filters)
        except (httpx.HTTPError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
            log.warning("EGMS query failed: %s", exc)
            return []

    def _fetch_points(self, bbox: BBox, filters: PointFilters | None) -> list[MeasurementPoint]:
        from pyproj import Transformer

        release = self._latest_release()
        to_wgs84 = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)
        east_by_cell: dict[tuple[str, str], float] = {}
        hits, query_id = self._search(bbox, release, "ORTHO-EAST")
        for hit in hits:
            for row in parse_ortho_csv(self._tile_text(hit["filename"], query_id))[0]:
                east_by_cell[(row["easting"], row["northing"])] = float(row["mean_velocity"])

        points: list[MeasurementPoint] = []
        hits, query_id = self._search(bbox, release, "ORTHO-UP")
        for hit in hits:
            rows, dates = parse_ortho_csv(self._tile_text(hit["filename"], query_id))
            tile = hit.get("tileId", hit["filename"])
            for row in rows:
                lon, lat = to_wgs84.transform(float(row["easting"]), float(row["northing"]))
                if not bbox.contains(lon, lat):
                    continue
                pid = f"egms-{tile}-{row['pid']}"
                series = TimeSeries(
                    point_id=pid,
                    samples=[
                        TimeSeriesSample(date=d, displacement_mm=v)
                        for d, v in zip(dates, row["_series"], strict=True)
                    ],
                )
                self._series[pid] = series
                points.append(
                    MeasurementPoint(
                        id=pid,
                        lon=lon,
                        lat=lat,
                        height_m=float(row["height"]),
                        vertical_velocity=float(row["mean_velocity"]),
                        horizontal_velocity=east_by_cell.get((row["easting"], row["northing"])),
                        velocity_uncertainty=float(row["mean_velocity_std"]),
                        source="egms",
                        product="EGMS-Ortho",
                        processing_window=release,
                        time_series=series,
                    )
                )
        if filters and filters.min_abs_velocity is not None:
            points = [p for p in points if abs(p.best_velocity or 0) >= filters.min_abs_velocity]
        points.sort(key=lambda p: abs(p.best_velocity or 0), reverse=True)
        if filters and filters.max_points:
            points = points[: filters.max_points]
        return points

    def get_time_series(self, point_id: str) -> TimeSeries | None:
        return self._series.get(point_id)
