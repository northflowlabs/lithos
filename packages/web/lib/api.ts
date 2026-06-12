// Thin typed client for the LITHOS API.

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

export const API_BASE =
  process.env.NEXT_PUBLIC_LITHOS_API?.replace(/\/$/, "") || "http://localhost:8000";

type PolygonGeometry = { type: "Polygon"; coordinates: number[][][] };

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`LITHOS API ${res.status} for ${path}`);
  }
  return res.json() as Promise<T>;
}

export const bboxParam = (b: [number, number, number, number]) => b.join(",");

export const api = {
  hero: () => getJson<HeroDescriptor>("/v1/hero"),

  sources: () => getJson<{ sources: SourceMeta[] }>("/v1/sources"),

  points: (bbox: [number, number, number, number], limit = 5000, withAnomaly = true) =>
    getJson<FeatureCollection<{ type: "Point"; coordinates: [number, number] }, PointProperties>>(
      `/v1/points?bbox=${bboxParam(bbox)}&limit=${limit}&with_anomaly=${withAnomaly}`,
    ),

  anomalies: (bbox: [number, number, number, number], limit = 2000) =>
    getJson<FeatureCollection<{ type: "Point"; coordinates: [number, number] }, PointProperties>>(
      `/v1/anomalies?bbox=${bboxParam(bbox)}&limit=${limit}`,
    ),

  timeSeries: (pointId: string) => getJson<TimeSeries>(`/v1/points/${pointId}/timeseries`),

  verdict: (pointId: string) => getJson<PointVerdict>(`/v1/points/${pointId}/verdict`),

  coverageGrid: () =>
    getJson<FeatureCollection<{ type: "Polygon"; coordinates: number[][][] }, CoverageProperties>>(
      "/v1/coverage/grid",
    ),

  timeSeriesCsvUrl: (pointId: string) => `${API_BASE}/v1/points/${pointId}/timeseries?format=csv`,

  scanAoi: async (polygon: PolygonGeometry): Promise<AoiScanResult> => {
    const res = await fetch(`${API_BASE}/v1/aoi/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ geometry: polygon }),
    });
    if (!res.ok) throw new Error(`AOI scan failed: ${res.status}`);
    return res.json() as Promise<AoiScanResult>;
  },
};

export type { PointFeature };
