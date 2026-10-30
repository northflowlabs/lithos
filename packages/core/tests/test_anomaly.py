"""Anomaly-engine regression suite against labelled events with a known answer.

Proves the engine catches the real thing (steady motion, acceleration, new onset,
emerging clusters) and does NOT cry wolf on seasonal swings or low-coherence noise.
"""

from __future__ import annotations

import labelled_events
import numpy as np

from lithos_core.anomaly import _classify_change, analyse_point, scan_area
from lithos_core.schema import AnomalyType


def _rng():
    return np.random.default_rng(42)


def test_steady_subsidence_flagged():
    p = labelled_events.steady_subsidence(_rng(), rate_mm_yr=-14.0)
    v = analyse_point(p)
    assert v.primary_flag is not None
    assert v.primary_flag.type in (AnomalyType.STEADY_MOTION,)
    assert v.velocity_mm_yr is not None and v.velocity_mm_yr < -8
    assert "sank" in v.headline


def test_accelerating_subsidence_detected_with_onset():
    p = labelled_events.accelerating_subsidence(_rng(), rate_before=-3, rate_after=-22)
    v = analyse_point(p)
    assert v.primary_flag is not None
    assert v.primary_flag.type == AnomalyType.ACCELERATING_SUBSIDENCE
    assert v.primary_flag.onset_date is not None
    assert v.primary_flag.confidence > 0.4
    assert "from around" in v.headline


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
    assert result.anomalous_count == 0  # steady sinking is a hotspot, not a change
    assert result.max_subsidence_mm_yr < -10
    assert any(f.type == AnomalyType.MOTION_HOTSPOT for f in result.cluster_flags)
    # Most newsworthy point should be from the subsiding bowl.
    assert result.verdicts[0].point_id.startswith("bowl-")


def test_a_change_of_slope_is_named_for_what_the_ground_did():
    assert _classify_change(5.0, -5.0) == AnomalyType.REVERSAL
    assert _classify_change(-5.0, 5.0) == AnomalyType.REVERSAL
    assert _classify_change(-12.0, -6.0) == AnomalyType.SLOWING
    assert _classify_change(12.0, 6.0) == AnomalyType.SLOWING
    assert _classify_change(-6.0, -12.0) == AnomalyType.ACCELERATING_SUBSIDENCE
    assert _classify_change(6.0, 12.0) == AnomalyType.ACCELERATING_UPLIFT
    assert _classify_change(-1.0, -9.0) == AnomalyType.NEW_ONSET_SUBSIDENCE
    assert _classify_change(-9.0, -1.0) == AnomalyType.STABILISING


def test_motion_with_no_clear_trend_is_not_called_stable():
    rng = np.random.default_rng(3)
    p = labelled_events.stable_noise(rng, seasonal_mm=0.0, noise_mm=40.0)
    p.vertical_velocity = 4.5
    p.los_velocity = 4.5
    v = analyse_point(p)
    assert v.primary_flag.type != AnomalyType.STABLE
    assert "no significant motion" not in v.headline


def test_steady_motion_is_not_anomalous():
    result = scan_area([labelled_events.steady_subsidence(_rng(), rate_mm_yr=-14.0)])
    assert result.anomalous_count == 0


def test_a_hotspot_reports_the_ground_it_saw():
    # A sinking area with one patch sinking less: high Gi*, but not uplift.
    rng = _rng()
    points = []
    for i in range(30):
        for j in range(30):
            rate = -6.0 if (i < 6 and j < 6) else -20.0
            p = labelled_events.steady_subsidence(
                rng, rate_mm_yr=rate, lon=11.0 + i * 0.004, lat=44.0 + j * 0.004, point_id=f"p{i}-{j}"
            )
            points.append(p)
    flags = scan_area(points).cluster_flags
    assert flags
    assert all(f.evidence["kind"] != "uplift" for f in flags)


def test_a_contradicted_datum_gives_a_relative_sentence_and_no_motion_claim():
    p = labelled_events.steady_subsidence(_rng(), rate_mm_yr=8.0)
    p.datum_note = "GNSS east of here disagrees, so this is not absolute motion."
    v = analyse_point(p)
    assert v.primary_flag.type == AnomalyType.RELATIVE_ONLY
    assert "rose" not in v.headline and "reads" in v.headline
    assert "not absolute" in v.headline
    assert v.primary_flag.is_notable is False


def test_relative_points_stay_out_of_area_statistics():
    a = labelled_events.steady_subsidence(_rng(), rate_mm_yr=-10.0, point_id="a")
    b = labelled_events.steady_subsidence(_rng(), rate_mm_yr=9.0, point_id="b")
    b.datum_note = "relative only"
    result = scan_area([a, b])
    assert result.point_count == 2
    assert result.left_out_count == 1
    assert result.max_uplift_mm_yr < 0
    assert [v.point_id for v in result.verdicts] == ["a"]


def test_an_area_of_only_relative_points_has_no_statistics():
    b = labelled_events.steady_subsidence(_rng(), rate_mm_yr=9.0, point_id="b")
    b.datum_note = "relative only"
    result = scan_area([b]).to_dict()
    assert result["mean_velocity_mm_yr"] is None
    assert result["max_uplift_mm_yr"] is None
    assert result["left_out_count"] == 1
    assert result["anomalous_count"] is None
    assert "relative only" in result["note"]
