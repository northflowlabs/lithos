# Coverage, honestly

LITHOS is global by design but its data is not yet uniform worldwide, and we will never
pretend otherwise. Honest coverage is a first-class feature, not a footnote.

## What is covered today

| Region | Source | Coverage | Notes |
| --- | --- | --- | --- |
| Bologna, Italy | COMET LiCSAR, tied to GNSS | Measured scene | October 2021 to April 2024, vertical and east motion |
| Everywhere the archive holds frames | COMET LiCSAR | Frames indexed; points once a scene is built | Not uniform; density varies by region |
| Copernicus Participating States | Copernicus EGMS | Dense, validated, millimetre grade | Active only with a CLMS API key; rolling five-year releases |

### LiCSAR

The archive publishes interferograms, not point velocities. `python -m lithos_ingest.frames`
crawls it into a committed index of every frame, with its footprint and newest acquisition.
Points exist where `python -m lithos_ingest.scene` has solved a scene; elsewhere the adapter
returns none rather than inventing them. Some older products are withheld on the archive,
which is why a scene's window can start later than its frame.

### EGMS

Copernicus Participating States only. Without a CLMS API key the adapter returns no points and
its coverage is reported as unavailable. Its footprint is a coarse box; the EGMS search decides
per query which tiles exist.

## How the coverage layer is built

It is computed, not hardcoded. `LithosCatalog.coverage_grid()` walks a 5 degree global grid and
marks a cell available when a source extent overlaps it, with the frame count and the newest
acquisition. Cells with none are marked unavailable with the note *"No public InSAR
ground-motion product indexed here."* A covered cell means the archive holds frames there, not
that LITHOS has solved them into points.

## The hero scene

The default view is Bologna, Italy, measured from two LiCSAR frames (`117A_04454_131312` and
`095D_04589_131313`). The window is what was solved: October 2021 to April 2024, ending where the
ascending frame stops. Earlier products on the descending frame are withheld on the archive.

Interferograms up to 60 days apart are averaged to about 400 m. For each one, a fit over the
ground south of the city removes the height-dependent atmosphere and the east-west ramp. Each is
then tied to the ground around GNSS station BOLG. Pairs that break phase closure or disagree with
the network are dropped, and the rest are inverted into a series for each geometry. The two are
combined into vertical and east motion on the dates they share, and BOLG's measured rate, about
-3 mm per year, fixes the vertical datum. The east motion stays relative to BOLG.

Left out: cells with mean coherence under 0.4, which removes most farmland; poor network fit;
ground above 250 m; too few dates; and cells that disagree with their neighbours. The counts are
in `filters` in `data/scenes/bologna/meta.json`.

### Verdicts have to survive

Every point's verdict is recomputed four more ways at build time: the reference moved 2 km, the
reference at the former BOLO site, no ramp removal, and no pairs under 24 days. A verdict that
changes class in any of them is published as inconclusive. In this build no change of behaviour
survived, so none is published: the scene shows trends, not turning points. About 760 of 1,069
verdicts held. "Stable" means under 2 mm per year on this datum, and moving the reference to BOLO
shifts the whole scene by about 2 mm per year, so it is a statement about the datum as well as the
ground.

### How far to trust it

- **Fastest subsidence: about 17 to 24 mm per year**, on the plain northwest of the city. The range
  has four causes: a single 400 m cell against the median of the worst 1.5 km patch (about 23 and
  18), the reference location (about 2), ramp removal (about 1), and the seasonal term, which is
  now removed from every rate because the window runs from autumn to spring.
- **East of 11.45E the values are relative only.** The rates there are shown faded and carry no
  motion verdict. At MEDI the scene reads about +2 mm per year where GNSS reads about -3, the
  opposite sign. The nearest usable cells are 3.8 to 4.4 km from the station.
- **Near the tie the scene agrees with GNSS.** At BLGN, 1.2 km from BOLG, the same-date double
  difference agrees within 0.3 mm per year, over the 12 months the records share.
- A trend's "±" is the 95% interval of the fit. It reflects scatter about the trend, not remaining
  atmosphere, the reference or the tie. The tie's own 1 sigma, about 0.5 mm per year, allows for
  correlated GNSS noise, but not for other long-period noise.
- The scene has not been compared with EGMS.

### What was tried for the east

A plane through the GNSS stations was the natural correction, and it was not applied. With the
scene widened to Modena, the error against GNSS is about -3 to -1 mm per year at MOPS and MODE, near
zero at BOLG, and +7 at MEDI. A plane through those leaves about 2 mm per year at its own stations,
and the error is not linear: it steps up between 11.45E and 11.5E, where the coherent ground breaks
into islands separated by farmland. That points to the islands not being tied to the city, which a
plane cannot fix, and only one site constrains the east.

The cause of the rising cells is unproven. Short-pair phase bias over fields was the first
suspect, so the 85 longer pairs (72 to 348 days) were compared with the short network. The
difference does not grow as coherence falls in a consistent way: ascending 3.9 to 1.9 mm per year
from low to high coherence, descending 0.8 to 1.9. And the east-west contrast in vertical rate is
the same in both, about 4.6 mm per year. So bias is not shown, and it does not explain the east.
Long pairs read about 3.5 mm per year lower than short ones everywhere, which is also unexplained.
With only 85 pairs that is a weak test.

## Coverage expands over time

The `freshness` job watches the upstream endpoints. If your region is not covered today, the
coverage map will say so, and tell you why.
