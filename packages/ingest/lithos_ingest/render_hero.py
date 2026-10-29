"""Render a static hero PNG from the cached hero scene for the README and docs.

This is the launch-day screenshot stand-in: the velocity field of the Bologna
subsidence bowl. Run: python -m lithos_ingest.render_hero
Requires matplotlib (a docs/dev dependency, not a runtime one).
"""

from __future__ import annotations

import json
from pathlib import Path


def render(out_path: Path | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    repo_root = Path(__file__).resolve().parents[3]
    samples = repo_root / "data" / "samples" / "hero_points.geojson"
    geo = json.loads(samples.read_text(encoding="utf-8"))

    lons, lats, vels = [], [], []
    for f in geo["features"]:
        lons.append(f["geometry"]["coordinates"][0])
        lats.append(f["geometry"]["coordinates"][1])
        vels.append(f["properties"].get("vertical_velocity") or 0.0)

    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=100)
    fig.patch.set_facecolor("#0b0e12")
    ax.set_facecolor("#0b0e12")
    sc = ax.scatter(lons, lats, c=vels, cmap="RdBu", vmin=-20, vmax=20, s=14, edgecolors="none")
    cb = plt.colorbar(sc, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("Vertical velocity (mm/yr)  ·  red sinks, blue rises", color="#e9e6df")
    cb.ax.yaxis.set_tick_params(color="#aab3bd")
    plt.setp(plt.getp(cb.ax.axes, "yticklabels"), color="#aab3bd")

    ax.set_title(
        "LITHOS: Bologna ground motion, 2019 to 2023",
        color="#f6f4ef",
        fontsize=13,
        loc="left",
        pad=10,
    )
    ax.tick_params(colors="#5b6571", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#283039")
    ax.set_xlabel("Longitude", color="#aab3bd", fontsize=9)
    ax.set_ylabel("Latitude", color="#aab3bd", fontsize=9)
    ax.text(
        0.99,
        0.01,
        "Cached demonstration scene · Source ethos: Copernicus EGMS",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        color="#5b6571",
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
