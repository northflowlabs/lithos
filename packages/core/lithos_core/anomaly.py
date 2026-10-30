"""The LITHOS anomaly engine.

Turns a measurement point's time series into a PointVerdict (flags + a quotable
sentence), and an area of points into ranked, newsworthy spatial findings. Built
only from the standard statistics in `stats.py`.

Design principles:
- Observed motion and anomalies only. Never a structural-failure forecast.
- Quality-gated: low-coherence points are not over-flagged.
- Uncertainty travels with every number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from lithos_core import stats
from lithos_core.language import headline_for
from lithos_core.schema import (
    AnomalyFlag,
    AnomalyType,
    MeasurementPoint,
    PointVerdict,
)

# Thresholds. Conservative on purpose: we would rather miss a marginal flag than
# cry wolf. All in mm/yr unless noted.
STABLE_VELOCITY = 2.0  # |velocity| below this is treated as not moving
ACCEL_DELTA = 4.0  # change in slope across a change-point to call "acceleration"
MIN_COHERENCE = 0.4  # below this, downweight confidence
MIN_SAMPLES = 12  # need at least this many epochs to analyse
MIN_SEGMENT_DAYS = 365  # a slope needs a full seasonal cycle on either side of a change


def _epoch_days(ts_dates: list[date]) -> np.ndarray:
    origin = ts_dates[0]
    return np.array([(d - origin).days for d in ts_dates], dtype=float)


def _onset_date(start: date, t_years: float) -> date:
    return start + timedelta(days=round(t_years * stats.DAYS_PER_YEAR))


def _quality_factor(point: MeasurementPoint) -> float:
    """Map coherence/quality to a 0.4..1.0 confidence multiplier."""
    q = point.coherence if point.coherence is not None else point.quality
    if q is None:
        return 0.85
    if q >= MIN_COHERENCE:
        return float(0.6 + 0.4 * min(1.0, (q - MIN_COHERENCE) / (1.0 - MIN_COHERENCE)))
    return float(0.4 * (q / MIN_COHERENCE))


def _datum(point: MeasurementPoint) -> str | None:
    return f"GNSS station {point.ref_point_id}" if point.ref_point_id else None


def _classify_change(before: float, after: float) -> AnomalyType:
    """Name a change of slope by what the ground did, so the sentence cannot contradict
    the numbers. A slope going more negative is not subsidence if the point was rising."""
    was_stable = abs(before) < STABLE_VELOCITY
    now_stable = abs(after) < STABLE_VELOCITY
    if was_stable and not now_stable:
        return AnomalyType.NEW_ONSET_SUBSIDENCE if after < 0 else AnomalyType.NEW_ONSET_UPLIFT
    if now_stable:
        return AnomalyType.STABILISING
    if before * after < 0:
        return AnomalyType.REVERSAL
    if abs(after) > abs(before):
        return AnomalyType.ACCELERATING_SUBSIDENCE if after < 0 else AnomalyType.ACCELERATING_UPLIFT
    return AnomalyType.SLOWING


def analyse_point(point: MeasurementPoint) -> PointVerdict:
    """Full single-point analysis. Returns flags plus a calm headline sentence."""
    ts = point.time_series
    velocity = point.best_velocity

    if ts is None or len(ts.dates) < MIN_SAMPLES:
        # Not enough history to say anything about change; report velocity if known.
        flag = AnomalyFlag(
            type=AnomalyType.INCONCLUSIVE
            if velocity is not None and abs(velocity) >= STABLE_VELOCITY
            else AnomalyType.STABLE,
            magnitude_mm_yr=velocity,
            confidence=0.3,
            evidence={"reason": "insufficient_time_series"},
        )
        return PointVerdict(
            point_id=point.id,
            velocity_mm_yr=velocity,
            velocity_uncertainty_mm_yr=point.velocity_uncertainty,
            flags=[flag],
            headline=headline_for(flag, velocity, None, point.velocity_uncertainty, _datum(point)),
            newsworthiness=abs(velocity or 0.0) * 0.1,
        )

    t_days = _epoch_days(ts.dates)
    y = np.asarray(ts.displacements, dtype=float)
    start = ts.dates[0]
    period = (ts.dates[0], ts.dates[-1])

    # Velocity, interval and significance all come from the series with its season removed.
    seasonal = stats.harmonic_decompose(t_days, y)
    trend = stats.robust_trend(t_days, seasonal.deseasonalised)
    # Detect regime changes on the de-seasonalised series so an annual swing is not
    # misread as a trend change.
    span_per_date = float(t_days[-1] - t_days[0]) / max(len(t_days) - 1, 1)
    min_segment = max(10, int(np.ceil(MIN_SEGMENT_DAYS / max(span_per_date, 1.0))))
    change_points = stats.detect_change_points(
        t_days, seasonal.deseasonalised, min_segment=min_segment
    )

    secular = seasonal.secular_slope_mm_yr
    obs_velocity = velocity if velocity is not None else trend.slope_mm_yr
    qf = _quality_factor(point)

    flags: list[AnomalyFlag] = []

    # 1. Acceleration / new onset / stabilising from the strongest change-point.
    strongest = change_points[0] if change_points else None
    if strongest and abs(strongest.slope_delta_mm_yr) >= ACCEL_DELTA:
        onset = _onset_date(start, strongest.t_years)
        before, after = strongest.slope_before_mm_yr, strongest.slope_after_mm_yr
        conf = float(min(0.95, 0.5 + 0.1 * np.log1p(strongest.score)) * qf)
        evidence = {
            "slope_before_mm_yr": round(before, 2),
            "slope_after_mm_yr": round(after, 2),
            "change_score": round(strongest.score, 2),
            "n_change_points": len(change_points),
        }
        atype = _classify_change(before, after)

        flags.append(
            AnomalyFlag(
                type=atype,
                magnitude_mm_yr=after,
                onset_date=onset,
                confidence=conf,
                evidence=evidence,
            )
        )

    # 2. Steady secular motion (no strong change-point but clearly moving).
    if not flags:
        moving = abs(obs_velocity) >= STABLE_VELOCITY
        if moving and trend.significant:
            flags.append(
                AnomalyFlag(
                    type=AnomalyType.STEADY_MOTION,
                    magnitude_mm_yr=obs_velocity,
                    confidence=float(min(0.9, 0.6 + 0.05 * abs(obs_velocity)) * qf),
                    evidence={
                        "secular_slope_mm_yr": round(secular, 2),
                        "seasonal_fraction": round(seasonal.seasonal_fraction, 2),
                        "slope_ci_mm_yr": [
                            round(trend.slope_low_mm_yr, 2),
                            round(trend.slope_high_mm_yr, 2),
                        ],
                    },
                )
            )
        else:
            flags.append(
                AnomalyFlag(
                    type=AnomalyType.INCONCLUSIVE if moving else AnomalyType.STABLE,
                    magnitude_mm_yr=obs_velocity,
                    confidence=float(0.7 * qf),
                    evidence={
                        "seasonal_fraction": round(seasonal.seasonal_fraction, 2),
                        "residual_std_mm": round(trend.residual_std_mm, 2),
                    },
                )
            )

    primary = max(flags, key=lambda f: (f.is_notable, f.confidence))
    if point.datum_note:
        primary = AnomalyFlag(
            type=AnomalyType.RELATIVE_ONLY,
            magnitude_mm_yr=obs_velocity,
            confidence=float(0.4 * qf),
            evidence={"reason": "datum_contradicted", "note": point.datum_note},
        )
        flags = [primary]
    elif point.verdict_robust is False:
        # The class changed when the build varied the processing, so it is not published.
        primary = AnomalyFlag(
            type=AnomalyType.INCONCLUSIVE,
            magnitude_mm_yr=obs_velocity,
            confidence=float(0.4 * qf),
            evidence={"reason": "changed_under_robustness_test"},
        )
        flags = [primary]
    accel_factor = 1.0
    if primary.type in (
        AnomalyType.ACCELERATING_SUBSIDENCE,
        AnomalyType.ACCELERATING_UPLIFT,
        AnomalyType.NEW_ONSET_SUBSIDENCE,
        AnomalyType.NEW_ONSET_UPLIFT,
    ):
        accel_factor = 2.0
    # A value that is relative only has no place in a ranking of motion.
    newsworthiness = 0.0 if point.datum_note else float(abs(obs_velocity) * accel_factor * qf)
    interval = round(
        point.velocity_uncertainty
        if point.velocity_uncertainty is not None
        else trend.ci95_half_width_mm_yr,
        2,
    )

    return PointVerdict(
        point_id=point.id,
        velocity_mm_yr=round(obs_velocity, 2),
        velocity_uncertainty_mm_yr=interval,
        flags=flags,
        headline=headline_for(primary, obs_velocity, period, interval, _datum(point)),
        newsworthiness=newsworthiness,
    )


@dataclass
class AreaScanResult:
    point_count: int
    anomalous_count: int
    mean_velocity_mm_yr: float | None  # None when no usable point remains
    max_subsidence_mm_yr: float | None
    max_uplift_mm_yr: float | None
    verdicts: list[PointVerdict]
    cluster_flags: list[AnomalyFlag]
    left_out_count: int = 0  # relative-only points, kept out of the statistics
    note: str | None = None

    def to_dict(self) -> dict:
        def rounded(value: float | None) -> float | None:
            return None if value is None else round(value, 2)

        return {
            "point_count": self.point_count,
            "anomalous_count": self.anomalous_count,
            "left_out_count": self.left_out_count,
            "note": self.note,
            "mean_velocity_mm_yr": rounded(self.mean_velocity_mm_yr),
            "max_subsidence_mm_yr": rounded(self.max_subsidence_mm_yr),
            "max_uplift_mm_yr": rounded(self.max_uplift_mm_yr),
            "cluster_flags": [f.model_dump(mode="json") for f in self.cluster_flags],
            "top_points": [v.model_dump(mode="json") for v in self.verdicts[:25]],
        }


def _spatial_weights(points: list[MeasurementPoint], radius_deg: float) -> np.ndarray:
    """Binary distance-band spatial weights including self, for Getis-Ord Gi*."""
    n = len(points)
    coords = np.array([[p.lon, p.lat] for p in points])
    w = np.zeros((n, n))
    r2 = radius_deg**2
    for i in range(n):
        d2 = np.sum((coords - coords[i]) ** 2, axis=1)
        w[i] = (d2 <= r2).astype(float)
    return w


def scan_area(
    points: list[MeasurementPoint],
    cluster_radius_deg: float = 0.01,
    hotspot_z: float = 2.5,
) -> AreaScanResult:
    """Analyse every point, then run Getis-Ord Gi* over velocities to find hotspots:
    places whose mean velocity stands out from the area. Gi* has no time term, so a
    hotspot says where the ground differs, not when that began."""
    verdicts = [analyse_point(p) for p in points]
    relative = {p.id for p in points if p.datum_note}
    verdicts = [v for v in verdicts if v.point_id not in relative]
    verdicts.sort(key=lambda v: v.newsworthiness, reverse=True)

    # Values that are relative only do not enter the area's statistics or its ranking.
    total = len(points)
    points = [p for p in points if not p.datum_note]
    velocities = np.array(
        [p.best_velocity if p.best_velocity is not None else 0.0 for p in points]
    )
    anomalous = sum(
        1 for v in verdicts if v.primary_flag is not None and v.primary_flag.is_anomalous
    )

    cluster_flags: list[AnomalyFlag] = []
    if len(points) >= 8:
        weights = _spatial_weights(points, cluster_radius_deg)
        gi = stats.getis_ord_gi_star(velocities, weights)
        # Gi* is relative to the area: a high z in a sinking city can still be sinking,
        # just less. The sign of the local mean decides what the ground actually did.
        local_mean = (weights @ velocities) / weights.sum(axis=1)
        for idx in {int(np.argmin(gi)), int(np.argmax(gi))}:
            if abs(gi[idx]) < hotspot_z:
                continue
            local = float(local_mean[idx])
            if local <= -STABLE_VELOCITY:
                kind = "subsidence"
            elif local >= STABLE_VELOCITY:
                kind = "uplift"
            else:
                kind = "relatively_stable"
            cluster_flags.append(
                AnomalyFlag(
                    type=AnomalyType.MOTION_HOTSPOT,
                    magnitude_mm_yr=local,
                    confidence=float(min(0.95, abs(gi[idx]) / 6.0)),
                    evidence={
                        "kind": kind,
                        "gi_z": round(float(gi[idx]), 2),
                        "center_lon": points[idx].lon,
                        "center_lat": points[idx].lat,
                    },
                )
            )

    return AreaScanResult(
        point_count=total,
        anomalous_count=anomalous,
        left_out_count=len(relative),
        note=(
            "Every point here is relative only, so the area has no statistics."
            if relative and not points
            else None
        ),
        mean_velocity_mm_yr=float(np.mean(velocities)) if len(velocities) else None,
        max_subsidence_mm_yr=float(np.min(velocities)) if len(velocities) else None,
        max_uplift_mm_yr=float(np.max(velocities)) if len(velocities) else None,
        verdicts=verdicts,
        cluster_flags=cluster_flags,
    )
