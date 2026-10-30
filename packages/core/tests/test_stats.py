"""Unit tests for the low-level statistics."""

from __future__ import annotations

import numpy as np

from lithos_core import stats


def test_robust_trend_recovers_slope():
    rng = np.random.default_rng(0)
    t_days = np.arange(0, 1200, 6, dtype=float)
    t_years = t_days / 365.25
    y = -10.0 * t_years + rng.normal(0, 1.5, len(t_years))
    res = stats.robust_trend(t_days, y)
    assert abs(res.slope_mm_yr - (-10.0)) < 1.0
    assert res.significant


def test_robust_trend_outlier_resistant():
    rng = np.random.default_rng(1)
    t_days = np.arange(0, 1200, 6, dtype=float)
    t_years = t_days / 365.25
    y = -8.0 * t_years + rng.normal(0, 1.0, len(t_years))
    y[::20] += 60.0  # spikes that would wreck OLS
    res = stats.robust_trend(t_days, y)
    assert abs(res.slope_mm_yr - (-8.0)) < 1.5


def test_harmonic_separates_seasonal_from_secular():
    t_days = np.arange(0, 1460, 6, dtype=float)
    t_years = t_days / 365.25
    y = -5.0 * t_years + 8.0 * np.sin(2 * np.pi * t_years)
    res = stats.harmonic_decompose(t_days, y)
    assert abs(res.secular_slope_mm_yr - (-5.0)) < 0.5
    assert abs(res.seasonal_amplitude_mm - 8.0) < 0.5
    assert res.seasonal_fraction > 0.3


def test_change_point_found_at_onset():
    t_days = np.arange(0, 1460, 6, dtype=float)
    t_years = t_days / 365.25
    onset = 2.0
    y = np.where(t_years <= onset, 0.0, -20.0 * (t_years - onset))
    cps = stats.detect_change_points(t_days, y)
    assert cps, "expected at least one change-point"
    assert abs(cps[0].t_years - onset) < 0.4
    assert cps[0].slope_after_mm_yr < cps[0].slope_before_mm_yr


def test_no_change_point_on_pure_line():
    rng = np.random.default_rng(2)
    t_days = np.arange(0, 1460, 6, dtype=float)
    t_years = t_days / 365.25
    y = -7.0 * t_years + rng.normal(0, 0.8, len(t_years))
    cps = stats.detect_change_points(t_days, y)
    # A clean straight line should not split into strong regimes.
    assert all(abs(c.slope_delta_mm_yr) < 4.0 for c in cps)


def test_getis_ord_flags_cluster():
    # 25 points on a 5x5 grid; a 2x2 corner block has strong negative values.
    coords = [(i, j) for i in range(5) for j in range(5)]
    values = np.zeros(25)
    for idx, (i, j) in enumerate(coords):
        if i < 2 and j < 2:
            values[idx] = -20.0
    n = 25
    w = np.zeros((n, n))
    for a, (ia, ja) in enumerate(coords):
        for b, (ib, jb) in enumerate(coords):
            if abs(ia - ib) <= 1 and abs(ja - jb) <= 1:
                w[a, b] = 1.0
    z = stats.getis_ord_gi_star(values, w)
    # The subsiding corner should be a strong low-cluster (negative z).
    corner = [idx for idx, (i, j) in enumerate(coords) if i < 2 and j < 2]
    assert min(z[corner]) < -1.5


def test_a_break_in_autocorrelated_noise_is_still_found():
    rng = np.random.default_rng(5)
    t = np.arange(150) * 12.0
    hits = 0
    for _ in range(40):
        noise = np.zeros(150)
        for i in range(1, 150):
            noise[i] = 0.5 * noise[i - 1] + rng.normal(0, 1.5)
        years = t / 365.25
        trend = np.where(years < 2.5, -3 * years, -3 * 2.5 - 20 * (years - 2.5))
        hits += bool(stats.detect_change_points(t, trend + noise))
    assert hits >= 30
