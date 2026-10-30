# lithos-ingest

Pluggable data-source adapters. Each source implements one `GroundMotionSource`
protocol and normalises its native products into the canonical `lithos_core` schema.
Adding a future source (including, later, Northflow's own Sentinel-1 derived products)
means implementing this one interface. Nothing downstream changes.

## Sources shipped

| Adapter | Coverage | Access | Licence of data |
| --- | --- | --- | --- |
| `licsar` | Scenes in `data/scenes/`; frames worldwide in the coverage layer | COMET-LiCS public HTTP archive | UK OGL v3.0 and Copernicus terms |
| `egms` | Copernicus Participating States | EGMS archive API, with a free CLMS API key | Copernicus data policy |

## Licensing firewall

The `licsar` adapter fetches **data products over HTTP** from the public archive. It
does not import, vendor, or link LiCSBAS / `licsar_proc` (which are GPL-3.0). See
[`docs/licensing.md`](../../docs/licensing.md).

## Scenes

`python -m lithos_ingest.scene bologna` reads the interferograms over Bologna, solves them and
writes `data/scenes/bologna/`. `python -m lithos_ingest.frames` refreshes the frame index, and
`python -m lithos_ingest.export_web_assets` the static files the web app can run from. Scene
building needs the `scenes` extra (rasterio). See [`docs/refresh.md`](../../docs/refresh.md).
