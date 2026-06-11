"""Ingest adapter and catalog tests. Run against the cached sample scene; no network."""

from __future__ import annotations

from lithos_ingest.base import BBox, PointFilters
from lithos_ingest.catalog import LithosCatalog
from lithos_ingest.sources.egms import EgmsSource
from lithos_ingest.sources.licsar import LicsarSource
from lithos_ingest.sources.sample import SampleSource

BOLOGNA = BBox(11.27, 44.43, 11.47, 44.57)


def test_sample_source_loads_hero():
    src = SampleSource()
    pts = src.query_points(BOLOGNA)
    assert len(pts) > 100
    assert all(BOLOGNA.contains(p.lon, p.lat) for p in pts)
    # The strongest subsidence should be a clearly negative vertical velocity.
    assert min(p.vertical_velocity for p in pts if p.vertical_velocity is not None) < -15


def test_sample_time_series_present():
    src = SampleSource()
    pts = src.query_points(BOLOGNA, filters=PointFilters(max_points=5))
    ts = src.get_time_series(pts[0].id)
    assert ts is not None and len(ts.samples) > 50


def test_sample_filters_apply():
    src = SampleSource()
    strong = src.query_points(BOLOGNA, filters=PointFilters(min_abs_velocity=10.0))
    assert strong
    assert all(abs(p.best_velocity or 0) >= 10.0 for p in strong)


def test_egms_degrades_without_credentials():
    src = EgmsSource(username=None, password=None)
    assert src.configured is False
    # Inside footprint but no creds -> empty, not error.
    assert src.query_points(BBox(2.0, 48.0, 3.0, 49.0)) == []
    cov = src.list_coverage()
    assert cov and cov[0].available is False


def test_licsar_honest_outside_belts():
    src = LicsarSource()
    # Mid-Atlantic ocean: no belt, must return empty (no fabricated coverage).
    assert src.query_points(BBox(-40.0, 20.0, -39.0, 21.0)) == []
    # Coverage declares belts explicitly.
    belts = src.list_coverage()
    assert any("japan" in c.cell_id for c in belts)


def test_licsar_never_imports_gpl():
    # The firewall: this module must not pull in any LiCSBAS / licsar_proc package.
    import lithos_ingest.sources.licsar as mod
    src = open(mod.__file__, encoding="utf-8").read()
    assert "import licsbas" not in src.lower()
    assert "import licsar_proc" not in src.lower()
    assert "from licsbas" not in src.lower()


def test_catalog_coverage_grid_is_honest():
    cat = LithosCatalog(sources=[SampleSource(), EgmsSource(), LicsarSource()])
    grid = cat.coverage_grid()
    available = [c for c in grid if c.available]
    empty = [c for c in grid if not c.available]
    # Both states must be present: real coverage and honest emptiness.
    assert available and empty
    assert all(c.note for c in empty)  # every empty cell explains itself


def test_catalog_anomalies_rank_subsidence_first():
    cat = LithosCatalog(sources=[SampleSource()])
    verdicts = cat.anomalies_in_bbox(BOLOGNA, filters=PointFilters(max_points=50))
    assert verdicts
    top = verdicts[0]
    assert top.velocity_mm_yr is not None and top.velocity_mm_yr < -10
    assert top.primary_flag is not None and top.primary_flag.is_notable
