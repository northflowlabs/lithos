# Coverage, honestly

LITHOS is global by design but its data is not yet uniform worldwide, and we will never
pretend otherwise. Honest coverage is a first-class feature, not a footnote.

## What is covered today

| Region | Source | Coverage | Notes |
| --- | --- | --- | --- |
| EU + Norway + UK + Iceland | Copernicus EGMS | Dense, validated, mm-grade | Rolling ~5-year windows (2019 to 2023, 2020 to 2024) |
| Global tectonic and volcanic belts, many populated regions | COMET LiCSAR | Strong but not uniform | Frame-based; density varies by region |
| Stable continental interiors, oceans | none | Thin or none | Shown explicitly in the coverage layer |

### EGMS footprint

Copernicus Participating States only. Live releases are rolling ~5-year windows; older
baselines are archived or migrating to CDSE and are handled as gracefully absent. EGMS is
not available outside these states, and the coverage layer says so.

### LiCSAR belts

LITHOS indexes the principal tectonic and volcanic belts as explicit coverage cells:
Anatolia/Aegean, Italy/Tyrrhenian, Iran/Zagros, the East African Rift, the Andes,
Cascadia/California, Japan, Indonesia/Sunda, the Himalaya, and Iceland. Outside the
indexed belts the LiCSAR adapter returns no points rather than fabricating coverage.

## How the coverage layer is built

It is computed, not hardcoded. `LithosCatalog.coverage_grid()` walks a coarse global grid
and, for each cell, asks every source whether it declares data there. Cells with at least
one source are marked available (with the source list and density); cells with none are
marked unavailable with the note *"No public InSAR ground-motion product indexed here."*

So when you pan to the middle of an ocean or a stable craton, the map does not go blank
and does not return a misleading zero. It shows the coverage overlay state for that cell,
with a short why. That honesty is the product.

## The shipped hero scene

The default view is a cached scene over Bologna, Italy, a well-documented EGMS subsidence
example. The bundled copy is a **synthetic stand-in** (clearly labelled `source:
sample-demo`, `is_synthetic: true`) so the app renders in under three seconds with no
credentials. Point the EGMS adapter at a real EGMS tile (free Copernicus account) to
replace it with live data.

## Coverage expands over time

The `freshness` job watches the upstream endpoints. If your region is not covered today, the
coverage map will say so, and tell you why.
