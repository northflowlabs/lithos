<a href="https://northflow.no"><img src=".github/assets/northflow-mark.svg" alt="Northflow" width="40" height="40"></a>

# LITHOS

LITHOS is an open source ground motion map that shows how the ground rises and sinks, to the millimetre, measured by radar satellites.

[Research page](https://research.northflow.no/systems/lithos) · [Quickstart](docs/quickstart.md) · [Notebook](https://colab.research.google.com/github/northflowlabs/lithos/blob/main/packages/notebook/lithos_quickstart.ipynb) · [Licence](#licence)

[![CI](https://github.com/northflowlabs/lithos/actions/workflows/ci.yml/badge.svg)](https://github.com/northflowlabs/lithos/actions/workflows/ci.yml)
[![Licence: Apache 2.0](https://img.shields.io/badge/licence-Apache%202.0-0e6b63)](LICENSE)

<img src="docs/assets/hero.png" alt="LITHOS map of a subsidence bowl, red where the ground sinks" width="820"/>

<sub>The demonstration scene that ships with LITHOS: a synthetic subsidence bowl modelled on Bologna, so the app renders without credentials. Red is sinking, blue is rising.</sub>

## What it does

Cities sink as groundwater is drawn down, coastlines subside, and dams, railways and buildings deform years before anyone notices. Radar satellites have measured this to the millimetre for more than a decade, and the processed data is public.

LITHOS reads two of those public datasets, the European Ground Motion Service (EGMS) and the global COMET LiCSAR archive, and adds a map that a non-specialist can read and an anomaly engine that flags points behaving differently from their neighbours. LITHOS does not process raw radar.

- **Click a point** to see its line-of-sight and vertical velocity in mm per year, its displacement time series and a plain-language summary, for example: *"This point has been sinking about 14 mm/year and accelerated after early 2023."*
- **Draw an area** to get aggregate statistics, a count of anomalous points and callouts for any new subsidence or uplift bowl inside it.
- **See where data exists.** A coverage layer shows where ground motion data is available and how recent it is.
- **Share and export.** Every view has a permalink. Export the map as PNG, a time series as CSV or an area as GeoJSON.
- **Build on it.** A documented API serves coverage, points, time series and anomaly results.

LITHOS measures dry-land surface motion: subsidence and uplift. It reports observed movement and flags anomalies. It does not predict structural failure, and it does not cover water, seabeds or offshore areas.

## The anomaly engine

Every point and area runs through a pipeline of standard, published statistics:

- **Acceleration and change points:** finds when a trend shifts, with the onset date
- **Emerging clusters:** hotspot analysis that flags a new deformation bowl inside an area
- **Seasonal and secular motion:** separates reversible seasonal swings from long-term motion
- **Confidence gating:** low-coherence points are not over-flagged

Each flag carries a machine-readable record (type, magnitude, onset, confidence, evidence) and one sentence that states its uncertainty. A regression suite runs the engine against labelled synthetic events with known ground truth. See [docs/anomaly-engine.md](docs/anomaly-engine.md).

## Coverage

| Region | Source | Coverage | Notes |
| --- | --- | --- | --- |
| EU, Norway, UK, Iceland | Copernicus EGMS | Dense, validated, millimetre grade | Rolling five-year windows, for example 2019 to 2023 |
| Tectonic and volcanic belts, many populated regions | COMET LiCSAR | Strong, not uniform | Frame based; density varies by region |
| Stable continental interiors, oceans | None | Thin or none | Shown in the coverage layer |

See [docs/coverage.md](docs/coverage.md).

## Run it locally

LITHOS runs with one command. Real EGMS data needs a free [Copernicus account](https://dataspace.copernicus.eu/); the demonstration scene renders without one.

```bash
git clone https://github.com/northflowlabs/lithos.git
cd lithos
cp .env.example .env        # add your Copernicus credentials (optional for the demonstration scene)
docker compose -f infra/docker-compose.yml up --build
```

Open `http://localhost:3000` for the web app and `http://localhost:8000/docs` for the API. For the notebook and a Python quickstart, see [docs/quickstart.md](docs/quickstart.md).

## How it works

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

Every source normalises into one schema, so new coverage changes nothing downstream. Design notes are in [docs/architecture.md](docs/architecture.md).

## Data and attribution

Credit these sources in any work you publish with LITHOS:

- **European Ground Motion Service (EGMS)**, Copernicus Land Monitoring Service. Contains modified Copernicus data, used under Copernicus terms.
- **COMET LiCSAR**, Centre for Observation and Modelling of Earthquakes, Volcanoes and Tectonics. Contains modified Copernicus Sentinel data, analysed by COMET.

LITHOS fetches LiCSAR products over the network and contains no LiCSAR or LiCSBAS code. The citation text and the details are in [docs/attribution.md](docs/attribution.md) and [docs/licensing.md](docs/licensing.md).

## Cite LITHOS

```
Northflow Technologies AS (2026). LITHOS: open ground motion intelligence.
https://github.com/northflowlabs/lithos
```

Used LITHOS in a story or a study? Open an issue with the `showcase` label or write to hello@northflow.no.

## Roadmap

Available now: EGMS and LiCSAR in one map, point inspection, area scans, the anomaly engine, the coverage layer, permalinks, exports, the public API, the web app and the notebook.

Planned: coverage region by region, more export formats, and a processing path that derives products directly from raw Sentinel-1 data.

Out of scope: predicting structural or geological failure, and water, seabed and offshore analysis.

## Contributing

We welcome new coverage adapters, anomaly methods, translations, documentation and bug reports. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [good first issues](https://github.com/northflowlabs/lithos/labels/good%20first%20issue). A clear, reproducible issue is the fastest way to get something fixed.

## Licence

LITHOS is licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 Northflow Technologies AS
