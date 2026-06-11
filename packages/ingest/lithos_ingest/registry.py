"""Source registry. Add a source here and it becomes available to the catalog and API."""

from __future__ import annotations

from typing import Callable

from lithos_ingest.base import GroundMotionSource
from lithos_ingest.sources.egms import EgmsSource
from lithos_ingest.sources.licsar import LicsarSource
from lithos_ingest.sources.sample import SampleSource

_FACTORIES: dict[str, Callable[[], GroundMotionSource]] = {
    "sample": SampleSource,
    "egms": EgmsSource,
    "licsar": LicsarSource,
}


def available_sources() -> list[str]:
    return list(_FACTORIES.keys())


def get_source(key: str) -> GroundMotionSource:
    if key not in _FACTORIES:
        raise KeyError(f"Unknown source '{key}'. Available: {available_sources()}")
    return _FACTORIES[key]()
