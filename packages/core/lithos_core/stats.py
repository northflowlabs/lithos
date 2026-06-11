"""Standard time-series statistics for the anomaly engine.

Every method here comes from the open literature on InSAR time-series analysis and
general change detection: robust (Theil-Sen) trend estimation, harmonic regression
for seasonal/secular separation, binary-segmentation change-point detection, and a
two-segment piecewise fit for acceleration. No GPL code, no maritime methodology.

All functions take plain numpy arrays so they are trivially testable and reusable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

# A year expressed in days, used to convert displacement slopes to mm/yr.
DAYS_PER_YEAR = 365.25


@dataclass
class TrendResult:
    slope_mm_yr: float
    intercept_mm: float
    slope_low_mm_yr: float
    slope_high_mm_yr: float
    residual_std_mm: float

    @property
    def uncertainty_mm_yr(self) -> float:
        """Half-width of the Theil-Sen confidence interval, as a 1-sigma-ish proxy."""
        return float(abs(self.slope_high_mm_yr - self.slope_low_mm_yr) / 2.0)

    @property
    def significant(self) -> bool:
        """Slope confidence interval excludes zero."""
        return (self.slope_low_mm_yr > 0) or (self.slope_high_mm_yr < 0)


@dataclass
class SeasonalResult:
    secular_slope_mm_yr: float
    seasonal_amplitude_mm: float
    seasonal_fraction: float  # seasonal amplitude / total signal range, 0..1
    detrended_deseasonalised: np.ndarray = field(repr=False)  # residual only (no trend)
    deseasonalised: np.ndarray = field(repr=False)  # secular trend + residual (seasonal removed)


@dataclass
class ChangePoint:
    index: int
    t_years: float  # time of change measured in years from series start
    score: float  # test statistic strength
    slope_before_mm_yr: float
    slope_after_mm_yr: float

    @property
    def slope_delta_mm_yr(self) -> float:
        return self.slope_after_mm_yr - self.slope_before_mm_yr


def _years_from_start(t_days: np.ndarray) -> np.ndarray:
    return (t_days - t_days[0]) / DAYS_PER_YEAR


def robust_trend(t_days: np.ndarray, y_mm: np.ndarray) -> TrendResult:
    """Theil-Sen robust linear trend. Resistant to outliers, standard for PS-InSAR."""
    t_years = _years_from_start(t_days)
    res = stats.theilslopes(y_mm, t_years, alpha=0.95)
    slope, intercept, lo, hi = float(res[0]), float(res[1]), float(res[2]), float(res[3])
    residuals = y_mm - (slope * t_years + intercept)
    return TrendResult(
        slope_mm_yr=slope,
        intercept_mm=intercept,
        slope_low_mm_yr=lo,
        slope_high_mm_yr=hi,
        residual_std_mm=float(np.std(residuals)),
    )


def harmonic_decompose(t_days: np.ndarray, y_mm: np.ndarray) -> SeasonalResult:
    """Separate secular trend from an annual seasonal cycle by least-squares fit of
    y = a + b*t + c*sin(2*pi*t) + d*cos(2*pi*t), with t in years.

    This is the standard harmonic-regression approach to seasonal/secular separation,
    chosen over STL so the package stays dependency-light and fully Apache-2.0.
    """
    t_years = _years_from_start(t_days)
    omega = 2.0 * np.pi
    design = np.column_stack(
        [
            np.ones_like(t_years),
            t_years,
            np.sin(omega * t_years),
            np.cos(omega * t_years),
        ]
    )
    coef, *_ = np.linalg.lstsq(design, y_mm, rcond=None)
    _a, b, c, d = coef
    secular_slope = float(b)
    seasonal_amp = float(np.hypot(c, d))

    seasonal_component = c * np.sin(omega * t_years) + d * np.cos(omega * t_years)
    trend_component = coef[0] + b * t_years
    residual = y_mm - trend_component - seasonal_component

    signal_range = float(np.ptp(y_mm)) or 1.0
    seasonal_fraction = float(min(1.0, (2.0 * seasonal_amp) / signal_range))

    return SeasonalResult(
        secular_slope_mm_yr=secular_slope,
        seasonal_amplitude_mm=seasonal_amp,
        seasonal_fraction=seasonal_fraction,
        detrended_deseasonalised=residual,
        deseasonalised=y_mm - seasonal_component,
    )


def _segment_slope(t_years: np.ndarray, y_mm: np.ndarray) -> float:
    if len(t_years) < 2:
        return 0.0
    res = stats.theilslopes(y_mm, t_years)
    return float(res[0])


def detect_change_points(
    t_days: np.ndarray,
    y_mm: np.ndarray,
    min_segment: int = 10,
    penalty: float = 14.0,
    max_points: int = 3,
) -> list[ChangePoint]:
    """Binary-segmentation change-point detection on the trend.

    At each candidate split we fit two linear segments and compare against a single
    line with a proper F-test for the two added degrees of freedom:

        F = (improvement / 2) / (RSS_two_segments / (n - 4))

    A split survives only if F exceeds `penalty` (a conservative critical value, well
    above the ~7 you would expect by chance at n in the low hundreds, so we miss
    marginal splits rather than invent them). Recurse into each segment.

    For best results pass a de-seasonalised series so an annual swing is not mistaken
    for a trend change. This is the classic binary-segmentation algorithm (Scott and
    Knott; Bai and Perron style), reimplemented independently under Apache-2.0.
    """
    t_years = _years_from_start(t_days)
    found: list[ChangePoint] = []

    def _rss(ts: np.ndarray, ys: np.ndarray) -> float:
        if len(ts) < 2:
            return 0.0
        slope, intercept = np.polyfit(ts, ys, 1)
        pred = slope * ts + intercept
        return float(np.sum((ys - pred) ** 2))

    def _recurse(lo: int, hi: int, depth: int) -> None:
        if depth >= max_points or (hi - lo) < 2 * min_segment:
            return
        ts, ys = t_years[lo:hi], y_mm[lo:hi]
        base = _rss(ts, ys)
        if base <= 0:
            return
        best_idx, best_stat = -1, 0.0
        for k in range(min_segment, (hi - lo) - min_segment):
            left = _rss(ts[:k], ys[:k])
            right = _rss(ts[k:], ys[k:])
            improvement = base - (left + right)
            n = hi - lo
            # Proper nested-model F-test: 2 extra params for the second segment.
            denom = (left + right) / max(n - 4, 1)
            stat = (improvement / 2.0) / denom if denom > 0 else 0.0
            if stat > best_stat:
                best_stat, best_idx = stat, lo + k
        if best_idx >= 0 and best_stat >= penalty:
            sb = _segment_slope(t_years[lo:best_idx], y_mm[lo:best_idx])
            sa = _segment_slope(t_years[best_idx:hi], y_mm[best_idx:hi])
            found.append(
                ChangePoint(
                    index=best_idx,
                    t_years=float(t_years[best_idx]),
                    score=float(best_stat),
                    slope_before_mm_yr=sb,
                    slope_after_mm_yr=sa,
                )
            )
            _recurse(lo, best_idx, depth + 1)
            _recurse(best_idx, hi, depth + 1)

    _recurse(0, len(t_years), 0)
    found.sort(key=lambda c: c.score, reverse=True)
    return found[:max_points]


def getis_ord_gi_star(
    values: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    """Getis-Ord Gi* local hotspot statistic (z-scores).

    `values` is length n; `weights` is an n x n spatial weights matrix (row i gives the
    neighbourhood of point i, including i itself). Returns a z-score per point: large
    positive = a cluster of high values (e.g. strong subsidence), large negative = a
    cluster of low values. Standard spatial statistics (Getis and Ord, 1992).
    """
    n = len(values)
    x_bar = float(np.mean(values))
    s = float(np.sqrt(np.mean(values**2) - x_bar**2)) or 1e-9

    z = np.zeros(n)
    for i in range(n):
        w = weights[i]
        sum_w = float(np.sum(w))
        sum_w2 = float(np.sum(w**2))
        numerator = float(np.sum(w * values)) - x_bar * sum_w
        denom = s * np.sqrt((n * sum_w2 - sum_w**2) / (n - 1)) if n > 1 else 1e-9
        z[i] = numerator / denom if denom > 0 else 0.0
    return z
