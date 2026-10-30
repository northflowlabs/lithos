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
in `filters` in `data/scenes/bologna/meta.json`. Before the coherence filter, every cell rising
faster than 8 mm per year had coherence under 0.5. Those were fields, whose short-pair phase is
known to be biased, not uplift.

### How far to trust it

- The fastest subsidence is about 20 mm per year, north and west of the city. Single 400 m cells
  reach 21. That peak held across coherence thresholds and moved about 2 mm per year with the
  reference location, so read it as about 20, not as an exact figure.
- A trend's "±" is the 95% interval of the fit. It reflects scatter about the trend, not remaining
  atmosphere, the reference or the tie.
- Away from BOLG, absolute values can be off by several mm per year. Against stations the scene was
  not tied to, it differs by about 4 mm per year at BLGN, over the 13 months the two overlap, and by
  about 5 at MEDI, from cells 3 km from the station. `checks` in `meta.json` has the numbers. It has
  not been compared with EGMS.

## Coverage expands over time

The `freshness` job watches the upstream endpoints. If your region is not covered today, the
coverage map will say so, and tell you why.
