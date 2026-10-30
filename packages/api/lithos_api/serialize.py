"""Serialisation helpers: canonical models -> GeoJSON / API dicts / CSV."""

from __future__ import annotations

import csv
import io

from lithos_core.schema import CoverageCell, MeasurementPoint, PointVerdict, TimeSeries


def point_feature(p: MeasurementPoint, verdict: PointVerdict | None = None) -> dict:
    props: dict = {
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
        "relative_only": p.datum_note is not None,
    }
    if verdict is not None:
        flag = verdict.primary_flag
        props.update(
            {
                "anomaly_type": flag.type.value if flag else None,
                "anomaly_confidence": flag.confidence if flag else None,
                "anomaly_onset": flag.onset_date.isoformat() if flag and flag.onset_date else None,
                "headline": verdict.headline,
                "newsworthiness": round(verdict.newsworthiness, 2),
            }
        )
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
        "properties": props,
    }


def points_feature_collection(
    points: list[MeasurementPoint],
    verdicts: dict[str, PointVerdict] | None = None,
) -> dict:
    verdicts = verdicts or {}
    return {
        "type": "FeatureCollection",
        "features": [point_feature(p, verdicts.get(p.id)) for p in points],
    }


def coverage_feature_collection(cells: list[CoverageCell]) -> dict:
    feats = []
    for c in cells:
        minlon, minlat, maxlon, maxlat = c.bbox
        feats.append(
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
                    "newest_window": c.newest_window,
                    "density_class": c.density_class,
                    "note": c.note,
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def timeseries_dict(ts: TimeSeries) -> dict:
    return {
        "point_id": ts.point_id,
        "samples": [
            {
                "date": s.date.isoformat(),
                "displacement_mm": s.displacement_mm,
                "uncertainty_mm": s.uncertainty_mm,
            }
            for s in ts.samples
        ],
    }


def timeseries_csv(ts: TimeSeries, notes: list[str] | None = None) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for line in notes or ():
        buf.write(f"# {line}\n")
    writer.writerow(["date", "displacement_mm"])
    for s in ts.samples:
        writer.writerow([s.date.isoformat(), "" if s.displacement_mm is None else s.displacement_mm])
    return buf.getvalue()
