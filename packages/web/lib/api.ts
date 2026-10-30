// Typed client for the LITHOS API, with a static-data fallback.
//
// Resolution order per call:
//   1. If NEXT_PUBLIC_LITHOS_API is set, try the live API.
//   2. On any failure (or if it is unset), fall back to bundled static hero assets.
// This makes the public Vercel deploy render the full hero with no backend, while a
// configured deployment uses the live engine (AOI clustering, any-bbox queries).

import { staticData } from "./staticData";
import type {
  AoiScanResult,
  CoverageProperties,
  FeatureCollection,
  HeroDescriptor,
  PointFeature,
  PointProperties,
  PointVerdict,
  SourceMeta,
  TimeSeries,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_LITHOS_API?.replace(/\/$/, "") || "";
export const STATIC_ONLY = API_BASE === "";

type PointFC = FeatureCollection<{ type: "Point"; coordinates: [number, number] }, PointProperties>;
type CoverageFC = FeatureCollection<{ type: "Polygon"; coordinates: number[][][] }, CoverageProperties>;
type PolygonGeometry = { type: "Polygon"; coordinates: number[][][] };

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`LITHOS API ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

// Try the live API, fall back to a static loader on any error.
async function withFallback<T>(remote: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
  if (STATIC_ONLY) return fallback();
  try {
    return await remote();
  } catch {
    return fallback();
  }
}

export const bboxParam = (b: [number, number, number, number]) => b.join(",");

export const api = {
  hero: () => withFallback<HeroDescriptor>(() => getJson("/v1/hero"), staticData.hero),

  sources: () => getJson<{ sources: SourceMeta[] }>("/v1/sources"),

  points: (bbox: [number, number, number, number], limit = 5000, withAnomaly = true) =>
    withFallback<PointFC>(
      () =>
        getJson(
          `/v1/points?bbox=${bboxParam(bbox)}&limit=${limit}&with_anomaly=${withAnomaly}`,
        ),
      () => staticData.points(withAnomaly),
    ),

  anomalies: (bbox: [number, number, number, number], limit = 2000) =>
    withFallback<PointFC>(
      () => getJson(`/v1/anomalies?bbox=${bboxParam(bbox)}&limit=${limit}`),
      staticData.anomalies,
    ),

  timeSeries: (pointId: string) =>
    withFallback<TimeSeries>(
      () => getJson(`/v1/points/${pointId}/timeseries`),
      () => staticData.timeSeries(pointId),
    ),

  verdict: (pointId: string) =>
    withFallback<PointVerdict>(
      () => getJson(`/v1/points/${pointId}/verdict`),
      () => staticData.verdict(pointId),
    ),

  coverageGrid: () =>
    withFallback<CoverageFC>(() => getJson("/v1/coverage/grid"), staticData.coverageGrid),

  scanAoi: (polygon: PolygonGeometry): Promise<AoiScanResult> =>
    withFallback<AoiScanResult>(
      async () => {
        const res = await fetch(`${API_BASE}/v1/aoi/scan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ geometry: polygon }),
        });
        if (!res.ok) throw new Error(`AOI scan failed: ${res.status}`);
        return res.json() as Promise<AoiScanResult>;
      },
      () => staticData.scanAoi(polygon),
    ),
};

// Build a CSV download for a time series client-side, so export works in static mode too.
export function timeSeriesToCsv(ts: TimeSeries): string {
  const rows = ["date,displacement_mm,uncertainty_mm"];
  for (const s of ts.samples) {
    rows.push(`${s.date},${s.displacement_mm ?? ""},${s.uncertainty_mm ?? ""}`);
  }
  return rows.join("\n");
}

export type { PointFeature };
