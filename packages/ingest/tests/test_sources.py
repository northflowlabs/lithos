"""Ingest adapter and catalog tests. They run on real data, with no network: the Bologna
scene and the recordings in tests/fixtures/licsar. The one exception is marked below."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
from lithos_core.sbas import invert_network, phase_to_los_mm
from lithos_ingest import frames as crawler
from lithos_ingest import licsar_archive as archive
from lithos_ingest.base import BBox, PointFilters
from lithos_ingest.catalog import LithosCatalog
from lithos_ingest.sources.egms import EgmsSource, parse_ortho_csv
from lithos_ingest.sources.licsar import LicsarSource

BOLOGNA = BBox(11.18, 44.40, 11.60, 44.60)
FIXTURES = Path(__file__).parent / "fixtures" / "licsar"


def test_scene_loads_measured_points():
    src = LicsarSource()
    pts = src.query_points(BOLOGNA)
    assert len(pts) > 1000
    assert all(BOLOGNA.contains(p.lon, p.lat) for p in pts)
    assert all(p.source == "licsar" for p in pts)
    assert all("117A_04454_131312" in p.product for p in pts)


def test_scene_shows_the_plain_sinking_and_the_foothills_still():
    pts = LicsarSource().query_points(BOLOGNA)
    north = [p.vertical_velocity for p in pts if p.lat > 44.54 and p.lon < 11.42]
    south = [p.vertical_velocity for p in pts if p.lat < 44.47 and p.lon < 11.42]
    assert np.median(north) < -8
    assert abs(np.median(south)) < 2


def test_scene_time_series_present():
    src = LicsarSource()
    pts = src.query_points(BOLOGNA, filters=PointFilters(max_points=5))
    ts = src.get_time_series(pts[0].id)
    assert ts is not None and len(ts.samples) > 40


def test_scene_filters_apply():
    src = LicsarSource()
    strong = src.query_points(BOLOGNA, filters=PointFilters(min_abs_velocity=10.0))
    assert strong
    assert all(abs(p.best_velocity or 0) >= 10.0 for p in strong)


def test_no_scene_means_no_points():
    assert LicsarSource().query_points(BBox(-40.0, 20.0, -39.0, 21.0)) == []


def test_licsar_frame_index_is_real_coverage():
    src = LicsarSource()
    assert len(src.frames) > 500
    over = [f["id"] for f in src.frames_over(BBox(11.3, 44.5, 11.4, 44.6))]
    assert "095D_04589_131313" in over and "117A_04454_131312" in over
    assert src.frames_over(BBox(-30.0, -40.0, -29.0, -39.0)) == []  # South Atlantic


def test_licsar_never_imports_gpl():
    # The firewall: these modules must not pull in any LiCSBAS / licsar_proc package.
    import lithos_ingest.sources.licsar as mod
    from lithos_core import sbas
    from lithos_ingest import scene

    for module in (mod, scene, archive, sbas):
        with open(module.__file__, encoding="utf-8") as fh:  # type: ignore[arg-type]
            src = fh.read().lower()
        assert "import licsbas" not in src
        assert "import licsar_proc" not in src
        assert "from licsbas" not in src


def test_catalog_coverage_grid_is_honest():
    cat = LithosCatalog(sources=[LicsarSource(), EgmsSource(service_key=None)])
    grid = cat.coverage_grid()
    available = [c for c in grid if c.available]
    empty = [c for c in grid if not c.available]
    assert available and empty
    assert all(c.note for c in empty)  # every empty cell explains itself
    assert all("frames" in (c.note or "") for c in available)


def test_catalog_anomalies_rank_subsidence_first():
    cat = LithosCatalog(sources=[LicsarSource()])
    verdicts = cat.anomalies_in_bbox(BOLOGNA, filters=PointFilters(max_points=50))
    assert verdicts
    top = verdicts[0]
    assert top.velocity_mm_yr is not None and top.velocity_mm_yr < -10
    assert top.primary_flag is not None and top.primary_flag.is_notable


# --- recordings from the archive ---------------------------------------------------


def test_parses_recorded_track_listing():
    frames = crawler.parse_frames((FIXTURES / "track_117.html").read_text(encoding="utf-8"))
    assert "117A_04454_131312" in frames
    assert not any("todel" in f for f in frames)


def test_parses_recorded_pair_listing():
    pairs = archive.parse_pairs((FIXTURES / "interferograms.html").read_text(encoding="utf-8"))
    assert len(pairs) >= 10
    assert all(p.days > 0 for p in pairs)
    assert pairs == sorted(pairs, key=lambda p: (p.first, p.second))


def test_parses_recorded_frame_footprint():
    west, south, east, north = crawler.parse_poly(
        (FIXTURES / "117A_04454_131312-poly.txt").read_text(encoding="utf-8")
    )
    assert west < 11.3 < east and south < 44.5 < north


def test_reads_recorded_interferogram_window():
    rasterio = pytest.importorskip("rasterio")
    path = next(FIXTURES.glob("*.geo.unw.tif"))
    with rasterio.open(path) as src:
        b = src.bounds
    reader = archive.Reader(BBox(b.left, b.bottom, b.right, b.top), requests_per_second=100)
    result = reader.read(str(path))
    assert result is not None
    data, (west, north, dx, dy) = result
    assert data.size > 100 and np.isfinite(data).any()
    assert dx > 0 > dy and abs(west - b.left) < dx and abs(north - b.top) < -dy


def test_solves_a_recorded_cell():
    cell = json.loads((FIXTURES / "cell_north_of_bologna.json").read_text(encoding="utf-8"))
    pairs = [archive.Pair(archive.parse_date(n[:8]), archive.parse_date(n[9:])) for n in cell["pairs"]]
    epochs = sorted({d for p in pairs for d in (p.first, p.second)})
    index = {d: i for i, d in enumerate(epochs)}
    links = np.array([[index[p.first], index[p.second]] for p in pairs])
    los = phase_to_los_mm(np.array(cell["phase_rad"], dtype=float))

    solved = invert_network(links, los, len(epochs))
    years = np.array([(d - epochs[0]).days for d in epochs]) / 365.25
    ok = np.isfinite(solved.displacement_mm)
    slope = np.polyfit(years[ok], solved.displacement_mm[ok], 1)[0]
    assert slope < -4  # receding from the satellite, as the plain subsides
    assert solved.residual_rms_mm < 3


# --- EGMS ---------------------------------------------------------------------------
# No CLMS key was available when this was written, so these exercise the adapter against
# the response shapes documented in the copernicus-land/egms-api notebook and a hand-made
# CSV with the columns of an Ortho tile. Replace it with a recording once a key exists.

ORTHO_UP = "pid;easting;northing;height;rmse;mean_velocity;mean_velocity_std;20190106;20190112\n"
ORTHO_UP += "1;4412050;2382050;40.0;1.2;-9.5;0.4;0.0;-0.2\n"
ORTHO_EAST = "pid;easting;northing;height;rmse;mean_velocity;mean_velocity_std;20190106;20190112\n"
ORTHO_EAST += "1;4412050;2382050;40.0;1.2;1.5;0.4;0.0;0.1\n"


def _zip(csv_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive_zip:
        archive_zip.writestr("tile.csv", csv_text)
    return buffer.getvalue()


def _service_key() -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return {
        "client_id": "client",
        "user_id": "user",
        "token_uri": "https://land.copernicus.eu/@@oauth2-token",
        "private_key": pem.decode(),
    }


def test_egms_without_a_key_returns_nothing():
    src = EgmsSource(service_key=None)
    assert src.configured is False
    assert src.query_points(BBox(11.0, 44.0, 12.0, 45.0)) == []
    assert src.list_coverage()[0].available is False


def test_parse_ortho_csv_reads_epoch_columns():
    rows, dates = parse_ortho_csv(ORTHO_UP)
    assert len(dates) == 2 and dates[0].isoformat() == "2019-01-06"
    assert rows[0]["_series"] == [0.0, -0.2]


@respx.mock
def test_egms_flow(tmp_path):
    base = "https://egms.land.copernicus.eu/insar-api/archive"
    respx.post("https://land.copernicus.eu/@@oauth2-token").mock(
        return_value=httpx.Response(200, json={"access_token": "t"})
    )
    respx.get(f"{base}/releases").mock(return_value=httpx.Response(200, json=["2019-2023"]))

    def search(request: httpx.Request) -> httpx.Response:
        kind = json.loads(request.content)["productType"]
        name = f"{kind}.zip"
        return httpx.Response(200, json={"status": True, "id": "q", "hits": [{"filename": name}]})

    respx.post(f"{base}/search").mock(side_effect=search)
    respx.get(f"{base}/download/ORTHO-UP.zip").mock(
        return_value=httpx.Response(200, content=_zip(ORTHO_UP))
    )
    respx.get(f"{base}/download/ORTHO-EAST.zip").mock(
        return_value=httpx.Response(200, content=_zip(ORTHO_EAST))
    )

    src = EgmsSource(service_key=_service_key(), cache_dir=tmp_path)
    pts = src.query_points(BBox(10.0, 44.0, 13.0, 46.0))
    assert len(pts) == 1
    assert pts[0].vertical_velocity == -9.5
    assert pts[0].horizontal_velocity == 1.5
    assert src.get_time_series(pts[0].id) is not None
