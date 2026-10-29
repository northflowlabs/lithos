"""Generate the LITHOS Colab notebook from a clean cell list.

Keeping the notebook in a generator avoids hand-editing fragile JSON. Run:
    python packages/notebook/build_notebook.py
to (re)write lithos_quickstart.ipynb.
"""

from __future__ import annotations

import json
from pathlib import Path

MD = "markdown"
CODE = "code"


def cell(kind: str, source: str) -> dict:
    base = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
    if kind == CODE:
        base["outputs"] = []
        base["execution_count"] = None
    return base


CELLS = [
    cell(
        MD,
        """# LITHOS quickstart: see the ground move, in a notebook

This notebook mirrors the LITHOS web flow with zero local install: pick a location, pull
normalised ground-motion points, run the anomaly engine, and plot velocity, a time series,
and the flags.

**Scope:** dry-land surface motion only. Observed motion and anomalies, never failure forecasts.

**Data:** Copernicus EGMS (Europe) and COMET LiCSAR (global belts). This notebook runs on the
cached hero scene by default so it works with no credentials. Add a free Copernicus account to
pull live EGMS tiles.

**License:** Apache-2.0. LiCSAR is used as a data source over the network only (see `docs/licensing.md`).
""",
    ),
    cell(
        MD,
        """## 1. Install

LITHOS ships as `pylithos-core` (the engine) and `pylithos-ingest` (data adapters). The bare
`lithos` name is taken on PyPI, hence the `pylithos` prefix; the import modules are `lithos_core`
and `lithos_ingest`.
""",
    ),
    cell(
        CODE,
        """# In Colab, install from PyPI (once published) or from the repo.
# %pip install pylithos-core pylithos-ingest
# For now, install from a local checkout of the monorepo:
%pip install -q -e packages/core -e packages/ingest matplotlib
print("LITHOS ready.")
""",
    ),
    cell(
        MD,
        """## 2. Pick a location and pull points

The `SampleSource` serves the cached Bologna hero scene offline. To pull live EGMS data, set
`EGMS_USERNAME` / `EGMS_PASSWORD` and use `lithos_ingest.sources.egms.EgmsSource` instead, or
add it to a `LithosCatalog`. The interface is identical.
""",
    ),
    cell(
        CODE,
        """from lithos_ingest.base import BBox
from lithos_ingest.catalog import LithosCatalog

# Bologna subsidence bowl (the hero scene).
bbox = BBox(11.27, 44.43, 11.47, 44.57)

catalog = LithosCatalog()              # sample + egms + licsar; degrades gracefully
points = catalog.query_points(bbox)
print(f"Pulled {len(points)} measurement points.")
print("Strongest subsidence:", min(p.best_velocity for p in points if p.best_velocity is not None), "mm/yr")
""",
    ),
    cell(
        MD,
        """## 3. Map the velocity field

Blue rises, red sinks. The bowl should be obvious.
""",
    ),
    cell(
        CODE,
        """import matplotlib.pyplot as plt

lons = [p.lon for p in points]
lats = [p.lat for p in points]
vels = [p.best_velocity or 0.0 for p in points]

fig, ax = plt.subplots(figsize=(7, 5))
sc = ax.scatter(lons, lats, c=vels, cmap="RdBu", vmin=-20, vmax=20, s=12)
plt.colorbar(sc, label="Vertical velocity (mm/yr)")
ax.set_title("LITHOS: Bologna ground motion")
ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
plt.show()
""",
    ),
    cell(
        MD,
        """## 4. Run the anomaly engine on one point

Click-equivalent: pick the most newsworthy point and read its verdict.
""",
    ),
    cell(
        CODE,
        """from lithos_core.anomaly import analyse_point

verdicts = [analyse_point(p) for p in points]
verdicts.sort(key=lambda v: v.newsworthiness, reverse=True)
top = verdicts[0]

print("Most newsworthy point:", top.point_id)
print("Velocity:", top.velocity_mm_yr, "mm/yr")
print("Verdict:", top.headline)
if top.primary_flag:
    print("Flag:", top.primary_flag.type.value, "| confidence", round(top.primary_flag.confidence, 2))
""",
    ),
    cell(
        CODE,
        """# Plot that point's displacement history with its onset, if any.
p = next(p for p in points if p.id == top.point_id)
ts = p.time_series
dates = [s.date for s in ts.samples]
disp = [s.displacement_mm for s in ts.samples]

fig, ax = plt.subplots(figsize=(7, 3))
ax.plot(dates, disp, lw=1.2)
ax.axhline(0, ls="--", lw=0.6, color="grey")
if top.primary_flag and top.primary_flag.onset_date:
    ax.axvline(top.primary_flag.onset_date, color="orange", lw=1, label="onset")
    ax.legend()
ax.set_title(f"{top.point_id}: {top.headline}")
ax.set_ylabel("Displacement (mm)")
plt.show()
""",
    ),
    cell(
        MD,
        """## 5. Scan an area for emerging clusters

The spatial scan (Getis-Ord Gi*) surfaces newly forming subsidence or uplift bowls.
""",
    ),
    cell(
        CODE,
        """from lithos_core.anomaly import scan_area

result = scan_area(points, cluster_radius_deg=0.01)
print(f"Points: {result.point_count}  Anomalous: {result.anomalous_count}")
print(f"Mean velocity: {result.mean_velocity_mm_yr:.1f} mm/yr")
print(f"Max subsidence: {result.max_subsidence_mm_yr:.1f} mm/yr")
for c in result.cluster_flags:
    print("Cluster:", c.evidence.get("kind"), "Gi* z =", c.evidence.get("gi_z"))
""",
    ),
    cell(
        MD,
        """## 6. Worked examples to try next

Swap the bbox and re-run. With Copernicus credentials and the EGMS adapter you can pull any of
these live. Without credentials, only the cached Bologna scene returns points.

- **Bologna, Italy**: `BBox(11.27, 44.43, 11.47, 44.57)` (subsidence bowl, the hero scene).
- **Mexico City**: `BBox(-99.30, 19.20, -98.95, 19.60)` (extreme groundwater subsidence; needs a global source).
- **Groningen, Netherlands**: `BBox(6.50, 53.15, 6.95, 53.45)` (gas-extraction subsidence; EGMS).

LITHOS reports observed motion and flags anomalies. Interpretation and engineering judgement
stay with qualified people. Please cite LITHOS and the underlying Copernicus / COMET data in any
work you publish (see the repository README).
""",
    ),
]


def build() -> dict:
    return {
        "cells": CELLS,
        "metadata": {
            "colab": {"provenance": [], "name": "lithos_quickstart.ipynb"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    out = Path(__file__).resolve().parent / "lithos_quickstart.ipynb"
    out.write_text(json.dumps(build(), indent=1), encoding="utf-8")
    print(f"Wrote {out} ({len(CELLS)} cells).")


if __name__ == "__main__":
    main()
