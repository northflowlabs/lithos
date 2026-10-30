"""Export static hero assets for the web app's offline/standalone mode.

The public Vercel deploy can render the full hero experience with no backend by reading
these precomputed files from /public/hero. When a live API is configured the web app
prefers it and uses these only as a fallback. Run:
    python -m lithos_ingest.export_web_assets
"""

from __future__ import annotations

import json
from pathlib import Path

from lithos_ingest.base import BBox, data_dir
from lithos_ingest.catalog import LithosCatalog
from lithos_ingest.sources.licsar import LicsarSource


def _web_hero_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "packages" / "web" / "public" / "hero"


def export(out_dir: Path | None = None) -> Path:
    out_dir = out_dir or _web_hero_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    source = LicsarSource()
    catalog = LithosCatalog(sources=[source])
    meta = source.hero
    bbox = BBox(*meta["bbox"])
    points = source.query_points(bbox)

    # 1. Descriptor.
    (out_dir / "hero.json").write_text(
        json.dumps(
            {
                "bbox": meta["bbox"],
                "center": meta["center"],
                "window": meta["window"],
                "name": meta["name"],
                "note": meta["note"],
                "last_epoch": meta["last_epoch"],
            }
        ),
        encoding="utf-8",
    )

    # 2. Points as GeoJSON with anomaly properties merged in (so the anomaly layer and
    #    panel headlines work in static mode).
    features = []
    verdicts = {}
    for p in points:
        v = catalog.verdict_for(p)
        flag = v.primary_flag
        verdicts[p.id] = {
            "point_id": p.id,
            "velocity_mm_yr": v.velocity_mm_yr,
            "velocity_uncertainty_mm_yr": v.velocity_uncertainty_mm_yr,
            "headline": v.headline,
            "newsworthiness": round(v.newsworthiness, 2),
            "flags": [f.model_dump(mode="json") for f in v.flags],
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
                "properties": {
                    "id": p.id,
                    "vertical_velocity": p.vertical_velocity,
                    "los_velocity": p.los_velocity,
                    "horizontal_velocity": p.horizontal_velocity,
                    "velocity_uncertainty": p.velocity_uncertainty,
                    "best_velocity": p.best_velocity,
                    "coherence": p.coherence,
                    "source": p.source,
                    "product": p.product,
                    "processing_window": p.processing_window,
                    "anomaly_type": flag.type.value if flag else None,
                    "anomaly_confidence": flag.confidence if flag else None,
                    "anomaly_onset": flag.onset_date.isoformat() if flag and flag.onset_date else None,
                    "headline": v.headline,
                    "newsworthiness": round(v.newsworthiness, 2),
                },
            }
        )
    (out_dir / "points.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    (out_dir / "verdicts.json").write_text(json.dumps(verdicts), encoding="utf-8")

    # 3. Time series (reuse the scene file).
    ts_src = data_dir() / "scenes" / meta["slug"] / "timeseries.json"
    (out_dir / "timeseries.json").write_text(ts_src.read_text(encoding="utf-8"), encoding="utf-8")

    # 4. Coverage grid (honest global availability), computed from real source extents.
    full = LithosCatalog()
    grid = full.coverage_grid()
    cov_features = []
    for c in grid:
        minlon, minlat, maxlon, maxlat = c.bbox
        cov_features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [minlon, minlat],
                            [maxlon, minlat],
                            [maxlon, maxlat],
                            [minlon, maxlat],
                            [minlon, minlat],
                        ]
                    ],
                },
                "properties": {
                    "cell_id": c.cell_id,
                    "available": c.available,
                    "sources": c.sources,
                    "density_class": c.density_class,
                    "note": c.note,
                },
            }
        )
    (out_dir / "coverage_grid.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": cov_features}), encoding="utf-8"
    )

    return out_dir


def main() -> None:
    out = export()
    print(f"Web hero assets written to {out}")


if __name__ == "__main__":
    main()
