// Shared types mirroring the LITHOS API contracts.

export interface HeroDescriptor {
  bbox: [number, number, number, number];
  center: [number, number];
  window: string;
  name: string;
  note?: string;
  last_epoch: string;
}

export interface PointProperties {
  id: string;
  vertical_velocity: number | null;
  los_velocity: number | null;
  horizontal_velocity: number | null;
  velocity_uncertainty: number | null;
  best_velocity: number | null;
  coherence: number | null;
  source: string;
  product: string;
  processing_window: string | null;
  anomaly_type?: string | null;
  anomaly_confidence?: number | null;
  anomaly_onset?: string | null;
  headline?: string | null;
  newsworthiness?: number | null;
}

export interface Feature<G, P> {
  type: "Feature";
  geometry: G;
  properties: P;
}

export interface FeatureCollection<G, P> {
  type: "FeatureCollection";
  features: Feature<G, P>[];
  summary?: { queried: number; notable: number };
}

export type PointFeature = Feature<{ type: "Point"; coordinates: [number, number] }, PointProperties>;

export interface TimeSeriesSample {
  date: string;
  displacement_mm: number;
  uncertainty_mm: number | null;
}

export interface TimeSeries {
  point_id: string;
  samples: TimeSeriesSample[];
}

export interface AnomalyFlag {
  type: string;
  magnitude_mm_yr: number | null;
  onset_date: string | null;
  confidence: number;
  evidence: Record<string, unknown>;
}

export interface PointVerdict {
  point_id: string;
  velocity_mm_yr: number | null;
  velocity_uncertainty_mm_yr: number | null;
  flags: AnomalyFlag[];
  headline: string;
  newsworthiness: number;
}

export interface CoverageProperties {
  cell_id: string;
  available: boolean;
  sources: string[];
  newest_window: string | null;
  density_class: string;
  note: string | null;
}

export interface SourceMeta {
  key: string;
  name: string;
  license: string;
  attribution: string;
  citation: string;
  coverage_description: string;
  url: string | null;
}

export interface AoiScanResult {
  point_count: number;
  anomalous_count?: number;
  mean_velocity_mm_yr?: number;
  max_subsidence_mm_yr?: number;
  max_uplift_mm_yr?: number;
  cluster_flags?: AnomalyFlag[];
  top_points?: PointVerdict[];
  note?: string;
}
