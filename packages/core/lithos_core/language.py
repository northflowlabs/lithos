"""Plain-language generation for anomaly flags.

One calm, precise, quotable sentence per verdict, with uncertainty stated. No
alarmism, no failure forecasting. A journalist should be able to paste it as is.
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


def headline_for(flag: AnomalyFlag, velocity_mm_yr: float | None) -> str:
    """Build the human sentence for a point's primary flag."""
    rate = _rate(velocity_mm_yr)
    onset = _season_phrase(flag.onset_date) if flag.onset_date else None

    if flag.type == AnomalyType.ACCELERATING_SUBSIDENCE:
        base = f"This point has been sinking {rate}"
        return f"{base} and the rate increased after {onset}." if onset else f"{base} and the rate is increasing."

    if flag.type == AnomalyType.ACCELERATING_UPLIFT:
        base = f"This point has been rising {rate}"
        return f"{base} and the rate increased after {onset}." if onset else f"{base} and the rate is increasing."

    if flag.type == AnomalyType.NEW_ONSET_SUBSIDENCE:
        return (
            f"This point was stable, then began sinking around {onset}, now {rate}."
            if onset
            else f"This point has recently begun sinking, now {rate}."
        )

    if flag.type == AnomalyType.NEW_ONSET_UPLIFT:
        return (
            f"This point was stable, then began rising around {onset}, now {rate}."
            if onset
            else f"This point has recently begun rising, now {rate}."
        )

    if flag.type == AnomalyType.STABILISING:
        return (
            f"This point was moving but has slowed and is now close to stable since {onset}."
            if onset
            else "This point was moving but has slowed and is now close to stable."
        )

    if flag.type == AnomalyType.STEADY_MOTION:
        direction = "sinking" if (velocity_mm_yr or 0) < 0 else "rising"
        return f"This point has been {direction} steadily at {rate} over the measured period."

    if flag.type == AnomalyType.EMERGING_CLUSTER:
        return "This area shows a newly forming deformation cluster over the selected window."

    return "This point shows no significant motion over the measured period."


def confidence_word(confidence: float) -> str:
    if confidence >= 0.8:
        return "high confidence"
    if confidence >= 0.55:
        return "moderate confidence"
    return "low confidence"
