"""LITHOS core: canonical ground-motion schema and anomaly engine.

Apache-2.0. Standard, openly-published statistics only. No GPL imports,
no maritime detection methodology. See docs/licensing.md and docs/anomaly-engine.md.
"""

from lithos_core.schema import (
    AnomalyFlag,
    AnomalyType,
    AvailabilityStatus,
    CoverageCell,
    MeasurementPoint,
    PointVerdict,
    SourceMeta,
    Tile,
    TimeSeries,
    TimeSeriesSample,
)

__version__ = "0.1.0"

__all__ = [
    "AnomalyFlag",
    "AnomalyType",
    "AvailabilityStatus",
    "CoverageCell",
    "MeasurementPoint",
    "PointVerdict",
    "SourceMeta",
    "Tile",
    "TimeSeries",
    "TimeSeriesSample",
    "__version__",
]
