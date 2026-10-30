# @northflow/lithos-web

The LITHOS web application: map-first ground-motion intelligence. Next.js 15 (App
Router) + React 19 + TypeScript + MapLibre GL + TanStack Query + Tailwind.

```bash
pnpm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_LITHOS_API at the API
pnpm dev                           # http://localhost:3000
```

The landing view is the map, already showing the hero scene (no splash wall). Click a
point for its velocity, time series, and a plain-language anomaly verdict. Toggle the
velocity / anomaly / coverage layers. Draw an area to scan it. Every view has a
permalink in the URL. Export PNG, time-series CSV, and AOI GeoJSON.

npm scope: `@northflow/lithos-web` (the bare `lithos` npm name is reserved/unconfirmed).

No Mapbox token: the basemap is keyless Esri raster tiles, under Esri's terms and swappable via
`NEXT_PUBLIC_BASEMAP_*`.
Colours follow a colourblind-safe diverging ramp (blue uplift, grey stable, red sinking).
