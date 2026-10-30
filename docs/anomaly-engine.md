# The anomaly engine

Raw velocity maps tell you what is moving. They do not tell you what *changed*. The LITHOS
anomaly engine (`lithos_core.anomaly`, built on `lithos_core.stats`) surfaces the points
and areas a human eye would miss in a field of thousands. It is built only from standard,
openly-published time-series and spatial statistics. No maritime methodology, no GPL code.

## Per-point analysis (`analyse_point`)

For each measurement point with enough history (at least 12 epochs):

1. **Robust trend**: Theil-Sen slope with a 95% confidence interval, outlier-resistant.
   Gives velocity (mm/yr) and an uncertainty.
2. **Seasonal vs. secular separation**: harmonic regression fits
   `y = a + b·t + c·sin(2πt) + d·cos(2πt)` (t in years), separating an annual seasonal
   cycle from the long-term trend. A reversible seasonal swing is never read as motion.
3. **Change-point detection**: binary segmentation on the *de-seasonalised* series, with
   a nested-model F statistic scaled for autocorrelated residuals. It is a screening threshold,
   not a significance level. A slope needs at least a year on each side. Finds regime shifts,
   with a date.
4. **Classification**: comparing the slope before and after the strongest change-point
   yields: accelerating subsidence or uplift, new-onset subsidence or uplift, slowing, a change
   of direction, stabilising, steady motion, stable, or inconclusive.
5. **Confidence gating**: coherence/quality scales the confidence down so low-quality
   points are not over-flagged.
6. **Robustness test** (scene builds): the scene is solved four more ways: the reference moved
   2 km, the reference at the old BOLO site, no ramp removal, and no pairs under 24 days. A
   verdict that changes class in any of them is published as inconclusive.

### Output contract

Every flag carries:

- **machine-readable:** `type`, `magnitude_mm_yr`, `onset_date`, `confidence`, `evidence`
  (the underlying statistics).
- **human-readable:** one calm sentence with its 95% interval and datum, for example *"This
  point sank steadily at about 14 ± 2 mm per year (95% interval) with the datum tied to GNSS
  station BOLG from October 2021 to April 2024."*
  Sentences are in the past tense and name their period, because the data has an end date. No
  alarmism. No failure prediction.

## Per-area analysis (`scan_area`)

1. Every point is analysed and ranked by **newsworthiness**
   (magnitude × acceleration factor × quality).
2. **Hotspot detection** runs Getis-Ord Gi* over the velocity field with a distance-band
   spatial weights matrix. A strong z marks a place whose mean velocity stands out from the
   area. Gi* is relative and has no time term: it shows where the ground differs, not when
   that began, and a high z in a sinking area may only mean sinking less. The local mean
   decides the reported kind: subsidence, uplift or relatively stable.
3. **Changed behaviour** counts points whose trend changed. Steady motion is notable but
   does not count.

Trend intervals are 95% Theil-Sen intervals. They reflect scatter about the trend, not
remaining atmosphere, the reference or the GNSS tie.

## Validation: catch the real thing, do not cry wolf

The regression suite (`packages/core/tests/test_anomaly.py`) runs the engine against
labelled test series with a known answer, which live in the test tree:

| Fixture | Expected |
| --- | --- |
| Steady subsidence (-14 mm/yr) | flagged as steady motion, velocity recovered |
| Accelerating subsidence (-3 to -22) | accelerating subsidence, onset date found |
| New-onset subsidence | new-onset / accelerating, onset date found |
| Stable seasonal swing | **not** flagged (stable) |
| Low-coherence noise | confidence gated below 0.55 |
| A subsiding bowl in a stable field | hotspot detected, ranked first |

The low-level statistics have their own unit tests in `test_stats.py` (trend recovery,
outlier resistance, seasonal separation, change-point precision, Gi* hotspot detection).

## Why these methods

They are the openly-published standard for this exact problem (PS-InSAR time-series
analysis and spatial hotspot detection), they are explainable to a journalist, and they
keep LITHOS Apache-2.0. The engine reports observed motion and flags anomalies. It does
not forecast structural or geological failure; interpretation stays with qualified people.
