# LITHOS infrastructure

## Local (one command)

```bash
docker compose -f infra/docker-compose.yml up --build
# web  -> http://localhost:3000
# api  -> http://localhost:8000/docs
```

The API serves the measured scenes with no credentials. Add `CLMS_SERVICE_KEY` to a root
`.env` to pull EGMS tiles.

## Production topology

- **Web.** The Next.js app is static first. Without `NEXT_PUBLIC_LITHOS_API` it serves the
  stored scene from `public/hero`. Set the variable at build time to use an API.
- **API.** `infra/Dockerfile.api` runs anywhere Docker runs. Put it behind a reverse proxy
  with TLS. Scenes are built separately and committed.

### Storage

Scenes are plain files under `data/scenes/`, copied into the API image. There is no database.

## Observability and freshness

- The API emits structured JSON logs and an `X-Response-Time-ms` header per request.
- `infra/freshness_monitor.py` is a scheduled job (cron or the `freshness` CI workflow)
  that checks whether the EGMS and LiCSAR endpoints answer, and reports per-source status as
  JSON. It exits non-zero when a source is down. It does not look for new data.
- The `refresh-scenes` workflow rebuilds the scenes on demand. See
  [`docs/refresh.md`](../docs/refresh.md).

## Resilience

The API serves the scenes on disk, so a LiCSAR outage does not affect it. If EGMS is
unreachable or its key is unusable, the adapter logs a warning and returns no points.
