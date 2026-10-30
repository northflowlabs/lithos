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
   a proper nested-model F-test gate (conservative, so we miss marginal splits rather than
   invent them). Finds regime shifts and the onset of acceleration, with a date.
4. **Classification**: comparing the slope before and after the strongest change-point
   yields: accelerating subsidence, accelerating uplift, new-onset subsidence/uplift,
   stabilising, steady motion, or stable.
5. **Confidence gating**: coherence/quality scales the confidence down so low-quality
   points are not over-flagged.

### Output contract

Every flag carries:

- **machine-readable:** `type`, `magnitude_mm_yr`, `onset_date`, `confidence`, `evidence`
  (the underlying statistics).
- **human-readable:** one calm, precise, quotable sentence with uncertainty stated, for
  example *"This point has been sinking about 14 mm/year and the rate increased after early
  2023."* No alarmism. No failure prediction.

## Per-area analysis (`scan_area`)

1. Every point is analysed and ranked by **newsworthiness**
   (magnitude × acceleration factor × quality).
2. **Emerging-cluster detection** runs Getis-Ord Gi* over the velocity field with a
   distance-band spatial weights matrix. A strong negative z marks a forming subsidence
   bowl; a strong positive z marks uplift. Each cluster is reported with its z-score and
   centre.

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
| A subsiding bowl in a stable field | emerging cluster detected, ranked first |

The low-level statistics have their own unit tests in `test_stats.py` (trend recovery,
outlier resistance, seasonal separation, change-point precision, Gi* hotspot detection).

## Why these methods

They are the openly-published standard for this exact problem (PS-InSAR time-series
analysis and spatial hotspot detection), they are explainable to a journalist, and they
keep LITHOS Apache-2.0. The engine reports observed motion and flags anomalies. It does
not forecast structural or geological failure; interpretation stays with qualified people.
