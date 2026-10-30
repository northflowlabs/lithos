"""Build a measured ground-motion scene from real LiCSAR interferograms.

A scene is one city or district measured from two viewing geometries. For each geometry
this reads the unwrapped interferograms over the area, averages them onto a common grid,
references them to stable ground and inverts the pair network into a displacement series
(lithos_core.sbas). The two geometries are then combined into vertical and east motion.

The result is written to data/scenes/<slug> and served by the licsar adapter. Nothing in a
scene is modelled: every value derives from the archive's interferograms. Needs the
`scenes` extra. Run:
    python -m lithos_ingest.scene bologna
"""

from __future__ import annotations

import argparse
import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
from lithos_core import stats
from lithos_core.sbas import decompose_vertical_east, invert_network, phase_to_los_mm

from lithos_ingest import licsar_archive as archive
from lithos_ingest.base import BBox, data_dir

CELL_DEG = 0.004  # about 400 m at mid latitudes
MIN_COHERENCE = 0.15  # per pixel, per interferogram
MIN_CELL_FILL = 0.25  # share of a cell's pixels that must survive that mask
MIN_PAIR_SHARE = 0.3  # share of a cell's pairs that must have data
MIN_EPOCH_SHARE = 0.6  # share of a cell's epochs the network must reach
MAX_RESIDUAL_MM = 3.0  # network residual above this means unreliable phase
MAX_HEIGHT_M = 250.0  # above this, stratified atmosphere outweighs the signal
MAX_NEIGHBOUR_GAP = 8.0  # mm/yr from the local median marks a lone outlier
MAX_UNCERTAINTY = 5.0  # mm/yr half-width of the trend interval; wider is noise
MAX_EAST_MM_YR = 8.0  # sideways motion this fast on built-up ground marks a bad solve
PAIR_SEPARATIONS = (12, 24, 36)  # days


@dataclass(frozen=True)
class SceneSpec:
    slug: str
    name: str
    bbox: BBox
    ascending: str
    descending: str
    start: date
    reference: BBox  # stable ground every interferogram is tied to
    reference_label: str


SCENES = {
    "bologna": SceneSpec(
        slug="bologna",
        name="Bologna, Italy",
        bbox=BBox(11.18, 44.40, 11.60, 44.60),
        ascending="117A_04454_131312",
        descending="095D_04589_131313",
        start=date(2021, 10, 1),
        reference=BBox(11.20, 44.42, 11.42, 44.47),
        reference_label="the foothills south of the city",
    )
}


@dataclass
class Grid:
    lons: np.ndarray
    lats: np.ndarray

    @classmethod
    def over(cls, bbox: BBox) -> Grid:
        lons = np.arange(bbox.min_lon + CELL_DEG / 2, bbox.max_lon, CELL_DEG)
        lats = np.arange(bbox.min_lat + CELL_DEG / 2, bbox.max_lat, CELL_DEG)
        return cls(lons, lats)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.lats.size, self.lons.size)


@dataclass
class Geometry:
    """One viewing geometry on the common grid."""

    frame: str
    epochs: list[date]
    los_mm: np.ndarray  # (epochs, rows, cols)
    residual_mm: np.ndarray
    coherence: np.ndarray
    height_m: np.ndarray
    unit_east: float
    unit_up: float


def _cell_ids(
    grid: Grid, transform: tuple[float, float, float, float], shape: tuple[int, int]
) -> np.ndarray:
    """Grid cell of every pixel; pixels outside the grid get -1."""
    west, north, dx, dy = transform
    origin_lon = grid.lons[0] - CELL_DEG / 2
    origin_lat = grid.lats[0] - CELL_DEG / 2
    cols = np.floor((west + (np.arange(shape[1]) + 0.5) * dx - origin_lon) / CELL_DEG).astype(int)
    rows = np.floor((north + (np.arange(shape[0]) + 0.5) * dy - origin_lat) / CELL_DEG).astype(int)
    rows_2d, cols_2d = np.meshgrid(rows, cols, indexing="ij")
    inside = (rows_2d >= 0) & (rows_2d < grid.shape[0]) & (cols_2d >= 0) & (cols_2d < grid.shape[1])
    return np.where(inside, rows_2d * grid.shape[1] + cols_2d, -1)


