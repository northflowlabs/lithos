"""Render a static hero PNG from the hero scene for the README and docs.

The picture shows the measured vertical velocity of the hero scene.
Run: python -m lithos_ingest.render_hero
Requires matplotlib, which is in the dev extras and not a runtime dependency.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from lithos_ingest.base import data_dir
from lithos_ingest.sources.licsar import HERO_SCENE


def render(out_path: Path | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    repo_root = Path(__file__).resolve().parents[3]
    scene = data_dir() / "scenes" / HERO_SCENE
    geo = json.loads((scene / "points.geojson").read_text(encoding="utf-8"))
    meta = json.loads((scene / "meta.json").read_text(encoding="utf-8"))

    lons, lats, vels, alphas = [], [], [], []
    for f in geo["features"]:
        lons.append(f["geometry"]["coordinates"][0])
        lats.append(f["geometry"]["coordinates"][1])
        vels.append(f["properties"].get("vertical_velocity") or 0.0)
        alphas.append(0.35 if f["properties"].get("datum_note") else 1.0)

    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=100)
    fig.patch.set_facecolor("#0b0e12")
    ax.set_facecolor("#0b0e12")
    sc = ax.scatter(lons, lats, c=vels, cmap="RdBu", vmin=-20, vmax=20, s=9, marker="s", edgecolors="none", alpha=alphas)  # type: ignore[arg-type]
    cb = plt.colorbar(sc, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("Vertical velocity (mm/yr)  ·  red sinks, blue rises", color="#e9e6df")
    cb.ax.yaxis.set_tick_params(color="#aab3bd")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="#aab3bd")

    ax.set_title(
        f"LITHOS: {meta['name']}, measured ground motion, {meta['window']}",
        color="#f6f4ef",
        fontsize=13,
        loc="left",
        pad=10,
    )
    ax.tick_params(colors="#aab3bd", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#283039")
    ax.set_xlabel("Longitude", color="#aab3bd", fontsize=9)
    ax.set_ylabel("Latitude", color="#aab3bd", fontsize=9)
    caveat = "\n".join(textwrap.wrap(meta.get("caveat", "") + " Those points are faded.", 118))
    credit = (
        "LiCSAR contains modified Copernicus Sentinel data 2021 to 2024 analysed by the Centre for "
        "the Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET). LiCSAR uses "
        "JASMIN, the UK's collaborative data analysis environment (http://jasmin.ac.uk). Open "
        "Government Licence v3.0."
    )
    fig.text(
        0.02,
        0.0,
        caveat + "\n" + "\n".join(textwrap.wrap(credit, 118)),
        ha="left",
        va="top",
        color="#d6d3cc",
        fontsize=7,
    )

    out_path = out_path or repo_root / "docs" / "assets" / "hero.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    out = render()
    print(f"Hero image written to {out}")


if __name__ == "__main__":
    main()
