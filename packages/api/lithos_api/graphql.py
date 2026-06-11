"""GraphQL schema (Strawberry) mirroring the REST surface for third-party builders."""

from __future__ import annotations

from typing import Optional

import strawberry

from lithos_api.deps import build_filters, get_catalog, parse_bbox


@strawberry.type
class Point:
    id: str
    lon: float
    lat: float
    best_velocity: Optional[float]
    coherence: Optional[float]
    source: str
    anomaly_type: Optional[str]
    headline: Optional[str]
    newsworthiness: Optional[float]


@strawberry.type
class CoverageCellType:
    cell_id: str
    available: bool
    sources: list[str]
    density_class: str
    note: Optional[str]


@strawberry.type
class SourceMetaType:
    key: str
    name: str
    license: str
    attribution: str
    coverage_description: str


@strawberry.type
class Query:
    @strawberry.field
    def sources(self) -> list[SourceMetaType]:
        return [
            SourceMetaType(
                key=m.key,
                name=m.name,
                license=m.license,
                attribution=m.attribution,
                coverage_description=m.coverage_description,
            )
            for m in get_catalog().source_metas()
        ]

    @strawberry.field
    def coverage(self) -> list[CoverageCellType]:
        return [
            CoverageCellType(
                cell_id=c.cell_id,
                available=c.available,
                sources=c.sources,
                density_class=c.density_class,
                note=c.note,
            )
            for c in get_catalog().coverage()
        ]

    @strawberry.field
    def anomalies(self, bbox: str, limit: int = 100) -> list[Point]:
        cat = get_catalog()
        b = parse_bbox(bbox)
        verdicts = cat.anomalies_in_bbox(b, filters=build_filters(None, None, limit))
        points = {p.id: p for p in cat.query_points(b, filters=build_filters(None, None, limit))}
        out: list[Point] = []
        for v in verdicts:
            p = points.get(v.point_id)
            if not p:
                continue
            flag = v.primary_flag
            out.append(
                Point(
                    id=p.id,
                    lon=p.lon,
                    lat=p.lat,
                    best_velocity=p.best_velocity,
                    coherence=p.coherence,
                    source=p.source,
                    anomaly_type=flag.type.value if flag else None,
                    headline=v.headline,
                    newsworthiness=round(v.newsworthiness, 2),
                )
            )
        return out


schema = strawberry.Schema(query=Query)
