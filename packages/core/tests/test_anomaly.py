"""Anomaly-engine regression suite against labelled events with a known answer.

Proves the engine catches the real thing (steady motion, acceleration, new onset,
emerging clusters) and does NOT cry wolf on seasonal swings or low-coherence noise.
"""

from __future__ import annotations

import labelled_events
import numpy as np

from lithos_core.anomaly import analyse_point, scan_area
from lithos_core.schema import AnomalyType


def _rng():
    return np.random.default_rng(42)


def test_steady_subsidence_flagged():
    p = labelled_events.steady_subsidence(_rng(), rate_mm_yr=-14.0)
    v = analyse_point(p)
    assert v.primary_flag is not None
    assert v.primary_flag.type in (AnomalyType.STEADY_MOTION,)
    assert v.velocity_mm_yr is not None and v.velocity_mm_yr < -8
    assert "sinking" in v.headline


def test_accelerating_subsidence_detected_with_onset():
    p = labelled_events.accelerating_subsidence(_rng(), rate_before=-3, rate_after=-22)
    v = analyse_point(p)
    assert v.primary_flag is not None
    assert v.primary_flag.type == AnomalyType.ACCELERATING_SUBSIDENCE
    assert v.primary_flag.onset_date is not None
    assert v.primary_flag.confidence > 0.4
    assert "increased after" in v.headline


def test_new_onset_subsidence_detected():
    p = labelled_events.new_onset_subsidence(_rng(), rate_after=-18)
    v = analyse_point(p)
    assert v.primary_flag is not None
    assert v.primary_flag.type in (
        AnomalyType.NEW_ONSET_SUBSIDENCE,
        AnomalyType.ACCELERATING_SUBSIDENCE,
    )
    assert v.primary_flag.onset_date is not None


def test_stable_seasonal_not_flagged():
    p = labelled_events.stable_noise(_rng(), seasonal_mm=5.0, noise_mm=3.0)
    v = analyse_point(p)
    assert v.primary_flag is not None
    assert v.primary_flag.type == AnomalyType.STABLE
    assert v.primary_flag.is_notable is False


def test_low_coherence_confidence_gated():
    p = labelled_events.low_coherence_wild(_rng())
    v = analyse_point(p)
    assert v.primary_flag is not None
    # Even if something is flagged, confidence must be gated low for junk points.
    assert v.primary_flag.confidence < 0.55


def test_newsworthiness_orders_accel_above_steady():
    accel = analyse_point(labelled_events.accelerating_subsidence(_rng()))
    steady = analyse_point(labelled_events.steady_subsidence(_rng(), rate_mm_yr=-14))
    assert accel.newsworthiness > steady.newsworthiness


def test_area_scan_finds_subsidence_cluster():
    rng = _rng()
    points = []
    # A subsiding bowl of 9 points clustered tightly, plus stable background.
    for k in range(9):
        points.append(
            labelled_events.steady_subsidence(
                rng,
                rate_mm_yr=-18.0,
                lon=11.34 + 0.001 * (k % 3),
                lat=44.49 + 0.001 * (k // 3),
                point_id=f"bowl-{k}",
            )
        )
    for k in range(12):
        points.append(
            labelled_events.stable_noise(
                rng,
                lon=11.40 + 0.002 * k,
                lat=44.55 + 0.001 * k,
                point_id=f"bg-{k}",
            )
        )
    result = scan_area(points, cluster_radius_deg=0.005)
    assert result.point_count == 21
    assert result.anomalous_count >= 9
    assert result.max_subsidence_mm_yr < -10
    assert any(f.type == AnomalyType.EMERGING_CLUSTER for f in result.cluster_flags)
    # Most newsworthy point should be from the subsiding bowl.
    assert result.verdicts[0].point_id.startswith("bowl-")
