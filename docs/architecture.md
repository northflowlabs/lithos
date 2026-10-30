# Architecture

LITHOS is a clean, boring, scalable pipeline: pluggable data sources normalise into one
canonical schema, the anomaly engine reads that schema, and the API/web/notebook/exports
read the engine. No cleverness where stability matters.

```
                 +--------------------------------------------+
   EGMS  ----->  |  ingest: pluggable source adapters          |
 LiCSAR  ----->  |  normalise to one canonical schema          |
                 +-------------------+------------------------+
                                     v
                 +--------------------------------------------+
                 |  core: anomaly engine (standard stats)      |
                 |  spatial index + precomputed flags          |
                 +-------------------+------------------------+
                                     v
            +---------------+--------+--------+---------------+
            v               v                 v               v
       web (map)      public API         notebook        exports
```

## Packages

| Package | Language | Responsibility |
| --- | --- | --- |
| `core` (`lithos_core`) | Python | Canonical schema + anomaly engine. No GPL, no maritime methodology. |
| `ingest` (`lithos_ingest`) | Python | `GroundMotionSource` adapters (LiCSAR, EGMS), the scene builder, catalog, coverage. |
| `api` (`lithos_api`) | Python / FastAPI | REST + GraphQL over the catalog. |
| `web` (`@northflow/lithos-web`) | TypeScript / Next.js | Map-first UI: hero, inspect, AOI, coverage, exports, permalinks. |
| `notebook` | Jupyter | Colab-runnable mirror of the core flow. |

## The spine: one canonical schema

Defined in `lithos_core.schema`:

- **`MeasurementPoint`**: id, lon, lat, height, los/vertical/horizontal velocity,
  uncertainty, coherence/quality, time series, source, product, processing window, ref point.
- **`Tile` / `CoverageCell`**: bbox, source, window, availability/density.
- **`TimeSeries`**, **`AnomalyFlag`**, **`PointVerdict`**.

Every source implements one interface:

```python
class GroundMotionSource(Protocol):
    def source_metadata(self) -> SourceMeta: ...
    def list_coverage(self) -> list[CoverageCell]: ...
    def query_points(self, bbox, time_window, filters) -> list[MeasurementPoint]: ...
    def get_time_series(self, point_id) -> TimeSeries | None: ...
```

Adding a future source (for example, Northflow's own SLC-derived product after the
self-processing path lands) means implementing this interface. Nothing downstream
changes. That is what makes the engine global by design.

## Serving strategy

- The `LithosCatalog` composes sources, dispatches queries, caches per-point verdicts,
  and computes the coverage grid from real declared extents.
- The API serves points as GeoJSON (MVT is a drop-in for very large tile sets). Time
  series are fetched on point-click and cached. Anomaly verdicts are precomputed per
  point and cached.
- AOI scans run the spatial engine on demand over the points inside a drawn polygon.

### Storage

Scenes are plain files under `data/scenes/`, loaded into memory by the adapter. That is
zero-config and fast at city scale. There is no database. The catalog depends only on the
source protocol, so a spatial store can be added behind an adapter if the data outgrows files.

## Honest coverage rendering

`LithosCatalog.coverage_grid()` stamps a coarse global grid from the sources' real
declared cells. Cells nobody stamps are returned with `available: false` and an explicit
note, so the map renders emptiness as a deliberate scientific layer, never a blank or a
misleading zero. See [`coverage.md`](coverage.md).

## Resilience

Every source degrades gracefully. If EGMS or LiCSAR is unreachable or changes shape, the
catalog logs a warning and serves cached data rather than raising. One bad source never
crashes a query.
