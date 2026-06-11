# lithos-api

The public LITHOS API: FastAPI REST + GraphQL over the canonical ground-motion data.
Versioned (`/v1`), CORS-enabled, rate-limit friendly, OpenAPI docs at `/docs`.

```bash
python -m lithos_api          # serves on :8000
# open http://localhost:8000/docs
```

## Endpoints (`/v1`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness + loaded sources |
| GET | `/sources` | source metadata, license, attribution |
| GET | `/hero` | the zero-input default scene descriptor |
| GET | `/coverage` | declared coverage cells (GeoJSON) |
| GET | `/coverage/grid` | honest global coverage grid (available + empty cells) |
| GET | `/points?bbox=&limit=&with_anomaly=` | points in bbox (GeoJSON) |
| GET | `/points/{id}/timeseries?format=json\|csv` | full displacement history |
| GET | `/points/{id}/verdict` | anomaly verdict for one point |
| GET | `/anomalies?bbox=&only_notable=` | ranked, newsworthy points (GeoJSON) |
| POST | `/aoi/scan` | scan a drawn polygon: stats, clusters, ranked points |
| `/graphql` | GraphQL playground + endpoint |

Scope: dry-land surface motion only. Observed motion and anomalies, never failure
forecasts. Attribution to Copernicus/EGMS and COMET LiCSAR is required for published work.
