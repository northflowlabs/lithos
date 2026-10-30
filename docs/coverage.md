# Coverage, honestly

LITHOS is global by design but its data is not yet uniform worldwide, and we will never
pretend otherwise. Honest coverage is a first-class feature, not a footnote.

## What is covered today

| Region | Source | Coverage | Notes |
| --- | --- | --- | --- |
| Bologna, Italy | COMET LiCSAR | Measured scene | October 2021 to April 2024, vertical and east motion |
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
`095D_04589_131313`). Interferograms 12 to 36 days apart are averaged to about 400 m, tied to
the foothills south of the city, inverted into time series for each geometry, and combined into
vertical and east motion over the dates the two frames share. All values are relative to that
reference ground, so the scene shows differential motion, not absolute motion. It has not yet
been compared with EGMS or GNSS. Cells with poor network fit, high ground, wide uncertainty,
implausible sideways motion or no agreement with their neighbours are left out. `data/scenes/bologna/meta.json` records the
build date and the frames.

## Coverage expands over time

The `freshness` job watches the upstream endpoints. If your region is not covered today, the
coverage map will say so, and tell you why.
