# LITHOS infrastructure

## Local (one command)

```bash
docker compose -f infra/docker-compose.yml up --build
# web  -> http://localhost:3000
# api  -> http://localhost:8000/docs
```

The API serves the cached hero scene with no credentials. Add `EGMS_USERNAME` /
`EGMS_PASSWORD` to a root `.env` to pull live EGMS tiles.

## Production topology

Following Northflow's existing pattern:

- **Web on Vercel.** The Next.js app is static-first and edge-friendly; Vercel gives
  zero-config previews and a global CDN for the launch-day traffic spike. Set
  `NEXT_PUBLIC_LITHOS_API` to the public API URL.
- **API + ingest on Hetzner.** `infra/Dockerfile.api` runs anywhere Docker runs. Put it
  behind a reverse proxy (Caddy/Traefik) with TLS. The ingest jobs and the spatial store
  live next to it to keep tile queries fast.

### Spatial store: DuckDB vs PostGIS

The default deployment uses the **cached/DuckDB** path: the sample source plus
normalised parquet/DuckDB tiles on local disk. This is zero-config, fast for
city-scale queries, and enough through the early coverage phase.

Switch to **PostGIS** (the commented `db` service) when you index large, frequently
updated tile sets and want concurrent writers, spatial indexes (GiST), and MVT
generation in the database. The catalog is storage-agnostic, so this is a config
change, not a rewrite. Justification and migration notes belong in
[`docs/architecture.md`](../docs/architecture.md).

## Observability and freshness

- The API emits structured JSON logs and an `X-Response-Time-ms` header per request.
- `infra/freshness_monitor.py` is a scheduled job (cron or the `freshness` CI workflow)
  that checks EGMS/LiCSAR reachability and reports per-source status as JSON. It exits
  non-zero when a source is down so alerting can hook in. New-coverage events feed the
  public launch-cadence narrative.

## Resilience

Every source degrades gracefully: if EGMS or LiCSAR is unreachable, the catalog serves
cached data and marks freshness rather than crashing. Upstream schema changes surface as
empty results plus a logged warning, never a hard 500.
