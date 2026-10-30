"""Canonical ground-motion schema.

Every data source (EGMS, LiCSAR, and any future product) normalises into these
models. Nothing downstream depends on a source's native format. This is the spine
that makes LITHOS global by design.

Units and conventions:
- Velocities are millimetres per year (mm/yr). Negative = moving away from the
  satellite along the line of sight; for the vertical component, negative = subsidence.
- Displacements in a time series are millimetres relative to the first epoch.
- Longitude/latitude are WGS84 decimal degrees.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AvailabilityStatus(str, Enum):
    """Whether a region has queryable ground-motion data."""

    AVAILABLE = "available"
    SPARSE = "sparse"
    NONE = "none"


class AnomalyType(str, Enum):
    """Kinds of behaviour the anomaly engine reports. Observed motion only."""

    ACCELERATING_SUBSIDENCE = "accelerating_subsidence"
    ACCELERATING_UPLIFT = "accelerating_uplift"
    NEW_ONSET_SUBSIDENCE = "new_onset_subsidence"
    NEW_ONSET_UPLIFT = "new_onset_uplift"
    STABILISING = "stabilising"
    SLOWING = "slowing"
    REVERSAL = "reversal"
    MOTION_HOTSPOT = "motion_hotspot"
    STEADY_MOTION = "steady_motion"
    INCONCLUSIVE = "inconclusive"
    RELATIVE_ONLY = "relative_only"
    STABLE = "stable"


class TimeSeriesSample(BaseModel):
    """One epoch of a displacement time series."""

    date: date
    displacement_mm: float | None = None  # None marks a date with no solution
    uncertainty_mm: float | None = None


class TimeSeries(BaseModel):
    """A full displacement history for one measurement point."""

    point_id: str
    samples: list[TimeSeriesSample] = Field(default_factory=list)

    @field_validator("samples")
    @classmethod
    def _sorted_and_nonempty(cls, v: list[TimeSeriesSample]) -> list[TimeSeriesSample]:
        return sorted(v, key=lambda s: s.date)

    @property
    def dates(self) -> list[date]:
        """The dates with a solution."""
        return [s.date for s in self.samples if s.displacement_mm is not None]

    @property
    def displacements(self) -> list[float]:
        return [s.displacement_mm for s in self.samples if s.displacement_mm is not None]


class MeasurementPoint(BaseModel):
    """A single persistent-scatterer / distributed-scatterer measurement point."""

    id: str
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    height_m: float | None = None

    los_velocity: float | None = None  # mm/yr along line of sight
    vertical_velocity: float | None = None  # mm/yr, negative = subsidence
    horizontal_velocity: float | None = None  # mm/yr east-west where available
    velocity_uncertainty: float | None = None  # mm/yr, half-width of the 95% trend interval

    coherence: float | None = Field(default=None, ge=0, le=1)
    quality: float | None = Field(default=None, ge=0, le=1)

    source: str = "unknown"
    product: str = "unknown"
    processing_window: str | None = None  # e.g. "2019-2023"
    ref_point_id: str | None = None  # what the velocity is relative to, e.g. a GNSS station
    # False when the verdict changed under the build's robustness test; None when untested.
    verdict_robust: bool | None = None
    # Set where independent data disagrees with the datum, so the value is relative only.
    datum_note: str | None = None

    time_series: TimeSeries | None = None

    @property
    def best_velocity(self) -> float | None:
        """Vertical if present (most interpretable), else LOS."""
        return self.vertical_velocity if self.vertical_velocity is not None else self.los_velocity


class Tile(BaseModel):
    """An ingested tile or frame of measurement points."""

    id: str
    source: str
    product_level: str
    bbox: tuple[float, float, float, float]  # minlon, minlat, maxlon, maxlat
    temporal_window: str
    point_count: int = 0
    last_updated: date | None = None
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE


class CoverageCell(BaseModel):
    """A coarse global grid cell describing honest data availability.

    Computed from actual ingested extents, never hardcoded.
    """

    cell_id: str
    bbox: tuple[float, float, float, float]
    available: bool
    sources: list[str] = Field(default_factory=list)
    newest_window: str | None = None
    density_class: str = "none"  # none | sparse | moderate | dense
    note: str | None = None


class SourceMeta(BaseModel):
    """Provenance and honest-coverage description for a data source."""

    key: str
    name: str
    license: str
    attribution: str
    citation: str
    coverage_description: str
    url: str | None = None


class AnomalyFlag(BaseModel):
    """One machine-readable anomaly record. Paired with a human sentence in the verdict."""

    type: AnomalyType
    magnitude_mm_yr: float | None = None
    onset_date: date | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: dict = Field(default_factory=dict)

    @property
    def is_notable(self) -> bool:
        """Notable = the ground is doing something worth a human's attention. Steady
        motion at a real rate counts; stable ground and an unclear trend do not."""
        return self.type not in (
            AnomalyType.STABLE,
            AnomalyType.INCONCLUSIVE,
            AnomalyType.RELATIVE_ONLY,
        )

    @property
    def is_anomalous(self) -> bool:
        """Anomalous = the behaviour changed. Steady motion is notable but not anomalous."""
        return self.is_notable and self.type != AnomalyType.STEADY_MOTION


class PointVerdict(BaseModel):
    """The full result of analysing one point: flags plus a quotable sentence."""

    point_id: str
    velocity_mm_yr: float | None = None
    velocity_uncertainty_mm_yr: float | None = None
    flags: list[AnomalyFlag] = Field(default_factory=list)
    headline: str = ""
    newsworthiness: float = 0.0  # magnitude x acceleration x coherence, for ranking

    @property
    def primary_flag(self) -> AnomalyFlag | None:
        notable = [f for f in self.flags if f.is_notable]
        if not notable:
            return self.flags[0] if self.flags else None
        return max(notable, key=lambda f: (f.confidence, abs(f.magnitude_mm_yr or 0)))
