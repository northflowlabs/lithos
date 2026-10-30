"""LITHOS FastAPI application: versioned REST + GraphQL, CORS-enabled, observable."""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from strawberry.fastapi import GraphQLRouter

from lithos_api import serialize
from lithos_api.deps import (
    build_filters,
    get_catalog,
    parse_bbox,
)
from lithos_api.geometry import point_in_polygon, ring_bbox
from lithos_api.graphql import schema

logging.basicConfig(
    level=os.getenv("LITHOS_LOG_LEVEL", "INFO"),
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("lithos.api")

API_VERSION = "v1"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Warm the hero verdict cache in a background thread so the first anomaly request
    # is served from cache and the hero view stays under the three-second wow gate.
    def _warm() -> None:
        try:
            n = get_catalog().warm_hero()
            log.info("hero warm-up complete: %d points cached", n)
        except Exception as exc:  # noqa: BLE001  never block or crash startup on warm-up
            log.warning("hero warm-up failed: %s", exc)

    threading.Thread(target=_warm, name="lithos-warm", daemon=True).start()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LITHOS API",
        version="0.1.0",
        description=(
            "Open access ground-motion intelligence. Coverage, points, time series, and "
            "anomaly flags, measured from COMET LiCSAR interferograms and EGMS tiles and "
            "normalised into one schema. "
            "Dry-land surface motion only. Observed motion and anomalies, never failure forecasts."
        ),
        license_info={"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"},
        lifespan=_lifespan,
    )

    origins = os.getenv("LITHOS_API_CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins] or ["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
        log.info("%s %s -> %s in %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
        return response

    prefix = f"/{API_VERSION}"

    # --- meta --------------------------------------------------------------------
    @app.get("/")
    def root() -> dict:
        return {
            "name": "LITHOS API",
            "version": "0.1.0",
            "docs": "/docs",
            "graphql": f"{prefix}/graphql",
            "scope": "dry-land surface motion only; observed motion and anomalies, no failure forecasts",
        }

    @app.get(f"{prefix}/health")
    def health() -> dict:
        cat = get_catalog()
        return {"status": "ok", "sources": [m.key for m in cat.source_metas()]}

    @app.get(f"{prefix}/sources")
    def sources() -> dict:
        cat = get_catalog()
        return {
            "sources": [m.model_dump() for m in cat.source_metas()],
            "attribution_required": True,
        }

    @app.get(f"{prefix}/hero")
    def hero() -> dict:
        """The zero-input default scene descriptor the web app loads first."""
        for source in get_catalog().sources:
            scene = getattr(source, "hero", None)
            if scene is not None:
                return {
                    "bbox": scene["bbox"],
                    "center": scene["center"],
                    "window": scene["window"],
                    "name": scene["name"],
                    "note": scene["note"],
                    "last_epoch": scene["last_epoch"],
                }
        raise HTTPException(503, "No scene is available; check LITHOS_DATA_DIR")

    # --- coverage ----------------------------------------------------------------
    @app.get(f"{prefix}/coverage")
    def coverage() -> dict:
        return serialize.coverage_feature_collection(get_catalog().coverage())

    @app.get(f"{prefix}/coverage/grid")
    def coverage_grid() -> dict:
        return serialize.coverage_feature_collection(get_catalog().coverage_grid())

    # --- points ------------------------------------------------------------------
    @app.get(f"{prefix}/points")
    def points(
        bbox: str = Query(..., description="minlon,minlat,maxlon,maxlat"),
        start: str | None = None,
        end: str | None = None,
        min_coherence: float | None = None,
        min_velocity: float | None = Query(None, description="min |velocity| mm/yr"),
        limit: int = Query(5000, le=20000),
        with_anomaly: bool = False,
    ) -> dict:
        if start or end:
            raise HTTPException(
                400, "start and end are not supported: a scene is served over its whole window"
            )
        cat = get_catalog()
        b = parse_bbox(bbox)
        filters = build_filters(min_coherence, min_velocity, limit)
        pts = cat.query_points(b, None, filters)
        verdicts = {p.id: cat.verdict_for(p) for p in pts} if with_anomaly else None
        return serialize.points_feature_collection(pts, verdicts)

    @app.get(f"{prefix}/points/{{point_id}}/timeseries")
    def timeseries(point_id: str, format: str = "json"):
        ts = get_catalog().get_time_series(point_id)
        if ts is None:
            raise HTTPException(404, f"No time series for point '{point_id}'")
        if format == "csv":
            return PlainTextResponse(
                serialize.timeseries_csv(ts),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{point_id}.csv"'},
            )
        return serialize.timeseries_dict(ts)

    @app.get(f"{prefix}/points/{{point_id}}/verdict")
    def point_verdict(point_id: str) -> dict:
        cat = get_catalog()
        point = cat.get_point(point_id)
        if point is None:
            raise HTTPException(404, f"Unknown point '{point_id}'")
        return cat.verdict_for(point).model_dump(mode="json")

    # --- anomalies ---------------------------------------------------------------
    @app.get(f"{prefix}/anomalies")
    def anomalies(
        bbox: str = Query(..., description="minlon,minlat,maxlon,maxlat"),
        limit: int = Query(2000, le=20000),
        only_notable: bool = True,
    ) -> dict:
        cat = get_catalog()
        b = parse_bbox(bbox)
        pts = cat.query_points(b, filters=build_filters(None, None, limit))
        by_id = {p.id: p for p in pts}
        verdicts = {p.id: cat.verdict_for(p) for p in pts}
        if only_notable:
            keep = {
                pid: v
                for pid, v in verdicts.items()
                if v.primary_flag is not None and v.primary_flag.is_notable
            }
        else:
            keep = verdicts
        ordered = sorted(keep.values(), key=lambda v: v.newsworthiness, reverse=True)
        ordered_points = [by_id[v.point_id] for v in ordered if v.point_id in by_id]
        fc = serialize.points_feature_collection(ordered_points, keep)
        fc["summary"] = {
            "queried": len(pts),
            "notable": len(keep),
        }
        return fc

    # --- AOI scan ----------------------------------------------------------------
    @app.post(f"{prefix}/aoi/scan")
    def aoi_scan(geometry: dict = Body(..., embed=True)) -> dict:  # noqa: B008  FastAPI's way to declare a body field
        """Scan a drawn polygon: aggregate stats, ranked points, emerging clusters."""
        if geometry.get("type") != "Polygon":
            raise HTTPException(400, "geometry must be a GeoJSON Polygon")
        coords = geometry.get("coordinates")
        if not coords or not coords[0]:
            raise HTTPException(400, "polygon has no coordinates")
        minlon, minlat, maxlon, maxlat = ring_bbox(coords[0])
        cat = get_catalog()
        bbox = parse_bbox(f"{minlon},{minlat},{maxlon},{maxlat}")
        candidates = cat.query_points(bbox, filters=build_filters(None, None, 20000))
        inside = [p for p in candidates if point_in_polygon(p.lon, p.lat, coords)]
        if not inside:
            return {
                "point_count": 0,
                "anomalous_count": 0,
                "note": "No indexed ground-motion points in this area.",
            }
        result = cat.scan_aoi(inside)
        return result.to_dict()

    # --- GraphQL -----------------------------------------------------------------
    graphql_app = GraphQLRouter(schema)
    app.include_router(graphql_app, prefix=f"{prefix}/graphql")

    return app


app = create_app()
