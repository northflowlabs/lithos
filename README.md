<div align="center">

# LITHOS

### See the ground move.

**LITHOS is a free, open-source tool that lets anyone watch the Earth's surface rise and sink, millimetre by millimetre, from a web browser. Type a place. See whether it is moving. Get an automatic flag when something is wrong.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](#try-it-in-60-seconds)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#roadmap)
[![Data: Copernicus EGMS + COMET LiCSAR](https://img.shields.io/badge/data-EGMS%20%2B%20LiCSAR-orange.svg)](#data-and-attribution)

<br/>

<!-- HERO IMAGE: the dramatic default scene. A real sinking city, EGMS velocity map,
     deep reds where the ground is subsiding. This is the screenshot that travels. -->
<img src="docs/assets/hero.png" alt="LITHOS showing ground subsidence over a major city" width="820"/>

<sub>Above: vertical ground motion over Bologna, 2019 to 2023. Red is sinking, blue is rising. Source: Copernicus EGMS.</sub>

</div>

---

## What this is

The solid ground under your feet is not still. Cities sink as groundwater is drawn down. Coastlines subside. Old mines collapse slowly. Dams, railways, and buildings deform years before anyone notices. Satellites have measured all of this, to millimetre precision, for over a decade. The data is public and free.

The problem is that almost nobody can use it. The measurements sit behind specialist tools, radar physics, and gigabyte downloads. LITHOS removes that wall.

LITHOS does not re-process raw satellite radar. It stands on top of two excellent, already-processed, free public datasets (Europe's EGMS and the global COMET LiCSAR archive), and adds the two things they lack: a map a non-specialist can actually read, and an intelligence layer that automatically flags the points that are behaving strangely, so you do not have to know what you are looking for.

It is built for journalists, OSINT researchers, civil engineers, geologists, planners, insurers, students, and anyone who wants to know whether the ground under a place they care about is moving.

> **Scope, stated plainly.** LITHOS measures **dry-land surface motion** (subsidence and uplift). It reports observed movement and flags anomalies. It does **not** predict structural failure, and it does **not** cover water, seabeds, or offshore areas. See [Roadmap](#roadmap) for what is coming and what is deliberately out.

---

## Try it in 60 seconds

**No install.**

- **Web app:** **[app.lithos.earth](#)** opens on a real subsiding city. Pan anywhere covered, click a point, see its history.
- **Notebook:** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](packages/notebook/lithos_quickstart.ipynb) Pick a location, pull the data, run the anomaly scan, plot it. Nothing to set up.

<!-- DEMO GIF: click a point -> side panel slides in -> time-series chart draws ->
     plain-language anomaly verdict appears. One loop, under 6 seconds. -->
<div align="center">
<img src="docs/assets/demo.gif" alt="Clicking a point and reading its ground-motion history and anomaly flag" width="720"/>
</div>

---

## What it does

**Click any covered point.** Get its line-of-sight and vertical velocity in mm/year, its full displacement time series, and a plain-language read on its behaviour, for example: *"This point has been sinking about 14 mm/year and accelerated after early 2023."*

**Draw an area.** Get aggregate statistics, a count of anomalous points, and automatic callouts for any newly forming subsidence or uplift bowl inside it.

**See where data exists, honestly.** A coverage layer shows exactly where ground-motion data is available and how recent it is. Where there is none, LITHOS tells you so. It never returns a misleading blank.

**Share and export.** Every view has a permalink (location, time window, and layers encoded in the URL, ready to drop into an article). Export the map as PNG, the time series as CSV, or an area's results as GeoJSON.

**Build on it.** A public, documented API serves coverage, points, time series, and anomaly results so others can build their own tools on top.

---

## The part that makes LITHOS different: the anomaly engine

Raw velocity maps tell you what is moving. They do not tell you what *changed*. LITHOS runs every point and every area through a standard, openly-published statistical pipeline that surfaces the things a human eye would miss in a field of thousands of points:

- **Acceleration and change-points:** detects when a point's trend shifts, for example stable ground that began sinking, or sinking that suddenly sped up, with the onset date.
- **Emerging clusters:** spatial hotspot analysis that flags a *new* deformation bowl forming inside an area over a chosen window.
- **Seasonal vs. secular:** separates reversible seasonal swings from real long-term motion, so the flags mean something.
- **Confidence-gated:** low-quality, low-coherence points are not over-flagged.

Every flag comes with a machine-readable record (type, magnitude, onset, confidence, evidence) and one calm, quotable sentence with its uncertainty stated. No alarmism. No failure predictions. Just the observation, clearly.

The engine is validated against documented, real-world deformation events to prove it catches the real thing and does not cry wolf on noise. See [`docs/anomaly-engine.md`](docs/anomaly-engine.md).

---

## Coverage, honestly

LITHOS is global by design but its data is not yet uniform worldwide, and we will never pretend otherwise. Honest coverage is a feature here, not a footnote.

| Region | Source | Coverage | Notes |
| --- | --- | --- | --- |
| EU + Norway + UK + Iceland | **Copernicus EGMS** | Dense, validated, mm-grade | Rolling 5-year windows (e.g. 2019 to 2023, 2020 to 2024) |
| Global tectonic and volcanic belts, many populated regions | **COMET LiCSAR** | Strong but not uniform | Frame-based; density varies by region |
| Stable continental interiors, oceans | none | Thin or none | Shown explicitly in the coverage layer |

Coverage expands over time. Each expansion is announced. If your region is not covered today, the coverage map will say so, and tell you why.

---

## Quickstart (self-host)

LITHOS runs locally with one command. You will need a **free Copernicus account** to download EGMS data ([register here](https://dataspace.copernicus.eu/), no cost). LITHOS ships with a cached hero scene, so it renders the default view even before you add credentials.

```bash
git clone https://github.com/northflow/lithos.git
cd lithos
cp .env.example .env        # add your free Copernicus credentials (optional for the hero scene)
docker compose -f infra/docker-compose.yml up --build
```

Then open `http://localhost:3000` for the web app and `http://localhost:8000/docs` for the API.

For the notebook workflow and a Python quickstart, see [`docs/quickstart.md`](docs/quickstart.md).

---

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

The data layer is pluggable: every source normalises into one schema, so adding new coverage (or, later, our own processed products) does not change anything downstream. That is what makes the engine global by design. Full design notes in [`docs/architecture.md`](docs/architecture.md).

---

## Data and attribution

LITHOS would not exist without the open science it stands on. Please honour these sources in any work you publish with LITHOS.

- **European Ground Motion Service (EGMS)**, Copernicus Land Monitoring Service. Contains modified Copernicus data. See [`docs/attribution.md`](docs/attribution.md) for the required citation.
- **COMET LiCSAR**, Centre for Observation and Modelling of Earthquakes, Volcanoes and Tectonics. Contains modified Copernicus Sentinel data, analysed by COMET. LiCSAR products are used here as a **data source accessed over the network**; LITHOS does not bundle or modify LiCSAR/LiCSBAS source code (see [Licensing](#licensing)).

---

## Licensing

LITHOS is released under **[Apache-2.0](LICENSE)**.

A deliberate boundary: the COMET LiCSAR / LiCSBAS toolchain is GPL-3.0. LITHOS treats those as **data providers it fetches from**, never as code it vendors or links, which keeps LITHOS permissively licensed and freely adoptable. The reasoning is documented in [`docs/licensing.md`](docs/licensing.md). EGMS data is used under Copernicus terms.

---

## How to cite LITHOS

If LITHOS supported your research, reporting, or analysis, please cite it:

```
Northflow Technologies (2026). LITHOS: open access ground-motion intelligence.
https://github.com/northflow/lithos
```

**Used LITHOS in a story or a study?** We would genuinely like to know. Open an issue with the `showcase` label or write to hello@lithos.earth. Real-world use is the only metric we care about.

---

## Roadmap

**Available now**
- EGMS (Europe) and LiCSAR (global belts) in one map
- Point inspection, area scans, the anomaly engine
- Honest coverage layer, permalinks, exports, public API
- Web app and Colab notebook

**Planned**
- Expanding coverage region by region (announced as it lands)
- More export formats and journalist-friendly templates
- A self-processing path that derives products directly from raw Sentinel-1, extending coverage beyond what is pre-processed today

**Deliberately out of scope**
- Predicting structural or geological failure. LITHOS reports what is observed and flags anomalies. Interpretation and engineering judgement stay with qualified people.
- Water, seabed, and offshore analysis.

---

## Contributing

Contributions are welcome: new coverage adapters, anomaly methods, translations, documentation, and bug reports. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [good first issues](https://github.com/northflow/lithos/labels/good%20first%20issue).

**An honest note on maintenance.** LITHOS is community-supported and maintained on a part-time basis. We aim to triage issues and review pull requests weekly, but response times will vary. If something is broken, a clear, reproducible issue is the fastest way to get it fixed, including by you.

---

## Why we built this

Northflow builds systems that turn public scientific data into something people can act on. We already do this for famine forecasting and maritime awareness. Ground motion is the same idea pointed at the Earth beneath us: a decade of free, precise measurement that almost nobody can read, made open to everyone.

LITHOS is **built on the same engine behind Northflow's maritime and humanitarian systems.** One engine, many sciences. This is one of them, given away.

<div align="center">
<br/>
<sub>A <a href="https://northflow.no">Northflow Technologies</a> project. Apache-2.0. Built in the open.</sub>
</div>
