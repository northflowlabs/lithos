"""Plain-language generation for anomaly flags.

One calm sentence per verdict, carrying its period, its 95% interval and what it is relative
to. No alarmism, no failure forecasting. It is a summary of one point; the scene's note says how
far absolute values can be trusted, and that note must travel with any quote.
"""

from __future__ import annotations

from datetime import date

from lithos_core.schema import AnomalyFlag, AnomalyType


def _season_phrase(d: date) -> str:
    """A loose, human onset phrase: 'early 2023', 'mid 2021', 'late 2020'."""
    part = "early" if d.month <= 4 else "mid" if d.month <= 8 else "late"
    return f"{part} {d.year}"


def _rate(mm_yr: float | None, interval: float | None = None) -> str:
    if mm_yr is None:
        return "an unknown rate"
    if interval is not None:
        return f"about {abs(mm_yr):.0f} ± {interval:.0f} mm per year (95% interval)"
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
    interval: float | None = None,
    datum: str | None = None,
) -> str:
    """Build the human sentence for a point's primary flag."""
    rate = _rate(velocity_mm_yr, interval)
    when = _period(period)
    relative = f"with the datum tied to {datum} " if datum else ""
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
        return f"This point {verb} steadily at {rate} {relative}{when}."

    if flag.type == AnomalyType.INCONCLUSIVE:
        return (
            f"This point moved {rate} {relative}{when}, but the trend is not firm: it cannot "
            "be told apart from scatter, or it changed when the processing was varied."
        )

    if flag.type == AnomalyType.RELATIVE_ONLY:
        sign = "+" if (velocity_mm_yr or 0) >= 0 else "-"
        reading = rate.replace("about ", f"about {sign}", 1)
        return f"This point reads {reading} {relative}{when}. {flag.evidence.get('note', '')}".strip()

    if flag.type == AnomalyType.MOTION_HOTSPOT:
        return f"This area stood out from its surroundings in mean velocity {when}."

    return f"This point showed no significant motion {relative}{when}."


def confidence_word(confidence: float) -> str:
    if confidence >= 0.8:
        return "high confidence"
    if confidence >= 0.55:
        return "moderate confidence"
    return "low confidence"
