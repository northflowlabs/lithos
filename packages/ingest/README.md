# lithos-ingest

Pluggable data-source adapters. Each source implements one `GroundMotionSource`
protocol and normalises its native products into the canonical `lithos_core` schema.
Adding a future source (including, later, Northflow's own Sentinel-1 derived products)
means implementing this one interface. Nothing downstream changes.

## Sources shipped

| Adapter | Coverage | Access | License of data |
| --- | --- | --- | --- |
| `egms` | EU + Norway + UK + Iceland | EGMS machine-to-machine API (free Copernicus login) | Copernicus terms |
| `licsar` | Global tectonic and volcanic belts | COMET-LiCS public HTTP archive | Copernicus Sentinel, analysed by COMET |
| `sample` | The cached hero scene and fixtures | Local files in `data/samples/` | Synthetic demonstration data |

## Licensing firewall

The `licsar` adapter fetches **data products over HTTP** from the public archive. It
does not import, vendor, or link LiCSBAS / `licsar_proc` (which are GPL-3.0). See
[`docs/licensing.md`](../../docs/licensing.md).

## Hero scene

`python -m lithos_ingest.hero` regenerates the deterministic offline hero scene into
`data/samples/`. The shipped hero is a synthetic stand-in modelled on the Bologna
subsidence bowl so the app renders in under three seconds with no credentials. Point
the `egms` adapter at real EGMS tiles (with a free Copernicus account) to replace it.
