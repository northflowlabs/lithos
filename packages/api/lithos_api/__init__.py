"""LITHOS public API: FastAPI REST + GraphQL over the canonical ground-motion data."""

from lithos_api.app import create_app

__all__ = ["create_app"]
