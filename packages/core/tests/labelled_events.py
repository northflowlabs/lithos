"""Labelled ground-motion series with a known answer, for the regression suite only.

A detector can only be scored against series whose truth is known, so these prove the
anomaly engine catches known behaviours and does not cry wolf on noise. They live in the
test tree and never reach the map, the API or the package. Every generator returns a
MeasurementPoint with a known ground truth, from a seeded numpy Generator.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from lithos_core.schema import MeasurementPoint, TimeSeries, TimeSeriesSample


def _epochs(start: date, n: int, cadence_days: int = 6) -> list[date]:
    """Sentinel-1 style 6-day cadence by default."""
    return [start + timedelta(days=i * cadence_days) for i in range(n)]


def _build_point(
    point_id: str,
    lon: float,
    lat: float,
    dates: list[date],
    disp: np.ndarray,
    coherence: float,
    velocity: float,
) -> MeasurementPoint:
    samples = [
        TimeSeriesSample(date=d, displacement_mm=float(v)) for d, v in zip(dates, disp)
    ]
    return MeasurementPoint(
        id=point_id,
        lon=lon,
        lat=lat,
        vertical_velocity=velocity,
        los_velocity=velocity,
        coherence=coherence,
        quality=coherence,
        source="test-fixture",
        product="labelled-fixture",
        processing_window=f"{dates[0].year}-{dates[-1].year}",
        time_series=TimeSeries(point_id=point_id, samples=samples),
    )


def steady_subsidence(
    rng: np.random.Generator,
    rate_mm_yr: float = -14.0,
    n: int = 200,
    noise_mm: float = 2.0,
    seasonal_mm: float = 3.0,
    lon: float = 11.34,
    lat: float = 44.49,
    point_id: str = "syn-steady",
) -> MeasurementPoint:
    dates = _epochs(date(2019, 1, 1), n)
    t_years = np.array([(d - dates[0]).days for d in dates]) / 365.25
    disp = rate_mm_yr * t_years
    disp += seasonal_mm * np.sin(2 * np.pi * t_years)
    disp += rng.normal(0, noise_mm, n)
    return _build_point(point_id, lon, lat, dates, disp, 0.85, rate_mm_yr)


def accelerating_subsidence(
    rng: np.random.Generator,
    rate_before: float = -3.0,
    rate_after: float = -22.0,
    onset_year_frac: float = 0.5,
    n: int = 220,
    noise_mm: float = 2.0,
    lon: float = 11.35,
    lat: float = 44.50,
    point_id: str = "syn-accel",
) -> MeasurementPoint:
    dates = _epochs(date(2019, 1, 1), n)
    t_years = np.array([(d - dates[0]).days for d in dates]) / 365.25
    total_years = t_years[-1]
    onset = total_years * onset_year_frac
    disp = np.where(
        t_years <= onset,
        rate_before * t_years,
        rate_before * onset + rate_after * (t_years - onset),
    )
    disp += 2.5 * np.sin(2 * np.pi * t_years)
    disp += rng.normal(0, noise_mm, n)
    return _build_point(point_id, lon, lat, dates, disp, 0.8, rate_after)


def new_onset_subsidence(
    rng: np.random.Generator,
    onset_year_frac: float = 0.55,
    rate_after: float = -18.0,
    n: int = 220,
    noise_mm: float = 1.8,
    lon: float = 11.33,
    lat: float = 44.48,
    point_id: str = "syn-onset",
) -> MeasurementPoint:
    return accelerating_subsidence(
        rng,
        rate_before=0.0,
        rate_after=rate_after,
        onset_year_frac=onset_year_frac,
        n=n,
        noise_mm=noise_mm,
        lon=lon,
        lat=lat,
        point_id=point_id,
    )


def stable_noise(
    rng: np.random.Generator,
    n: int = 200,
    noise_mm: float = 3.0,
    seasonal_mm: float = 4.0,
    lon: float = 11.36,
    lat: float = 44.51,
    point_id: str = "syn-stable",
) -> MeasurementPoint:
    """Pure seasonal swing + noise, no secular trend. Must NOT be flagged."""
    dates = _epochs(date(2019, 1, 1), n)
    t_years = np.array([(d - dates[0]).days for d in dates]) / 365.25
    disp = seasonal_mm * np.sin(2 * np.pi * t_years) + rng.normal(0, noise_mm, n)
    return _build_point(point_id, lon, lat, dates, disp, 0.78, 0.0)


def low_coherence_wild(
    rng: np.random.Generator,
    n: int = 200,
    noise_mm: float = 9.0,
    lon: float = 11.30,
    lat: float = 44.46,
    point_id: str = "syn-lowcoh",
) -> MeasurementPoint:
    """Noisy, low-coherence point. Confidence must be gated down."""
    dates = _epochs(date(2019, 1, 1), n)
    disp = rng.normal(0, noise_mm, n)
    p = _build_point(point_id, lon, lat, dates, disp, 0.25, 0.0)
    return p
