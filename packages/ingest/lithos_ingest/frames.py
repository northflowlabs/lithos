"""Build the LiCSAR frame index from the public archive.

The index lists every published frame with its real footprint and its newest epoch, so
coverage comes from what the archive holds and not from regions drawn by hand. It is a
long crawl, so the result is committed and refreshed from time to time. Run:
    python -m lithos_ingest.frames
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from lithos_ingest.base import FRAME_INDEX
from lithos_ingest.licsar_archive import ARCHIVE, Throttle

_FRAME = re.compile(r'href="(\d{3}[AD]_\d{5}_\d{6})/"')
_TRACK = re.compile(r'href="(\d{1,3})/"')
_EPOCH = re.compile(r'href="(\d{8})/?"')


def parse_frames(listing: str) -> list[str]:
    """Frame ids in a track listing. Directories marked for deletion do not match."""
    return sorted(set(_FRAME.findall(listing)))


def parse_epochs(listing: str) -> list[str]:
    return sorted(set(_EPOCH.findall(listing)))


def parse_poly(text: str) -> tuple[float, float, float, float] | None:
    """Bounding box of a frame's `-poly.txt`, one `lon lat` vertex per line. A few frames
    publish `None None` for a vertex; those without a usable outline return None."""
    vertices = []
    for line in text.splitlines():
        try:
            lon, lat = map(float, line.split())
        except ValueError:
            continue
        vertices.append((lon, lat))
    if len(vertices) < 3:
        return None
    lons, lats = zip(*vertices, strict=True)
    return (min(lons), min(lats), max(lons), max(lats))


def crawl(workers: int = 6) -> dict:
    throttle = Throttle()
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:

        def text(url: str) -> str:
            for attempt in range(4):
                time.sleep(attempt * 5)
                throttle.wait()
                try:
                    resp = client.get(url)
                except httpx.HTTPError:
                    continue
                return resp.text if resp.status_code == 200 else ""
            return ""

        def frame_entry(track: int, frame: str) -> dict | None:
            base = f"{ARCHIVE}/{track}/{frame}"
            box = parse_poly(text(f"{base}/metadata/{frame}-poly.txt"))
            epochs = parse_epochs(text(f"{base}/epochs/"))
            if box is None or not epochs:
                return None
            return {
                "id": frame,
                "track": track,
                "bbox": [round(v, 3) for v in box],
                "first_epoch": epochs[0],
                "last_epoch": epochs[-1],
            }

        tracks = sorted({int(t) for t in _TRACK.findall(text(f"{ARCHIVE}/"))})
        with ThreadPoolExecutor(workers) as pool:
            listings = pool.map(lambda t: (t, parse_frames(text(f"{ARCHIVE}/{t}/"))), tracks)
            jobs = [(t, f) for t, frames in listings for f in frames]
            entries = list(pool.map(lambda job: frame_entry(*job), jobs))
    frames = [e for e in entries if e is not None]
    return {"crawled": date.today().isoformat(), "archive": ARCHIVE, "frames": frames}


def main() -> None:
    index = crawl()
    FRAME_INDEX.parent.mkdir(parents=True, exist_ok=True)
    # One line per key, so the crawl date can change without touching the line of frames.
    lines = [f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'))}" for k, v in index.items()]
    FRAME_INDEX.write_text("{" + ",\n".join(lines) + "}\n", encoding="utf-8")
    print(f"{len(index['frames'])} frames written to {FRAME_INDEX}")


if __name__ == "__main__":
    main()
