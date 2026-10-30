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

Following Northflow's existing pattern:

- **Web on Vercel.** The Next.js app is static-first and edge-friendly; Vercel gives
  zero-config previews and a global CDN. Set
  `NEXT_PUBLIC_LITHOS_API` to the public API URL.
- **API + ingest on Hetzner.** `infra/Dockerfile.api` runs anywhere Docker runs. Put it
  behind a reverse proxy (Caddy/Traefik) with TLS. Scenes are built separately and committed.

### Storage

Scenes are plain files under `data/scenes/`, copied into the API image. There is no database.

## Observability and freshness

- The API emits structured JSON logs and an `X-Response-Time-ms` header per request.
- `infra/freshness_monitor.py` is a scheduled job (cron or the `freshness` CI workflow)
  that checks EGMS/LiCSAR reachability and reports per-source status as JSON. It exits
  non-zero when a source is down so alerting can hook in.

## Resilience

Every source degrades gracefully: if EGMS or LiCSAR is unreachable, the catalog serves
cached data and marks freshness rather than crashing. Upstream schema changes surface as
empty results plus a logged warning, never a hard 500.
