"""Build a measured ground-motion scene from real LiCSAR interferograms.

A scene is one city or district measured from two viewing geometries. For each geometry
this reads the unwrapped interferograms over the area, averages them onto a common grid,
removes the height-dependent part of the atmosphere and the east-west ramp, references them to the ground around
a GNSS station and inverts the pair network into a displacement series (lithos_core.sbas).
The two geometries are then combined into vertical and east motion, and the vertical is
tied to the station's measured rate. Every verdict is held against four other ways of
processing the same data, and other stations check the result.

The result is written to data/scenes/<slug> and served by the licsar adapter. Every value
derives from the archive's interferograms and GNSS rates, through the corrections above. Products already read are kept in data/cache, so a rebuild only asks the archive for
what is new. Needs the `scenes` extra. Run:
    python -m lithos_ingest.scene bologna
"""

from __future__ import annotations

import argparse
import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
from lithos_core import stats
from lithos_core.anomaly import analyse_point
from lithos_core.sbas import (
    decompose_vertical_east,
    find_triplets,
    invert_network,
    phase_to_los_mm,
)
from lithos_core.schema import (
    AnomalyType,
    MeasurementPoint,
    TimeSeries,
    TimeSeriesSample,
)

from lithos_ingest import gnss
from lithos_ingest import licsar_archive as archive
from lithos_ingest.base import BBox, data_dir

CELL_DEG = 0.004  # about 400 m at mid latitudes
MIN_COHERENCE = 0.15  # per pixel, per interferogram
MIN_CELL_FILL = 0.25  # share of a cell's pixels that must survive that mask
MIN_PAIR_SHARE = 0.3  # share of a cell's pairs that must have data
MIN_EPOCH_SHARE = 0.7  # share of the solved window's dates a cell must reach
MIN_SCENE_SHARE = 0.5  # share of cells that must be solved for a date to count
MIN_MEAN_COHERENCE = 0.4  # below this, rates scatter more; the cause is open, see docs/coverage.md
MAX_RESIDUAL_MM = 3.0  # network residual above this means unreliable phase
MAX_HEIGHT_M = 250.0  # above this, stratified atmosphere outweighs the signal
MAX_NEIGHBOUR_GAP = 8.0  # mm/yr from the local median marks a lone outlier
MAX_INTERVAL = 5.0  # mm/yr half-width of the trend's 95% interval; wider is noise
MAX_EAST_MM_YR = 8.0  # sideways motion this fast on built-up ground marks a bad solve
MAX_PAIR_DAYS = 60  # the longest pairs read; the 48 and 60 day ones bridge network gaps
MAX_INTERPOLATE_DAYS = 60  # a date is only read across a gap this short
STATION_RADIUS_DEG = 0.012  # about 1 km: the ground around the tie station
NEAR_STATION_KM = 1.5  # scene cells within this speak for a station
EAST_CHECK = "MEDI"  # the station that decides whether the east of a scene can be trusted
CHECK_RADIUS_KM = 4.5  # if none are, the nearest cells within this, flagged by their distance
REFERENCE_MAX_HEIGHT_M = 120.0
ATMOSPHERE_MIN_CELLS = 30
ATMOSPHERE_MIN_RELIEF_M = 40.0  # no fit without this spread of heights


@dataclass(frozen=True)
class Variant:
    """One way of processing a scene. The robustness test varies these."""

    name: str
    reference_lonlat: tuple[float, float] | None = None  # None: the spec's station
    remove_ramp: bool = True
    min_pair_days: int = 0


@dataclass(frozen=True)
class SceneSpec:
    slug: str
    name: str
    bbox: BBox
    ascending: str
    descending: str
    start: date
    reference_station: str  # GNSS station inside the scene that fixes the datum
    reference_lonlat: tuple[float, float]
    check_stations: dict[str, tuple[float, float]]  # not used in the tie
    atmosphere: BBox  # ground with relief and little motion, for the height fit
    variants: tuple[Variant, ...] = ()  # the robustness test
    relative_east_of: float | None = None  # past this longitude GNSS contradicts the datum


