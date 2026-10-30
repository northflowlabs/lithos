"""Read COMET LiCSAR products from the public archive over HTTP.

Data only. Nothing here imports LiCSBAS or licsar_proc (see docs/licensing.md). GeoTIFF
windows are read with HTTP range requests, so a city needs a few kilobytes per product
and not the whole frame. Reading needs the optional `scenes` extra (rasterio).
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date

import httpx
import numpy as np

from lithos_ingest.base import BBox

ARCHIVE = os.getenv(
    "LICSAR_ARCHIVE_BASE",
    "https://gws-access.jasmin.ac.uk/public/nceo_geohazards/LiCSAR_products.public",
).rstrip("/")

_PAIR = re.compile(r'href="(\d{8})_(\d{8})/?"')


def parse_date(text: str) -> date:
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


@dataclass(frozen=True)
class Pair:
    """One interferogram: phase change between two acquisition dates."""

    first: date
    second: date

    @property
    def name(self) -> str:
        return f"{self.first:%Y%m%d}_{self.second:%Y%m%d}"

    @property
    def days(self) -> int:
        return (self.second - self.first).days


def parse_pairs(listing: str) -> list[Pair]:
    """Interferogram pairs in an `interferograms/` directory listing."""
    found = {Pair(parse_date(a), parse_date(b)) for a, b in _PAIR.findall(listing)}
    return sorted(found, key=lambda p: (p.first, p.second))


def frame_url(frame: str) -> str:
    return f"{ARCHIVE}/{int(frame[:3])}/{frame}"


def list_pairs(frame: str, timeout: float = 60.0) -> list[Pair]:
    resp = httpx.get(f"{frame_url(frame)}/interferograms/", timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return parse_pairs(resp.text)


class Throttle:
    """Spaces out requests to the archive, however many threads share it."""

    def __init__(self, requests_per_second: float | None = None) -> None:
        rate = requests_per_second or float(os.getenv("LICSAR_RATE_LIMIT_RPS", "2"))
        self._interval = 1.0 / max(rate, 0.1)
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self._interval
        if start > now:
            time.sleep(start - now)


class Reader:
    """Windowed GeoTIFF reads at a polite request rate."""

    def __init__(self, bbox: BBox, requests_per_second: float | None = None) -> None:
        self.bbox = bbox
        self._throttle = Throttle(requests_per_second)

    def read(self, url: str) -> tuple[np.ndarray, tuple[float, float, float, float]] | None:
        """(array, (west, north, dx, dy)), or None when the product does not exist."""
        import rasterio
        from rasterio.errors import RasterioIOError
        from rasterio.windows import Window, from_bounds

        self._throttle.wait()
        path = url if not url.startswith("http") else f"/vsicurl/{url}"
        try:
            with (
                rasterio.Env(
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                    GDAL_HTTP_MAX_RETRY="3",
                    GDAL_HTTP_RETRY_DELAY="5",
                ),
                rasterio.open(path) as src,
            ):
                b = self.bbox
                window = from_bounds(b.min_lon, b.min_lat, b.max_lon, b.max_lat, src.transform)
                window = window.round_offsets().round_lengths()
                bounds = Window(0, 0, src.width, src.height)  # type: ignore[call-arg]
                window = window.intersection(bounds)
                data = src.read(1, window=window)
                t = src.window_transform(window)
                return data, (t.c, t.f, t.a, t.e)
        except RasterioIOError:
            return None