def _cell_mean(
    values: np.ndarray, ids: np.ndarray, grid: Grid, min_fill: float = 0.0
) -> np.ndarray:
    """Mean of the finite pixels in each grid cell, NaN where too few survive."""
    size = grid.shape[0] * grid.shape[1]
    good = np.isfinite(values) & (ids >= 0)
    totals = np.bincount(ids[good], weights=values[good], minlength=size)
    counts = np.bincount(ids[good], minlength=size).astype(float)
    pixels = np.bincount(ids[ids >= 0], minlength=size).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        means = totals / counts
    means[counts < np.maximum(1.0, min_fill * pixels)] = np.nan
    return means.reshape(grid.shape)


def fetch_geometry(frame: str, spec: SceneSpec, grid: Grid, workers: int = 4) -> Geometry:
    """Read one frame's interferograms over the scene and solve its time series."""
    pairs = [
        p
        for p in archive.list_pairs(frame)
        if p.first >= spec.start and p.days in PAIR_SEPARATIONS
    ]
    reader = archive.Reader(spec.bbox, requests_per_second=20)
    base = archive.frame_url(frame)

    meta: dict[str, np.ndarray] = {}
    transform = None
    for key in ("E", "U", "hgt"):
        product = reader.read(f"{base}/metadata/{frame}.geo.{key}.tif")
        if product is None:
            raise RuntimeError(f"{frame}: the {key} product is missing from the archive")
        meta[key], transform = product
    assert transform is not None
    ids = _cell_ids(grid, transform, meta["hgt"].shape)

    def read_pair(pair: archive.Pair) -> tuple[archive.Pair, np.ndarray, np.ndarray] | None:
        name = pair.name
        unw = reader.read(f"{base}/interferograms/{name}/{name}.geo.unw.tif")
        coh = reader.read(f"{base}/interferograms/{name}/{name}.geo.cc.tif")
        if unw is None or coh is None or unw[0].shape != ids.shape or coh[0].shape != ids.shape:
            return None  # some pairs are withheld or incomplete on the archive
        phase = unw[0].astype("float32")
        coherence = coh[0] / 255.0
        phase[(phase == 0) | (coherence < MIN_COHERENCE)] = np.nan
        return pair, _cell_mean(phase, ids, grid, MIN_CELL_FILL), _cell_mean(coherence, ids, grid)

    with ThreadPoolExecutor(workers) as pool:
        results = [r for r in pool.map(read_pair, pairs) if r is not None]
    if not results:
        raise RuntimeError(f"{frame}: no readable interferograms since {spec.start}")

    used = [r[0] for r in results]
    phase = np.stack([r[1] for r in results])
    coherence = np.nanmean(np.stack([r[2] for r in results]), axis=0)

    # Tie every interferogram to the reference ground so atmosphere common to the scene and
    # frame-wide offsets cancel.
    lons, lats = np.meshgrid(grid.lons, grid.lats)
    ref = spec.reference
    in_ref = (
        (lons >= ref.min_lon) & (lons <= ref.max_lon) & (lats >= ref.min_lat) & (lats <= ref.max_lat)
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a pair with no reference stays NaN
        phase -= np.nanmedian(phase[:, in_ref], axis=1)[:, None, None]
    los = phase_to_los_mm(phase)

    epochs = sorted({d for p in used for d in (p.first, p.second)})
    index = {d: i for i, d in enumerate(epochs)}
    links = np.array([[index[p.first], index[p.second]] for p in used])

    series = np.full((len(epochs), *grid.shape), np.nan)
    residual = np.full(grid.shape, np.nan)
    for r, c in np.ndindex(*grid.shape):
        cell = los[:, r, c]
        if np.isfinite(cell).mean() < MIN_PAIR_SHARE:
            continue
        solved = invert_network(links, cell.copy(), len(epochs))
        series[:, r, c] = solved.displacement_mm
        residual[r, c] = solved.residual_rms_mm

    def unit(key: str) -> float:
        values = meta[key].astype(float)
        return float(np.mean(values[np.isfinite(values) & (values != 0)]))

    height = _cell_mean(meta["hgt"].astype(float), ids, grid)
    return Geometry(frame, epochs, series, residual, coherence, height, unit("E"), unit("U"))


def _at(dates: list[date], target: list[date], series: np.ndarray) -> np.ndarray:
    """Linear interpolation of one cell's series onto the target dates."""
    x = np.array([d.toordinal() for d in dates], dtype=float)
    ok = np.isfinite(series)
    if ok.sum() < 2:
        return np.full(len(target), np.nan)
    return np.interp([d.toordinal() for d in target], x[ok], series[ok])


def _trend(epochs: list[date], y: np.ndarray) -> stats.TrendResult:
    days = np.array([(d - epochs[0]).days for d in epochs], dtype=float)
    return stats.robust_trend(days, y)


def _drop_lone_outliers(velocity: np.ndarray) -> np.ndarray:
    """Clear cells that disagree with their neighbourhood. Real motion is spatially smooth."""
    kept = velocity.copy()
    rows, cols = velocity.shape
    for r, c in zip(*np.nonzero(np.isfinite(velocity)), strict=True):
        around = velocity[max(r - 2, 0) : min(r + 3, rows), max(c - 2, 0) : min(c + 3, cols)]
        around = around[np.isfinite(around)]
        if around.size < 5 or abs(velocity[r, c] - np.median(around)) > MAX_NEIGHBOUR_GAP:
            kept[r, c] = np.nan
    return kept


def combine(spec: SceneSpec, grid: Grid, asc: Geometry, desc: Geometry) -> dict:
    """Vertical and east series from both geometries, over the window they share."""
    start = max(asc.epochs[0], desc.epochs[0])
    end = min(asc.epochs[-1], desc.epochs[-1])
    # The sparser geometry sets the dates; the other is interpolated onto them.
    base, other = (asc, desc) if len(asc.epochs) <= len(desc.epochs) else (desc, asc)
    keep = [i for i, d in enumerate(base.epochs) if start <= d <= end]
    epochs = [base.epochs[i] for i in keep]
    n_rows, n_cols = grid.shape

    vertical = np.full((len(epochs), n_rows, n_cols), np.nan)
    east = vertical.copy()
    velocity = np.full(grid.shape, np.nan)
    unit_a = (asc.unit_east, asc.unit_up)
    unit_b = (desc.unit_east, desc.unit_up)

    for r, c in np.ndindex(n_rows, n_cols):
        if not (
            asc.residual_mm[r, c] <= MAX_RESIDUAL_MM
            and desc.residual_mm[r, c] <= MAX_RESIDUAL_MM
            and asc.height_m[r, c] <= MAX_HEIGHT_M
        ):
            continue
        y_base = base.los_mm[keep, r, c]
        if np.isfinite(y_base).mean() < MIN_EPOCH_SHARE:
            continue
        if np.isfinite(other.los_mm[:, r, c]).mean() < MIN_EPOCH_SHARE:
            continue
        ok = np.isfinite(y_base)
        y_other = _at(other.epochs, epochs, other.los_mm[:, r, c])
        y_a, y_d = (y_base, y_other) if base is asc else (y_other, y_base)
        up, ew = decompose_vertical_east(y_a[ok], y_d[ok], unit_a, unit_b)
        vertical[ok, r, c] = up - up[0]
        east[ok, r, c] = ew - ew[0]
        velocity[r, c] = _trend([e for e, k in zip(epochs, ok, strict=True) if k], up).slope_mm_yr

    velocity = _drop_lone_outliers(velocity)

    points: list[dict] = []
    series: dict[str, list[float | None]] = {}
    for r, c in zip(*np.nonzero(np.isfinite(velocity)), strict=True):
        ok = np.isfinite(vertical[:, r, c])
        dates = [e for e, k in zip(epochs, ok, strict=True) if k]
        up = _trend(dates, vertical[ok, r, c])
        if up.uncertainty_mm_yr > MAX_UNCERTAINTY:
            continue
        ew = _trend(dates, east[ok, r, c])
        if abs(ew.slope_mm_yr) > MAX_EAST_MM_YR:
            continue
        los = _trend(dates, _at(desc.epochs, dates, desc.los_mm[:, r, c]))
        pid = f"{spec.slug}-{len(points):04d}"
        coherence = float(np.nanmean([asc.coherence[r, c], desc.coherence[r, c]]))
        points.append(
            {
                "id": pid,
                "lon": round(float(grid.lons[c]), 5),
                "lat": round(float(grid.lats[r]), 5),
                "height_m": round(float(asc.height_m[r, c]), 1),
                "vertical_velocity": round(up.slope_mm_yr, 2),
                "horizontal_velocity": round(ew.slope_mm_yr, 2),
                "los_velocity": round(los.slope_mm_yr, 2),
                "velocity_uncertainty": round(up.uncertainty_mm_yr, 2),
                "coherence": round(coherence, 2),
                "quality": round(coherence, 2),
                "source": "licsar",
                "product": f"LiCSAR small-baseline vertical ({asc.frame} + {desc.frame})",
                "processing_window": f"{start:%Y-%m} to {end:%Y-%m}",
            }
        )
        series[pid] = [None if np.isnan(v) else round(float(v), 2) for v in vertical[:, r, c]]

    b = spec.bbox
    meta = {
        "slug": spec.slug,
        "name": spec.name,
        "source": "licsar",
        "bbox": list(b.as_tuple()),
        "center": [(b.min_lon + b.max_lon) / 2, (b.min_lat + b.max_lat) / 2],
        "window": f"{start:%Y-%m} to {end:%Y-%m}",
        "first_epoch": start.isoformat(),
        "last_epoch": end.isoformat(),
        "built": date.today().isoformat(),
        "frames": [asc.frame, desc.frame],
        "point_count": len(points),
        "epochs": len(epochs),
        "note": (
            f"Measured with Sentinel-1 from frames {asc.frame} and {desc.frame}, COMET LiCSAR "
            f"interferograms, {start:%B %Y} to {end:%B %Y}. Motion is relative to "
            f"{spec.reference_label}."
        ),
    }
    return {
        "meta": meta,
        "dates": [d.isoformat() for d in epochs],
        "points": points,
        "series": series,
    }


def write(scene: dict, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or data_dir() / "scenes" / scene["meta"]["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
            "properties": {k: v for k, v in p.items() if k not in ("lon", "lat")},
        }
        for p in scene["points"]
    ]
    collection = {"type": "FeatureCollection", "features": features}
    (out_dir / "points.geojson").write_text(json.dumps(collection), encoding="utf-8")
    (out_dir / "timeseries.json").write_text(
        json.dumps({"dates": scene["dates"], "series": scene["series"]}), encoding="utf-8"
    )
    (out_dir / "meta.json").write_text(json.dumps(scene["meta"], indent=2), encoding="utf-8")
    return out_dir


def build(spec: SceneSpec) -> dict:
    grid = Grid.over(spec.bbox)
    asc = fetch_geometry(spec.ascending, spec, grid)
    desc = fetch_geometry(spec.descending, spec, grid)
    return combine(spec, grid, asc, desc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a scene from LiCSAR interferograms.")
    parser.add_argument("slug", choices=sorted(SCENES))
    scene = build(SCENES[parser.parse_args().slug])
    out = write(scene)
    print(f"{scene['meta']['point_count']} points, {scene['meta']['epochs']} epochs: {out}")


if __name__ == "__main__":
    main()