SCENES = {
    "bologna": SceneSpec(
        slug="bologna",
        name="Bologna, Italy",
        bbox=BBox(11.18, 44.40, 11.68, 44.60),
        ascending="117A_04454_131312",
        descending="095D_04589_131313",
        start=date(2021, 10, 1),
        reference_station="BOLG",
        reference_lonlat=(11.3568, 44.5002),
        check_stations={"BLGN": (11.3506, 44.5110), "MEDI": (11.6468, 44.5200)},
        atmosphere=BBox(11.18, 44.40, 11.68, 44.48),
        relative_east_of=11.45,
        variants=(
            Variant("reference moved 2 km", reference_lonlat=(11.3818, 44.5002)),
            Variant("reference at BOLO", reference_lonlat=(11.3288, 44.4876)),
            Variant("no ramp removal", remove_ramp=False),
            Variant("no pairs under 24 days", min_pair_days=24),
        ),
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

    def near(self, lon: float, lat: float, radius: float = STATION_RADIUS_DEG) -> np.ndarray:
        lons, lats = np.meshgrid(self.lons, self.lats)
        return np.hypot((lons - lon) * np.cos(np.radians(lat)), lats - lat) <= radius


@dataclass
class Geometry:
    """One viewing geometry on the common grid."""

    frame: str
    epochs: list[date]
    los_mm: np.ndarray  # (epochs, rows, cols)
    residual_mm: np.ndarray
    components: np.ndarray
    rejected: np.ndarray
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


def _fetch(frame: str, spec: SceneSpec, workers: int = 4) -> tuple[list[archive.Pair], Path]:
    """Read the frame's products into the cache. Only what is missing touches the archive,
    at the reader's rate limit, however many workers share it."""
    cache = data_dir() / "cache" / "licsar" / spec.slug / frame
    cache.mkdir(parents=True, exist_ok=True)
    reader = archive.Reader(spec.bbox)
    base = archive.frame_url(frame)

    meta_path = cache / "metadata.npz"
    if not meta_path.exists():
        meta: dict[str, np.ndarray] = {}
        for key in ("E", "U", "hgt"):
            product = reader.read(f"{base}/metadata/{frame}.geo.{key}.tif")
            if product is None:
                raise RuntimeError(f"{frame}: the {key} product is missing from the archive")
            meta[key] = product[0]
            meta["transform"] = np.array(product[1])
        np.savez_compressed(meta_path, **meta)  # type: ignore[arg-type]

    pairs = [
        p
        for p in archive.list_pairs(frame)
        if p.first >= spec.start and p.days <= MAX_PAIR_DAYS
    ]

    def read_pair(pair: archive.Pair) -> None:
        path = cache / f"{pair.name}.npz"
        if path.exists():
            return
        try:
            unw = reader.read(f"{base}/interferograms/{pair.name}/{pair.name}.geo.unw.tif")
            coh = reader.read(f"{base}/interferograms/{pair.name}/{pair.name}.geo.cc.tif")
        except OSError:  # a refused or failed read may work next time, so it is not recorded
            return
        if unw is None or coh is None:
            path.with_suffix(".missing").touch()
            return
        np.savez_compressed(path, unw=unw[0].astype("float32"), cc=coh[0])

    todo = [p for p in pairs if not (cache / f"{p.name}.missing").exists()]
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(read_pair, todo))
    return [p for p in pairs if (cache / f"{p.name}.npz").exists()], cache


def _remove_long_wavelength_delay(
    phase: np.ndarray,
    height: np.ndarray,
    lons: np.ndarray,
    mask: np.ndarray,
    reference_height: float,
    remove_ramp: bool = True,
) -> None:
    """Per interferogram, fit phase against height and longitude over `mask` and remove
    both terms: the stratified atmosphere, and the east-west ramp that atmosphere and orbit
    errors leave across a scene. The mask keeps the fit off subsiding ground, where motion
    would pose as atmosphere, and along the scene, so a ramp is not fitted to the plain."""
    usable = mask & np.isfinite(height)
    west = float(lons[0, 0])
    for k in range(phase.shape[0]):
        cells = usable & np.isfinite(phase[k])
        if cells.sum() < ATMOSPHERE_MIN_CELLS:
            continue
        h, x, y = height[cells], lons[cells], phase[k][cells]
        if np.percentile(h, 90) - np.percentile(h, 10) < ATMOSPHERE_MIN_RELIEF_M:
            continue
        design = np.column_stack([h - reference_height, x - west, np.ones_like(h)])
        coef = np.linalg.lstsq(design, y, rcond=None)[0]
        misfit = y - design @ coef
        within = np.abs(misfit) < 2.5 * misfit.std()
        coef = np.linalg.lstsq(design[within], y[within], rcond=None)[0]
        phase[k] -= coef[0] * (np.nan_to_num(height, nan=reference_height) - reference_height)
        if remove_ramp:
            phase[k] -= coef[1] * (lons - west)


@dataclass
class Stack:
    """One frame's interferograms on the common grid, before any correction."""

    frame: str
    pairs: list[archive.Pair]
    phase: np.ndarray  # (pairs, rows, cols)
    coherence: np.ndarray
    height_m: np.ndarray
    unit_east: float
    unit_up: float


def load_stack(frame: str, spec: SceneSpec, grid: Grid) -> Stack:
    pairs, cache = _fetch(frame, spec)
    if not pairs:
        raise RuntimeError(f"{frame}: no readable interferograms since {spec.start}")
    with np.load(cache / "metadata.npz") as stored:
        meta = {k: stored[k] for k in stored.files}
    ids = _cell_ids(grid, tuple(meta["transform"]), meta["hgt"].shape)

    used: list[archive.Pair] = []
    stacks: list[np.ndarray] = []
    cohs: list[np.ndarray] = []
    for pair in pairs:
        with np.load(cache / f"{pair.name}.npz") as stored:
            unw, coh = stored["unw"], stored["cc"]
        if unw.shape != ids.shape or coh.shape != ids.shape:
            continue
        coherence = coh / 255.0
        unw[(unw == 0) | (coherence < MIN_COHERENCE)] = np.nan
        used.append(pair)
        stacks.append(_cell_mean(unw, ids, grid, MIN_CELL_FILL))
        cohs.append(_cell_mean(coherence, ids, grid))

    def unit(key: str) -> float:
        values = meta[key].astype(float)
        return float(np.mean(values[np.isfinite(values) & (values != 0)]))

    return Stack(
        frame,
        used,
        np.stack(stacks),
        np.nanmean(np.stack(cohs), axis=0),
        _cell_mean(meta["hgt"].astype(float), ids, grid),
        unit("E"),
        unit("U"),
    )


def solve_geometry(
    stack: Stack, spec: SceneSpec, grid: Grid, variant: Variant, only: np.ndarray | None = None
) -> Geometry:
    """Correct, reference and invert one frame. `only` limits the inversion to some cells."""
    chosen = [i for i, p in enumerate(stack.pairs) if p.days >= variant.min_pair_days]
    used = [stack.pairs[i] for i in chosen]
    phase = stack.phase[chosen].copy()
    height = stack.height_m

    lon, lat = variant.reference_lonlat or spec.reference_lonlat
    in_ref = grid.near(lon, lat) & (height <= REFERENCE_MAX_HEIGHT_M)
    lons, lats = np.meshgrid(grid.lons, grid.lats)
    box = spec.atmosphere
    low_motion = (
        (lons >= box.min_lon) & (lons <= box.max_lon) & (lats >= box.min_lat) & (lats <= box.max_lat)
    )
    _remove_long_wavelength_delay(
        phase,
        height,
        lons,
        low_motion,
        float(np.nanmedian(height[in_ref])),
        variant.remove_ramp,
    )

    # Tie every interferogram to the ground around the station, so an offset common to the
    # scene cancels. Atmosphere that varies across it does not, beyond the two terms above.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # a pair with no reference stays NaN
        phase -= np.nanmedian(phase[:, in_ref], axis=1)[:, None, None]
    los = phase_to_los_mm(phase)

    epochs = sorted({d for p in used for d in (p.first, p.second)})
    index = {d: i for i, d in enumerate(epochs)}
    links = np.array([[index[p.first], index[p.second]] for p in used])
    triplets = find_triplets(links)

    series = np.full((len(epochs), *grid.shape), np.nan)
    residual = np.full(grid.shape, np.nan)
    components = np.zeros(grid.shape, dtype=int)
    rejected = np.zeros(grid.shape, dtype=int)
    for r, c in np.ndindex(*grid.shape):
        if only is not None and not only[r, c]:
            continue
        cell = los[:, r, c]
        if np.isfinite(cell).mean() < MIN_PAIR_SHARE:
            continue
        solved = invert_network(links, cell.copy(), len(epochs), triplets)
        series[:, r, c] = solved.displacement_mm
        residual[r, c] = solved.residual_rms_mm
        components[r, c] = solved.components
        rejected[r, c] = solved.pairs_rejected

    return Geometry(
        stack.frame,
        epochs,
        series,
        residual,
        components,
        rejected,
        stack.coherence,
        height,
        stack.unit_east,
        stack.unit_up,
    )


def _at(dates: list[date], target: list[date], series: np.ndarray) -> np.ndarray:
    """One cell's series read at the target dates, by straight lines between solved dates.
    Dates outside the solved span, or inside a long gap, stay NaN; nothing is extended."""
    ok = np.isfinite(series)
    out = np.full(len(target), np.nan)
    if ok.sum() < 2:
        return out
    x = np.array([d.toordinal() for d, k in zip(dates, ok, strict=True) if k], dtype=float)
    y = series[ok]
    t = np.array([d.toordinal() for d in target], dtype=float)
    after = np.searchsorted(x, t)
    inside = (after > 0) & (after < x.size)
    exact = np.isin(t, x)
    gap = np.zeros_like(t)
    gap[inside] = x[after[inside]] - x[after[inside] - 1]
    readable = exact | (inside & (gap <= MAX_INTERPOLATE_DAYS))
    out[readable] = np.interp(t[readable], x, y)
    return out


def _secular(epochs: list[date], y: np.ndarray) -> stats.TrendResult:
    """Trend of a series with its annual cycle removed, so a window that starts in autumn
    and ends in spring does not pass a season off as motion."""
    days = np.array([(d - epochs[0]).days for d in epochs], dtype=float)
    return stats.robust_trend(days, stats.harmonic_decompose(days, y).deseasonalised)


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


def _vertical_east(
    asc: Geometry, desc: Geometry, epochs: list[date], r: int, c: int
) -> tuple[np.ndarray, np.ndarray]:
    """Vertical and east series of one cell on the given dates, from the first solved date."""
    y_a = _at(asc.epochs, epochs, asc.los_mm[:, r, c])
    y_d = _at(desc.epochs, epochs, desc.los_mm[:, r, c])
    ok = np.isfinite(y_a) & np.isfinite(y_d)
    up = np.full(len(epochs), np.nan)
    east = up.copy()
    if ok.sum() >= 3:
        u, e = decompose_vertical_east(
            y_a[ok], y_d[ok], (asc.unit_east, asc.unit_up), (desc.unit_east, desc.unit_up)
        )
        up[ok] = u - u[0]
        east[ok] = e - e[0]
    return up, east


def _km_between(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    return float(np.hypot((lon_a - lon_b) * np.cos(np.radians(lat_a)), lat_a - lat_b) * 111.2)


def _station_checks(
    spec: SceneSpec, epochs: list[date], points: list[dict], series: dict
) -> list[dict]:
    """Same-date double differences: scene cells near a station minus scene cells near the
    tie station, against the same difference of the two GNSS records. The tie cancels, and
    an annual term is fitted, so what is left is the scene's error between the two places."""
    tie_text = gnss.fetch_text(spec.reference_station)
    tie_days, tie_up = gnss.parse_days(tie_text)
    ref_lon, ref_lat = spec.reference_lonlat
    grid = np.array([[np.nan if v is None else v for v in series[p["id"]]] for p in points])

    def around(lon: float, lat: float) -> tuple[np.ndarray, np.ndarray]:
        km = np.array([_km_between(lon, lat, p["lon"], p["lat"]) for p in points])
        near = km <= NEAR_STATION_KM
        return (near if near.any() else km <= CHECK_RADIUS_KM), km

    ref_cells, _ = around(ref_lon, ref_lat)
    ref_series = np.nanmedian(grid[ref_cells], axis=0)
    checks: list[dict] = []
    for station, (lon, lat) in spec.check_stations.items():
        entry: dict = {"station": station, "provider": gnss.PROVIDERS.get(station, "unknown")}
        checks.append(entry)
        days, up = gnss.parse_days(gnss.fetch_text(station))
        cells, km = around(lon, lat)
        if not cells.any():
            entry["note"] = "no scene cells near the station"
            continue
        scene_dd = np.nanmedian(grid[cells], axis=0) - ref_series
        gnss_dd = np.full(len(epochs), np.nan)
        for k, d in enumerate(epochs):
            ordinal = d.toordinal()
            i, j = np.searchsorted(days, ordinal), np.searchsorted(tie_days, ordinal)
            if i < days.size and j < tie_days.size and days[i] == ordinal and tie_days[j] == ordinal:
                gnss_dd[k] = up[i] - tie_up[j]
        ok = np.isfinite(scene_dd) & np.isfinite(gnss_dd)
        used = [d for d, k in zip(epochs, ok, strict=True) if k]
        if len(used) < 10 or (used[-1] - used[0]).days < 300:
            entry["note"] = "the records share too few dates"
            continue
        scene_rate = _secular(used, scene_dd[ok]).slope_mm_yr
        gnss_rate = _secular(used, gnss_dd[ok]).slope_mm_yr
        entry.update(
            km=[round(float(km[cells].min()), 1), round(float(km[cells].max()), 1)],
            cells=int(cells.sum()),
            dates=len(used),
            first=used[0].isoformat(),
            last=used[-1].isoformat(),
            scene_minus_tie=round(scene_rate, 2),
            gnss_minus_tie=round(gnss_rate, 2),
            difference=round(scene_rate - gnss_rate, 2),
        )
    return checks


def _caveat(spec: SceneSpec, checks: list[dict], tie_rate: float) -> str:
    """The one sentence that travels with the data, built from the station checks."""
    parts = [f"Tied to GNSS only at {spec.reference_station}."]
    for c in checks:
        if "difference" not in c:
            continue
        if c["station"] == EAST_CHECK:
            scene = tie_rate + c["scene_minus_tie"]
            station = tie_rate + c["gnss_minus_tie"]
            parts.append(
                f"At {c['station']} the scene reads {scene:+.1f} mm per year where GNSS reads "
                f"{station:+.1f}, the opposite sign, from cells {c['km'][0]} to {c['km'][1]} km away."
            )
        else:
            parts.append(f"At {c['station']} they agree within {abs(c['difference']):.1f} mm per year.")
    if spec.relative_east_of is not None:
        parts.append(f"East of {spec.relative_east_of}E values are relative only.")
    return " ".join(parts)


def _peak(points: list[dict]) -> dict:
    """The fastest sinking: one cell, and the median of the worst 1.5 km patch, which leans
    less on any single cell."""
    velocity = np.array([p["vertical_velocity"] for p in points])
    lon = np.array([p["lon"] for p in points])
    lat = np.array([p["lat"] for p in points])
    patch = 0.0
    for i in range(len(points)):
        near = np.hypot((lon - lon[i]) * 0.71, lat - lat[i]) <= 1.5 / 111.2
        if near.sum() >= 6:
            patch = min(patch, float(np.median(velocity[near])))
    return {"cell_mm_yr": round(float(velocity.min()), 1), "patch_mm_yr": round(patch, 1)}


def _class_of(
    pid: str, epochs: list[date], up: np.ndarray, rate: float, coherence: float
) -> AnomalyType | None:
    ok = np.isfinite(up)
    if ok.sum() < 3:
        return None
    samples = [
        TimeSeriesSample(date=d, displacement_mm=float(v))
        for d, v in zip(epochs, up, strict=True)
        if np.isfinite(v)
    ]
    point = MeasurementPoint(
        id=pid,
        lon=0.0,
        lat=0.0,
        vertical_velocity=rate,
        coherence=coherence,
        time_series=TimeSeries(point_id=pid, samples=samples),
    )
    flag = analyse_point(point).primary_flag
    return flag.type if flag else None


def combine(
    spec: SceneSpec,
    grid: Grid,
    asc: Geometry,
    desc: Geometry,
    variants: dict[str, tuple[Geometry, Geometry]] | None = None,
) -> dict:
    """Vertical and east series from both geometries, over the dates they both solve. Each
    point's verdict is then held against the variants, which are the same scene processed
    differently."""
    base = asc if len(asc.epochs) <= len(desc.epochs) else desc
    n_rows, n_cols = grid.shape
    counts = {"cells": n_rows * n_cols}

    def drop(reason: str, mask: np.ndarray, within: np.ndarray) -> np.ndarray:
        counts[reason] = int((within & mask).sum())
        return within & ~mask

    alive = drop(
        "low_coherence", ~(_mean_coherence(asc, desc) >= MIN_MEAN_COHERENCE), np.ones(grid.shape, bool)
    )
    alive = drop("no_data", ~(np.isfinite(asc.residual_mm) & np.isfinite(desc.residual_mm)), alive)
    alive = drop(
        "poor_network_fit",
        (asc.residual_mm > MAX_RESIDUAL_MM) | (desc.residual_mm > MAX_RESIDUAL_MM),
        alive,
    )
    alive = drop("high_ground", ~(asc.height_m <= MAX_HEIGHT_M), alive)

    vertical = np.full((len(base.epochs), n_rows, n_cols), np.nan)
    east = vertical.copy()
    for r, c in zip(*np.nonzero(alive), strict=True):
        vertical[:, r, c], east[:, r, c] = _vertical_east(asc, desc, base.epochs, r, c)

    # The window is what got solved, not where the frames happen to end. It is judged on
    # the cells that hold most dates, so a field that decorrelates in winter has no vote.
    usable = np.isfinite(vertical).mean(axis=0) >= MIN_EPOCH_SHARE
    share = np.isfinite(vertical[:, usable]).mean(axis=1) if usable.any() else np.zeros(1)
    solved_dates = np.flatnonzero(share >= MIN_SCENE_SHARE)
    if solved_dates.size < 3:
        raise RuntimeError(f"{spec.slug}: too few dates solved across the scene")
    first, last = int(solved_dates[0]), int(solved_dates[-1])
    epochs = base.epochs[first : last + 1]
    vertical = vertical[first : last + 1]
    east = east[first : last + 1]
    alive = drop("too_few_dates", np.isfinite(vertical).mean(axis=0) < MIN_EPOCH_SHARE, alive)
    counts["split_network_kept"] = int(
        (alive & ((asc.components > 1) | (desc.components > 1))).sum()
    )

    # The datum: motion relative to the station, plus the station's measured rate.
    tie = gnss.fit_rate(
        spec.reference_station,
        gnss.fetch_text(spec.reference_station),
        epochs[0],
        epochs[-1],
    )
    if tie is None:
        raise RuntimeError(f"{spec.reference_station} does not cover {epochs[0]} to {epochs[-1]}")
    years = np.array([(d - epochs[0]).days for d in epochs]) / stats.DAYS_PER_YEAR

    def tied(up: np.ndarray) -> np.ndarray:
        return up + tie.rate_mm_yr * years

    velocity = np.full(grid.shape, np.nan)
    for r, c in zip(*np.nonzero(alive), strict=True):
        vertical[:, r, c] = tied(vertical[:, r, c])
        ok = np.isfinite(vertical[:, r, c])
        dates = [e for e, k in zip(epochs, ok, strict=True) if k]
        velocity[r, c] = _secular(dates, vertical[ok, r, c]).slope_mm_yr
    smoothed = _drop_lone_outliers(velocity)
    alive = drop("lone_outlier", np.isfinite(velocity) & ~np.isfinite(smoothed), alive)

    points: list[dict] = []
    series: dict[str, list[float | None]] = {}
    cells: list[tuple[int, int]] = []
    reasons = {"wide_interval": 0, "sideways": 0}
    for r, c in zip(*np.nonzero(alive), strict=True):
        ok = np.isfinite(vertical[:, r, c])
        dates = [e for e, k in zip(epochs, ok, strict=True) if k]
        up = _secular(dates, vertical[ok, r, c])
        if up.ci95_half_width_mm_yr > MAX_INTERVAL:
            reasons["wide_interval"] += 1
            continue
        ew = _secular(dates, east[ok, r, c])
        if abs(ew.slope_mm_yr) > MAX_EAST_MM_YR:
            reasons["sideways"] += 1
            continue
        los = _at(desc.epochs, dates, desc.los_mm[:, r, c])
        los_ok = np.isfinite(los)
        los_trend = _secular([d for d, k in zip(dates, los_ok, strict=True) if k], los[los_ok])
        pid = f"{spec.slug}-{len(points):04d}"
        coherence = round(float(_mean_coherence(asc, desc)[r, c]), 2)
        points.append(
            {
                "id": pid,
                "lon": round(float(grid.lons[c]), 5),
                "lat": round(float(grid.lats[r]), 5),
                "height_m": round(float(asc.height_m[r, c]), 1),
                "vertical_velocity": round(up.slope_mm_yr, 2),
                "horizontal_velocity": round(ew.slope_mm_yr, 2),
                "los_velocity": round(los_trend.slope_mm_yr, 2),
                "velocity_uncertainty": round(up.ci95_half_width_mm_yr, 2),
                "coherence": coherence,
                "quality": coherence,
                "source": "licsar",
                "product": f"LiCSAR small-baseline vertical ({asc.frame} + {desc.frame})",
                "processing_window": f"{dates[0]:%Y-%m} to {dates[-1]:%Y-%m}",
                "reference": spec.reference_station,
            }
        )
        series[pid] = [None if np.isnan(v) else round(float(v), 2) for v in vertical[:, r, c]]
        cells.append((int(r), int(c)))
    counts.update(reasons)

    # The robustness test: a verdict stands only if every variant gives the same class.
    held = np.ones(len(points), dtype=bool)
    robustness: dict[str, dict] = {}
    base_classes = [
        _class_of(
            p["id"],
            epochs,
            vertical[:, r, c],
            p["vertical_velocity"],
            p["coherence"],
        )
        for p, (r, c) in zip(points, cells, strict=True)
    ]
    for name, (var_asc, var_desc) in (variants or {}).items():
        same = np.zeros(len(points), dtype=bool)
        rates = []
        for i, (p, (r, c)) in enumerate(zip(points, cells, strict=True)):
            up = tied(_vertical_east(var_asc, var_desc, epochs, r, c)[0])
            ok = np.isfinite(up)
            rate = float("nan")
            if ok.sum() >= 10:
                rate = _secular(
                    [e for e, k in zip(epochs, ok, strict=True) if k], up[ok]
                ).slope_mm_yr
                same[i] = _class_of(p["id"], epochs, up, rate, p["coherence"]) == base_classes[i]
            rates.append(rate)
        held &= same
        finite = [
            {**p, "vertical_velocity": v}
            for p, v in zip(points, rates, strict=True)
            if np.isfinite(v)
        ]
        robustness[name] = {
            "same_verdict": int(same.sum()),
            "peak": _peak(finite),
            "median_shift_mm_yr": round(
                float(np.nanmedian(np.array(rates) - [p["vertical_velocity"] for p in points])), 2
            ),
        }
    if variants:
        for p, ok in zip(points, held, strict=True):
            p["verdict_robust"] = bool(ok)

    start, end = epochs[0], epochs[-1]
    checks = _station_checks(spec, epochs, points, series)
    caveat = _caveat(spec, checks, tie.rate_mm_yr)
    east_check = next((c for c in checks if c["station"] == EAST_CHECK and "difference" in c), None)
    if spec.relative_east_of is not None and east_check:
        note = (
            f"GNSS station {EAST_CHECK}, east of here, disagrees by about "
            f"{abs(east_check['difference']):.0f} mm per year, with the opposite sign, so do not "
            "read this as absolute motion."
        )
        for p in points:
            if p["lon"] > spec.relative_east_of:
                p["datum_note"] = note
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
        "datum": {**asdict(tie), "provider": gnss.PROVIDERS.get(tie.station, "unknown")},
        "checks": checks,
        "caveat": caveat,
        "relative_east_of": spec.relative_east_of,
        "peak": _peak(points),
        "robustness": robustness,
        "verdicts_held": int(held.sum()) if variants else None,
        "filters": counts,
        "note": (
            f"Measured with Sentinel-1 from frames {asc.frame} and {desc.frame}, COMET LiCSAR "
            f"interferograms, {start:%B %Y} to {end:%B %Y}. Vertical motion is tied to GNSS "
            f"station {spec.reference_station}."
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


def _mean_coherence(asc: Geometry, desc: Geometry) -> np.ndarray:
    return np.nanmean(np.stack([asc.coherence, desc.coherence]), axis=0)


def build(spec: SceneSpec) -> dict:
    grid = Grid.over(spec.bbox)
    asc_stack = load_stack(spec.ascending, spec, grid)
    desc_stack = load_stack(spec.descending, spec, grid)
    only = np.nanmean(np.stack([asc_stack.coherence, desc_stack.coherence]), axis=0)
    only = only >= MIN_MEAN_COHERENCE

    def solve(variant: Variant) -> tuple[Geometry, Geometry]:
        return (
            solve_geometry(asc_stack, spec, grid, variant, only),
            solve_geometry(desc_stack, spec, grid, variant, only),
        )

    asc, desc = solve(Variant("base"))
    return combine(spec, grid, asc, desc, {v.name: solve(v) for v in spec.variants})


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a scene from LiCSAR interferograms.")
    parser.add_argument("slug", choices=sorted(SCENES))
    scene = build(SCENES[parser.parse_args().slug])
    out = write(scene)
    print(f"{scene['meta']['point_count']} points, {scene['meta']['epochs']} epochs: {out}")


if __name__ == "__main__":
    main()
