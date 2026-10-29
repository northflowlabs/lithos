# Licensing

LITHOS is released under **Apache-2.0** (see [`LICENSE`](../LICENSE)). This document
spells out the one boundary that keeps it that way.

## The LiCSAR firewall (the one-way door)

The COMET LiCSAR toolchain (`LiCSBAS`, `licsar_proc`) is **GPL-3.0**. To keep LITHOS
permissively licensed and freely adoptable, we treat LiCSAR strictly as a **data
provider we fetch from over the network**, never as code we vendor or link.

What this means in practice:

1. **LITHOS fetches data products** from the public COMET-LiCS portal/archive over HTTP.
   Fetching and using openly-published data outputs does not impose copyleft on LITHOS.
2. **LITHOS must not** vendor, fork, copy, or statically/dynamically link `LiCSBAS` or
   `licsar_proc` source into this codebase.
3. If LiCSBAS-style time-series processing is genuinely needed beyond what the portal
   serves, the only allowed paths are:
   - (a) call it as an **out-of-process, separately-licensed optional tool** the user
     installs themselves, clearly documented, or
   - (b) **reimplement the standard algorithm independently from public literature**
     under Apache-2.0.
   LITHOS takes path (b): the anomaly engine in `packages/core` is built only from
   standard, openly-published time-series and spatial statistics (Theil-Sen trend,
   binary-segmentation change-points, harmonic seasonal/secular separation, Getis-Ord
   Gi*). It contains no GPL code.

### Enforcement

The firewall is not just a promise:

- `packages/ingest/tests/test_sources.py::test_licsar_never_imports_gpl` asserts the
  LiCSAR adapter imports no `licsbas` / `licsar_proc` package.
- The CI workflow `licensing-firewall` greps the whole `packages/` tree for any such
  import and fails the build if one appears.

## EGMS

EGMS data is open under **Copernicus terms**. Downloads require a free Copernicus
account. We attribute per Copernicus requirements (see [`attribution.md`](attribution.md)).
We call the official EGMS machine-to-machine API directly rather than reusing third-party
toolkit code, to avoid inheriting any incompatible license.

## Scope boundary

LITHOS implements standard, openly-published dry-land subsidence/uplift InSAR analysis
(the same class of capability as SNAP, MintPy, LiCSBAS, EGMS itself). It contains no
maritime detection methodology and no internal Northflow integration. The anomaly engine
is general-purpose ground-motion statistics, nothing more.

## Python and npm naming

- The Python distributions are named in the **`pylithos`** namespace
  (`pylithos-core`, `pylithos-ingest`, `pylithos-api`) because the bare `lithos` name is
  already taken on PyPI. They are not published on PyPI yet. Import modules stay `lithos_core` / `lithos_ingest` / `lithos_api`.
- The web app publishes (if ever) under the npm scope **`@northflow/lithos-web`**.
