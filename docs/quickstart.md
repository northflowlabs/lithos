# Quickstart

Three ways in: the web app, the notebook, and the Python library.

## 1. Self-host the full stack (Docker)

```bash
git clone https://github.com/northflow/lithos.git
cd lithos
cp .env.example .env        # optional: add free Copernicus credentials for live EGMS
docker compose -f infra/docker-compose.yml up --build
```

- Web app: <http://localhost:3000>
- API + OpenAPI docs: <http://localhost:8000/docs>

The hero scene renders without any credentials.

## 2. The notebook (no install)

Open `packages/notebook/lithos_quickstart.ipynb` in Colab. It pulls normalised points,
runs the anomaly engine, and plots a velocity map, a time series, and the flags. Worked
examples for Bologna, Mexico City, and Groningen are included.

## 3. The Python library

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e "packages/core[dev]" -e "packages/ingest[dev]"
python -m lithos_ingest.hero      # build the cached hero scene
```

```python
from lithos_ingest.base import BBox
from lithos_ingest.catalog import LithosCatalog
from lithos_core.anomaly import analyse_point, scan_area

catalog = LithosCatalog()
points = catalog.query_points(BBox(11.27, 44.43, 11.47, 44.57))   # Bologna

verdict = analyse_point(points[0])
print(verdict.headline)

area = scan_area(points)
print(area.anomalous_count, "anomalous points;", len(area.cluster_flags), "clusters")
```

Distributions publish under the `pylithos` namespace on PyPI (`pylithos-core`,
`pylithos-ingest`, `pylithos-api`); import modules stay `lithos_core` etc.

## Running the API alone

```bash
pip install -e "packages/core[dev]" -e "packages/ingest[dev]" -e "packages/api[dev]"
python -m lithos_api        # serves on :8000
```

## Free Copernicus account (for live EGMS)

Register at <https://dataspace.copernicus.eu/> (no cost). Put `EGMS_USERNAME` and
`EGMS_PASSWORD` in `.env`. Without them, LITHOS serves the cached hero scene and any
LiCSAR belt data, and degrades gracefully.
