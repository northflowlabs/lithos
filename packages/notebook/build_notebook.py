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

**Data:** a scene measured from COMET LiCSAR interferograms. It needs no credentials. Copernicus
EGMS tiles (Europe) work too, with a free CLMS API key.

**License:** Apache-2.0. LiCSAR is used as a data source over the network only (see `docs/licensing.md`).
""",
    ),
    cell(
        MD,
        """## 1. Install

LITHOS is installed from its repository, which also holds the measured scenes. The packages
are `pylithos-core` (the engine) and `pylithos-ingest` (data adapters); the import modules are
`lithos_core` and `lithos_ingest`.
""",
    ),
    cell(
        CODE,
        """!git clone --quiet --depth 1 https://github.com/northflowlabs/lithos.git
%cd lithos
%pip install -q ./packages/core ./packages/ingest matplotlib
import os
os.environ["LITHOS_DATA_DIR"] = os.path.abspath("data")
print("LITHOS ready.")
""",
    ),
    cell(
        MD,
        """## 2. Pick a location and pull points

The catalog serves the Bologna scene, measured from Sentinel-1. With a CLMS API key in
`CLMS_SERVICE_KEY` and the `egms` extra, the same call also returns EGMS tiles.
""",
    ),
    cell(
        CODE,
        """from lithos_ingest.base import BBox
from lithos_ingest.catalog import LithosCatalog

# Bologna and the subsiding plain to its north.
bbox = BBox(11.18, 44.40, 11.60, 44.60)

catalog = LithosCatalog()
points = catalog.query_points(bbox)
print(f"Pulled {len(points)} measurement points.")
print("Strongest subsidence:", min(p.best_velocity for p in points if p.best_velocity is not None), "mm/yr")
""",
    ),
    cell(
        MD,
        """## 3. Map the velocity field

Blue rises, red sinks. The plain north of the city is sinking; the city centre barely moves.
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
        """## 6. Where to go next

LITHOS reports observed motion and flags anomalies. Interpretation and engineering judgement
stay with qualified people.

To measure another area, add it to `SCENES` in `lithos_ingest/scene.py` and run
`python -m lithos_ingest.scene <name>`. It needs the `scenes` extra and two frames, one ascending
and one descending, with shared dates.

Please cite LITHOS and the underlying Copernicus and COMET data in any work you publish
(see the repository README).
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
