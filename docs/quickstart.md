# Quickstart

Three ways in: the web app, the notebook, and the Python library.

## 1. Self-host the full stack (Docker)

```bash
git clone https://github.com/northflowlabs/lithos.git
cd lithos
cp .env.example .env        # optional: add a CLMS API key for EGMS
docker compose -f infra/docker-compose.yml up --build
```

- Web app: <http://localhost:3000>
- API + OpenAPI docs: <http://localhost:8000/docs>

The measured scenes render without any credentials.

## 2. The notebook (no install)

Open `packages/notebook/lithos_quickstart.ipynb` in Colab. It pulls normalised points,
runs the anomaly engine, and plots a velocity map, a time series, and the flags.

## 3. The Python library

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e "packages/core[dev]" -e "packages/ingest[dev]"
```

```python
from lithos_ingest.base import BBox
from lithos_ingest.catalog import LithosCatalog
from lithos_core.anomaly import analyse_point, scan_area

catalog = LithosCatalog()
points = catalog.query_points(BBox(11.18, 44.40, 11.60, 44.60))   # Bologna

verdict = analyse_point(points[0])
print(verdict.headline)

area = scan_area(points)
print(area.anomalous_count, "anomalous points;", len(area.cluster_flags), "clusters")
```

The distributions are named `pylithos-core`, `pylithos-ingest` and `pylithos-api` (the bare
`lithos` name is taken on PyPI). They are not on PyPI yet, so install from this repository as
shown above. Import modules stay `lithos_core` etc.

## Running the API alone

```bash
pip install -e "packages/core[dev]" -e "packages/ingest[dev]" -e "packages/api[dev]"
python -m lithos_api        # serves on :8000
```

## Build a scene

```bash
pip install -e "packages/ingest[scenes]"
python -m lithos_ingest.scene bologna
```

Add an area to `SCENES` in `lithos_ingest/scene.py` with one ascending and one descending frame
(`LicsarSource().frames_over(bbox)` lists them) and a patch of stable ground. A scene over a city
reads about a thousand interferograms and takes a few minutes.

## EGMS

Register at <https://land.copernicus.eu> (no cost) and create an API token in your profile.
Save the JSON file you receive, set `CLMS_SERVICE_KEY_FILE` to its path in `.env`, and install
`pylithos-ingest[egms]`. Without a key, LITHOS serves its measured scenes and nothing from EGMS.
