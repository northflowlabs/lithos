"""Deterministic hero scene generator.

Produces the zero-input default view: a subsidence bowl modelled on Bologna, Italy
(a well-documented EGMS subsidence example). The output is cached to data/samples so
the web app and API render in under three seconds with no credentials and no network.

Honesty note: the shipped hero is a SYNTHETIC stand-in, clearly labelled as such in its
metadata (source = "sample-demo"). Run the EGMS adapter with a free Copernicus account
to cache a real EGMS tile in its place. See docs/coverage.md.

Run: python -m lithos_ingest.hero
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# Bologna town centre. The historical subsidence bowl sits to the north and east.
HERO_CENTER_LON = 11.343
HERO_CENTER_LAT = 44.494
BOWL_LON = 11.39  # bowl centre offset to the east-northeast
BOWL_LAT = 44.52
HERO_WINDOW = "2019-2023"

N_EPOCHS = 122  # ~12-day cadence over ~4 years
CADENCE_DAYS = 12
GRID = 26  # 26 x 26 = 676 candidate points before thinning


def _dates() -> list[date]:
    start = date(2019, 1, 1)
    return [start + timedelta(days=i * CADENCE_DAYS) for i in range(N_EPOCHS)]


def generate(seed: int = 7) -> dict:
    """Build the hero scene as a plain dict ready to serialise.

    Returns {meta, dates, points, series} where points is a list of property dicts
    and series maps point_id -> list[float] displacements aligned to dates.
    """
    rng = np.random.default_rng(seed)
    dates = _dates()
    t_years = np.array([(d - dates[0]).days for d in dates]) / 365.25

    lons = np.linspace(11.27, 11.47, GRID)
    lats = np.linspace(44.43, 44.57, GRID)

    points: list[dict] = []
    series: dict[str, list[float]] = {}
    idx = 0

    for la in lats:
        for lo in lons:
            # Distance from the bowl centre, in degrees, shapes the subsidence rate.
            d = np.hypot((lo - BOWL_LON) * np.cos(np.radians(la)), la - BOWL_LAT)
            # Gaussian bowl: up to ~-30 mm/yr at the centre, decaying with distance.
            bowl_rate = -30.0 * np.exp(-(d**2) / (2 * 0.035**2))

            # Coherence falls off in the rural fringe; thin those points out.
            coherence = float(np.clip(0.9 - 1.5 * d + rng.normal(0, 0.05), 0.2, 0.95))
            if coherence < 0.45 and rng.random() < 0.6:
                continue  # honest sparsity at the edges

            pid = f"hero-{idx:04d}"
            idx += 1

            # A pocket of points east of the bowl ACCELERATED after early 2022.
            accelerates = (abs(lo - 11.42) < 0.02) and (abs(la - 44.50) < 0.02)
            seasonal_amp = float(rng.uniform(1.5, 4.0))

            if accelerates:
                onset = 3.0  # ~early 2022
                rate_before = bowl_rate * 0.3
                rate_after = bowl_rate * 1.8 - 6.0
                disp = np.where(
                    t_years <= onset,
                    rate_before * t_years,
                    rate_before * onset + rate_after * (t_years - onset),
                )
                reported_velocity = rate_after
            else:
                disp = bowl_rate * t_years
                reported_velocity = bowl_rate

            disp = disp + seasonal_amp * np.sin(2 * np.pi * t_years)
            disp = disp + rng.normal(0, max(1.0, 4.0 * (1 - coherence)), N_EPOCHS)
            disp = disp - disp[0]  # reference first epoch to zero

            points.append(
                {
                    "id": pid,
                    "lon": round(float(lo), 6),
                    "lat": round(float(la), 6),
                    "vertical_velocity": round(float(reported_velocity), 2),
                    "los_velocity": round(float(reported_velocity * 0.92), 2),
                    "velocity_uncertainty": round(float(0.8 + 2.0 * (1 - coherence)), 2),
                    "coherence": round(coherence, 2),
                    "quality": round(coherence, 2),
                    "source": "sample-demo",
                    "product": "EGMS-Ortho-vertical (synthetic stand-in)",
                    "processing_window": HERO_WINDOW,
                }
            )
            series[pid] = [round(float(v), 2) for v in disp]

    meta = {
        "name": "Bologna subsidence (hero scene)",
        "source": "sample-demo",
        "is_synthetic": True,
        "modelled_on": "Bologna, Italy EGMS subsidence",
        "center": [HERO_CENTER_LON, HERO_CENTER_LAT],
        "bbox": [11.27, 44.43, 11.47, 44.57],
        "window": HERO_WINDOW,
        "point_count": len(points),
        "epochs": N_EPOCHS,
        "note": (
            "Synthetic demonstration scene modelled on the Bologna subsidence bowl so "
            "the app renders offline. Replace with a real EGMS tile via the egms adapter."
        ),
    }

    return {
        "meta": meta,
        "dates": [d.isoformat() for d in dates],
        "points": points,
        "series": series,
    }


def _samples_dir() -> Path:
    # repo_root/data/samples ; this file is packages/ingest/lithos_ingest/hero.py
    return Path(__file__).resolve().parents[3] / "data" / "samples"


def write(scene: dict, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or _samples_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Points as GeoJSON for direct map consumption.
    features = []
    for p in scene["points"]:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                "properties": {k: v for k, v in p.items() if k not in ("lon", "lat")},
            }
        )
    geojson = {
        "type": "FeatureCollection",
        "metadata": scene["meta"],
        "features": features,
    }

    (out_dir / "hero_points.geojson").write_text(json.dumps(geojson), encoding="utf-8")
    (out_dir / "hero_timeseries.json").write_text(
        json.dumps({"dates": scene["dates"], "series": scene["series"]}), encoding="utf-8"
    )
    (out_dir / "hero_meta.json").write_text(json.dumps(scene["meta"], indent=2), encoding="utf-8")
    return out_dir


def main() -> None:
    scene = generate()
    out = write(scene)
    print(
        f"Hero scene written to {out} "
        f"({scene['meta']['point_count']} points, {scene['meta']['epochs']} epochs)."
    )


if __name__ == "__main__":
    main()
