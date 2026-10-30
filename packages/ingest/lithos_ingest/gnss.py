"""Vertical rates from GNSS stations, processed by the Nevada Geodetic Laboratory.

A radar scene measures motion relative to a point in the scene. A continuous GNSS station
inside the scene gives that point an absolute rate, and stations the scene was not tied to
give an independent check. Cite Blewitt et al. (2018), Eos 99, and the station's data
provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import numpy as np

TENV3_URL = "https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/{station}.tenv3"


# Who runs each station. BOLG is as its RINEX header reads; the institution is unconfirmed.
PROVIDERS = {
    "BOLG": 'RINEX header "GEOFISICA BOLOGNA"',
    "BLGN": "INGV",
    "MEDI": "ASI Telespazio",
    "MSEL": "Unknown",
    "MOPS": "Unknown",
}


@dataclass(frozen=True)
class StationRate:
    station: str
    rate_mm_yr: float
    sigma_mm_yr: float  # 1 sigma, widened for lag-1 autocorrelation of the daily residuals
    days: int
    first: str
    last: str


def parse_tenv3(text: str) -> tuple[np.ndarray, np.ndarray]:
    """Decimal years and vertical position in mm from a tenv3 file."""
    rows = [line.split() for line in text.splitlines()[1:] if line.strip()]
    years = np.array([float(r[2]) for r in rows])
    up_mm = np.array([(float(r[11]) + float(r[12])) * 1000.0 for r in rows])  # u0 + up
    return years, up_mm


def parse_days(text: str) -> tuple[np.ndarray, np.ndarray]:
    """Calendar days as ordinals, sorted, and vertical position in mm."""
    rows = [line.split() for line in text.splitlines()[1:] if line.strip()]
    days = np.array([int(r[3]) + 678576 for r in rows])  # MJD to proleptic ordinal
    up_mm = np.array([(float(r[11]) + float(r[12])) * 1000.0 for r in rows])
    return days, up_mm


def _decimal(d: date) -> float:
    return d.year + (d.timetuple().tm_yday - 1) / 365.25


def fit_rate(station: str, text: str, start: date, end: date) -> StationRate | None:
    """Rate over a window with an annual term, after one 3-sigma pass over the residuals.
    None when the station does not cover at least 80% of the window's length."""
    years, up = parse_tenv3(text)
    a, b = _decimal(start), _decimal(end)
    keep = (years >= a) & (years <= b)
    if keep.sum() < 60 or np.ptp(years[keep]) < 0.8 * (b - a):
        return None
    t = years[keep] - a
    y = up[keep]
    design = np.column_stack(
        [t, np.ones_like(t), np.sin(2 * np.pi * t), np.cos(2 * np.pi * t)]
    )
    coef = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - design @ coef
    good = np.abs(residual) < 3 * residual.std()
    design, y = design[good], y[good]
    coef = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - design @ coef
    dof = max(y.size - design.shape[1], 1)
    covariance = np.linalg.inv(design.T @ design) * float(residual @ residual) / dof
    r = float(residual[:-1] @ residual[1:]) / float(residual @ residual)
    r = min(max(r, 0.0), 0.95)
    widen = np.sqrt((1.0 + r) / (1.0 - r))  # days are not independent: GNSS noise is coloured
    return StationRate(
        station=station,
        rate_mm_yr=round(float(coef[0]), 2),
        sigma_mm_yr=round(float(np.sqrt(covariance[0, 0]) * widen), 2),
        days=int(y.size),
        first=start.isoformat(),
        last=end.isoformat(),
    )


def fetch_text(station: str, timeout: float = 60.0) -> str:
    resp = httpx.get(TENV3_URL.format(station=station), timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def last_day(text: str) -> date:
    """The station's last observation."""
    year = parse_tenv3(text)[0][-1]
    whole = int(year)
    return date(whole, 1, 1) + timedelta(days=int((year - whole) * 365.25))
