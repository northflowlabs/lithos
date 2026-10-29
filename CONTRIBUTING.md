# Contributing to LITHOS

Thank you for helping make ground-motion data readable for everyone. LITHOS is Apache-2.0 and community-supported.

## Ground rules

1. **Licensing firewall (non-negotiable).** LITHOS is Apache-2.0. The COMET LiCSAR / LiCSBAS toolchain is GPL-3.0. We fetch LiCSAR **data products over the network** only. Do **not** vendor, fork, copy, or link LiCSBAS / `licsar_proc` source into this repo. If you need time-series processing beyond what a portal serves, reimplement the standard algorithm from public literature under Apache-2.0, or call an external tool out-of-process. See [`docs/licensing.md`](docs/licensing.md).
2. **Scope.** LITHOS is dry-land surface motion only. No water, seabed, vessels, or offshore targets. No structural-failure forecasting. The anomaly engine is built from standard, openly-published time-series and spatial statistics only.
3. **Honesty.** Never let copy or UI imply uniform global coverage. Coverage is computed from real ingested extents, never hardcoded.
4. **No em dashes** in user-facing copy or docs.

## Development

```bash
# Python packages (core, ingest, api) use one virtualenv.
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e "packages/core[dev]" -e "packages/ingest[dev]" -e "packages/api[dev]"
# distributions install as pylithos-core / pylithos-ingest / pylithos-api
# (the bare `lithos` name is taken on PyPI); import modules stay lithos_core etc.

# Run the test suite
pytest packages

# Type check
pyright packages/core packages/ingest packages/api

# Web app
cd packages/web && pnpm install && pnpm dev
```

## Adding a new data source

Implement the `GroundMotionSource` protocol in `packages/ingest/lithos_ingest/sources/`. Normalise into the canonical schema in `lithos_core.schema`. Provide a `SourceMeta` with license, attribution, and an honest coverage description. Nothing downstream needs to change. See [`docs/architecture.md`](docs/architecture.md).

## Pull requests

- One logical change per PR. Include tests. CI must be green (lint, typecheck, test, build).
- The anomaly engine has a regression suite of labelled synthetic events; if you touch detection, add a fixture proving it catches the real thing without crying wolf.
- Be calm and precise in any user-facing language: observed motion plus uncertainty, never alarmism.

## Good first issues

Look for the [`good first issue`](https://github.com/northflowlabs/lithos/labels/good%20first%20issue) label: coverage adapters, colourmap accessibility, docs, and notebook examples are great entry points.
