"""API tests against the measured Bologna scene. No network."""

from __future__ import annotations

from fastapi.testclient import TestClient
from lithos_api.app import create_app

client = TestClient(create_app())
BBOX = "11.18,44.40,11.68,44.60"


def test_health():
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "licsar" in r.json()["sources"]


def test_hero_descriptor():
    r = client.get("/v1/hero")
    assert r.status_code == 200
    body = r.json()
    assert len(body["bbox"]) == 4
    assert "Sentinel-1" in body["note"]
    assert "is_synthetic" not in body


def test_sources_have_attribution():
    r = client.get("/v1/sources")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["sources"]}
    assert {"egms", "licsar"} <= keys
    for s in r.json()["sources"]:
        assert s["attribution"]


def test_points_feature_collection():
    r = client.get(f"/v1/points?bbox={BBOX}&limit=200")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 50
    f0 = fc["features"][0]
    assert f0["geometry"]["type"] == "Point"
    assert "best_velocity" in f0["properties"]


def test_points_with_anomaly():
    r = client.get(f"/v1/points?bbox={BBOX}&limit=50&with_anomaly=true")
    feats = r.json()["features"]
    assert any(f["properties"].get("headline") for f in feats)


def test_time_filters_are_refused_not_ignored():
    r = client.get(f"/v1/points?bbox={BBOX}&start=2022-01-01")
    assert r.status_code == 400


def test_an_area_of_relative_points_has_no_numbers():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[11.46, 44.40], [11.68, 44.40], [11.68, 44.60], [11.46, 44.60], [11.46, 44.40]]],
    }
    body = client.post("/v1/aoi/scan", json={"geometry": polygon}).json()
    assert body["point_count"] > 100
    assert body["left_out_count"] == body["point_count"]
    assert body["mean_velocity_mm_yr"] is None and body["max_uplift_mm_yr"] is None
    assert body["top_points"] == []
    assert body["note"]


def test_malformed_polygon_is_refused():
    r = client.post("/v1/aoi/scan", json={"geometry": {"type": "Polygon", "coordinates": [[1, 2, 3]]}})
    assert r.status_code == 400


def test_timeseries_says_where_and_how_far_to_trust_it():
    east = client.get("/v1/points?bbox=11.5,44.4,11.6,44.6&limit=1").json()["features"][0]
    pid = east["properties"]["id"]
    body = client.get(f"/v1/points/{pid}/timeseries").json()
    assert body["relative_only"] is True and "lon" in body
    assert "relative_only=True" in client.get(f"/v1/points/{pid}/timeseries?format=csv").text


def test_bbox_too_large_rejected():
    r = client.get("/v1/points?bbox=-10,-10,30,30")
    assert r.status_code == 413


def test_bad_bbox_rejected():
    r = client.get("/v1/points?bbox=1,2,3")
    assert r.status_code == 400


def test_timeseries_json_and_csv():
    feats = client.get(f"/v1/points?bbox={BBOX}&limit=1").json()["features"]
    pid = feats[0]["properties"]["id"]
    rj = client.get(f"/v1/points/{pid}/timeseries")
    assert rj.status_code == 200
    assert len(rj.json()["samples"]) > 40
    rc = client.get(f"/v1/points/{pid}/timeseries?format=csv")
    assert rc.status_code == 200
    assert rc.text.startswith(f"# point {pid}, lon=")
    assert "# LiCSAR contains modified Copernicus Sentinel data" in rc.text
    assert "Blewitt" in rc.text
    assert "date,displacement_mm" in rc.text
    assert "\n# " in rc.text


def test_point_verdict():
    feats = client.get(f"/v1/points?bbox={BBOX}&limit=1").json()["features"]
    pid = feats[0]["properties"]["id"]
    r = client.get(f"/v1/points/{pid}/verdict")
    assert r.status_code == 200
    assert r.json()["point_id"] == pid
    assert r.json()["headline"]


def test_anomalies_ranked_and_summarised():
    r = client.get(f"/v1/anomalies?bbox={BBOX}&limit=300")
    assert r.status_code == 200
    fc = r.json()
    assert "summary" in fc
    assert fc["summary"]["notable"] >= 1
    if fc["features"]:
        # Most newsworthy first.
        ns = [f["properties"]["newsworthiness"] for f in fc["features"]]
        assert ns == sorted(ns, reverse=True)


def test_coverage_grid_has_available_and_empty():
    fc = client.get("/v1/coverage/grid").json()
    avail = [f for f in fc["features"] if f["properties"]["available"]]
    empty = [f for f in fc["features"] if not f["properties"]["available"]]
    assert avail and empty
    assert all(f["properties"]["note"] for f in empty)


def test_aoi_scan_polygon():
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [11.34, 44.48],
                [11.45, 44.48],
                [11.45, 44.55],
                [11.34, 44.55],
                [11.34, 44.48],
            ]
        ],
    }
    r = client.post("/v1/aoi/scan", json={"geometry": polygon})
    assert r.status_code == 200
    body = r.json()
    assert body["point_count"] > 0
    assert "max_subsidence_mm_yr" in body
    assert body["max_subsidence_mm_yr"] < 0


def test_graphql_anomalies_query():
    q = f'{{ anomalies(bbox: "{BBOX}", limit: 20) {{ id headline anomalyType }} }}'
    r = client.post("/v1/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["anomalies"]
    assert isinstance(data, list)
