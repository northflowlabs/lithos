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
combined into vertical and east motion on the ascending frame's dates, with the descending series
interpolated onto them, and BOLG's measured rate, about -3 mm per year, fixes the vertical datum.
The east motion stays relative to BOLG.

BOLG changed receiver on 2023-06-28, inside the window. The tie fits no step there: the Nevada
Geodetic Laboratory lists none, and a step fitted over 2019 to 2026 comes to about 0.1 mm. Fitted
over the scene's window alone it would be about 2 mm and the rate about -4.3, so that much of the
tie rests on the longer record.

Left out: cells with mean coherence under 0.4, which removes most farmland; poor network fit;
ground above 250 m; too few dates; and cells that disagree with their neighbours. The counts are
in `filters` in `data/scenes/bologna/meta.json`.

### Verdicts have to survive

Every point's verdict is recomputed four more ways at build time: the reference moved 2 km, the
reference at the former BOLO site, no ramp removal, and no pairs under 24 days. A verdict that
changes class in any of them is published as inconclusive. West of 11.45E, 636 of 888 verdicts
held. The change test found 17 candidate changes of behaviour there and none survived, so none is
published: the scene shows trends, not turning points. "Stable" means under 2 mm per year on this
datum, and moving the reference to BOLO shifts the whole scene by about 2 mm per year, so it says
something about the datum as well as the ground.

### How far to trust it

- **Fastest subsidence: about 17 to 26 mm per year**, on the plain northwest of the city. The range
  comes from reading one 400 m cell or the worst 1.5 km patch, the reference location, and ramp
  removal. The choice of pairs moves it too.
- **East of 11.45E the values are relative only.** They are faded and carry no motion verdict. The
  line is a judgement from the scene's pattern and one GNSS site, as no station lies between BLGN
  and MEDI. At MEDI the scene and GNSS differ by 4.7 ± 1.6 mm per year, from cells 3.8 to 4.4 km
  from the station. That they also differ in sign holds only narrowly: GNSS plus that misfit puts
  the scene at +1.8 ± 1.6. The -2.9 in the caveat is GNSS on the 60 SAR dates of the check;
  `gnss.fit_rate` on the daily series over the window gives -2.52 ± 0.46 (1 sigma).
- **Near the tie the check is weak.** At BLGN, 1.3 km from BOLG, the scene is consistent with GNSS
  within about ±4.6 mm per year (95%), over about 13 months. That is not a tight check.
- A trend's "±" is the 95% interval of the fit. It reflects scatter about the trend, not remaining
  atmosphere, the reference or the tie.
- The scene has not been compared with EGMS.

`checks` and `caveat` in `meta.json` hold the current figures; the caveat is worded from them.

### What was tried for the east

No correction for the east is applied, and the repository has no code that fits one. `python -m
lithos_ingest.scene wide` widens the scene to Modena and prints the same-date checks against BOLG,
and nothing more. The scene minus GNSS is -3.1 ± 3.2 mm per year at MOPS, 0.0 ± 3.3 at MODE and
+5.8 ± 1.9 at MEDI (95%).

These figures are weaker than their intervals suggest. They move with the box the atmosphere is
fitted over, by as much as the intervals: MOPS from -3.06 to +0.15, MEDI by about 1.1. That is why
MEDI reads +5.8 ± 1.9 here and 4.69 ± 1.6 in `meta.json`. The cells, dates and GNSS are the same,
but the wide run fits atmosphere and ramp over 10.90E to 11.70E and the published scene over
11.18E to 11.68E.

MOPS and MODE sit 60 m apart and read differently, and MODE's 0.0 is not an agreement. MODE has a
396-day gap, 2022-09 to 2023-10, and resumes at the antenna and radome change the Nevada Geodetic
Laboratory lists for 2023-10-25, so the step cannot be estimated. A trial step of -3 to -5 mm,
which the command does not apply, moves MODE to -1.4 to -2.4.

The cause of the east's rising values is not known. A test against 85 longer pairs (72 to 348
days) for short-pair phase bias was inconclusive: those pairs cluster by season and their dates do
not match the short network's.

## Coverage expands over time

The `freshness` job watches the upstream endpoints. If your region is not covered today, the
coverage map will say so, and tell you why.
