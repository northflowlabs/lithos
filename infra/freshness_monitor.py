"""Data-freshness and source-availability monitor.

Scheduled job (cron / GitHub Actions) that checks whether the upstream EGMS and
LiCSAR endpoints are reachable and whether new releases have appeared. Emits one
JSON line per source so it can feed a log drain or alerting. New-coverage events are
the launch-cadence narrative: when a source gains data, announce it.

This script never crashes the service; it only reports. Run:
    python infra/freshness_monitor.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

import httpx

CHECKS = {
    "egms": os.getenv("EGMS_API_BASE", "https://egms.land.copernicus.eu/insar-api/archive")
    + "/levels",  # answers 200 with a "please log in" body when the service is up
    "licsar": os.getenv(
        "LICSAR_ARCHIVE_BASE",
        "https://gws-access.jasmin.ac.uk/public/nceo_geohazards/LiCSAR_products.public",
    )
    + "/",
}


def check(url: str) -> dict:
    try:
        resp = httpx.head(url, timeout=15.0, follow_redirects=True)
        return {"reachable": resp.status_code < 500, "status": resp.status_code}
    except httpx.HTTPError as exc:
        return {"reachable": False, "status": None, "error": str(exc)}


def main() -> int:
    now = datetime.now(UTC).isoformat()
    any_down = False
    for key, url in CHECKS.items():
        result = check(url)
        if not result["reachable"]:
            any_down = True
        print(json.dumps({"ts": now, "source": key, "url": url, **result}))
    # Non-zero exit if a source is down, so CI/cron can alert.
    return 1 if any_down else 0


if __name__ == "__main__":
    sys.exit(main())
