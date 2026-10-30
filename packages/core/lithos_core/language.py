"""Plain-language generation for anomaly flags.

One calm, precise, quotable sentence per verdict. No alarmism, no failure forecasting.
A journalist should be able to paste it as is. Measurements end on a known date, so every
sentence is in the past tense and names its period.
"""

from __future__ import annotations

from datetime import date

from lithos_core.schema import AnomalyFlag, AnomalyType


def _season_phrase(d: date) -> str:
    """A loose, human onset phrase: 'early 2023', 'mid 2021', 'late 2020'."""
    part = "early" if d.month <= 4 else "mid" if d.month <= 8 else "late"
    return f"{part} {d.year}"


def _rate(mm_yr: float | None) -> str:
    if mm_yr is None:
        return "an unknown rate"
    return f"about {abs(mm_yr):.0f} mm per year"


def _period(period: tuple[date, date] | None) -> str:
    if period is None:
        return "over the measured period"
    return f"from {period[0]:%B %Y} to {period[1]:%B %Y}"


def _way(mm_yr: float | None) -> str:
    return "sinking" if (mm_yr or 0) < 0 else "rising"


def headline_for(
    flag: AnomalyFlag,
    velocity_mm_yr: float | None,
    period: tuple[date, date] | None = None,
) -> str:
    """Build the human sentence for a point's primary flag."""
    rate = _rate(velocity_mm_yr)
    when = _period(period)
    onset = _season_phrase(flag.onset_date) if flag.onset_date else "mid-window"
    before = flag.evidence.get("slope_before_mm_yr")
    after = flag.evidence.get("slope_after_mm_yr", flag.magnitude_mm_yr)

    if flag.type in (AnomalyType.ACCELERATING_SUBSIDENCE, AnomalyType.ACCELERATING_UPLIFT):
        return (
            f"This point was {_way(after)} {_rate(before)}, and from around {onset} "
            f"{_rate(after)}, {when}."
        )

    if flag.type in (AnomalyType.NEW_ONSET_SUBSIDENCE, AnomalyType.NEW_ONSET_UPLIFT):
        return (
            f"This point was close to stable, then began {_way(after)} around {onset}, "
            f"at {_rate(after)}, {when}."
        )

    if flag.type == AnomalyType.SLOWING:
        return (
            f"This point was {_way(before)} {_rate(before)}, and slowed to {_rate(after)} "
            f"around {onset}, {when}."
        )

    if flag.type == AnomalyType.REVERSAL:
        return (
            f"This point changed direction around {onset}: it was {_way(before)} "
            f"{_rate(before)}, then {_way(after)} {_rate(after)}, {when}."
        )

    if flag.type == AnomalyType.STABILISING:
        return (
            f"This point was {_way(before)} {_rate(before)}, and was close to stable "
            f"after {onset}, {when}."
        )

    if flag.type == AnomalyType.STEADY_MOTION:
        verb = "sank" if (velocity_mm_yr or 0) < 0 else "rose"
        return f"This point {verb} steadily at {rate} {when}."

    if flag.type == AnomalyType.INCONCLUSIVE:
        return (
            f"This point moved {rate} {when}, but that trend cannot be told apart from "
            "the scatter in its measurements."
        )

    if flag.type == AnomalyType.MOTION_HOTSPOT:
        return f"This area stood out from its surroundings in mean velocity {when}."

    return f"This point showed no significant motion {when}."


def confidence_word(confidence: float) -> str:
    if confidence >= 0.8:
        return "high confidence"
    if confidence >= 0.55:
        return "moderate confidence"
    return "low confidence"
