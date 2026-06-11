# lithos-core

The domain heart of LITHOS: the canonical ground-motion schema every data source
normalises into, and the anomaly engine that flags points and areas behaving strangely.

**Licensing boundary.** This package is Apache-2.0 and contains only standard,
openly-published time-series and spatial statistics (robust trend estimation,
change-point detection, harmonic seasonal/secular separation, Getis-Ord hotspot
analysis). It imports no GPL code and no maritime detection methodology.

```python
from lithos_core.schema import MeasurementPoint, TimeSeries
from lithos_core.anomaly import analyse_point, scan_area

verdict = analyse_point(point)
print(verdict.headline)   # "This point has been sinking about 14 mm/year and accelerated after early 2023."
```

See [`docs/anomaly-engine.md`](../../docs/anomaly-engine.md) for the method and the
labelled-event validation suite.
