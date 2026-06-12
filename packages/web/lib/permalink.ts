// Full app state encoded in the URL hash so any view is shareable and quotable.
// Format: #lon/lat/zoom/layers/selectedPointId

export interface AppState {
  lon: number;
  lat: number;
  zoom: number;
  layers: { velocity: boolean; anomaly: boolean; coverage: boolean; dark: boolean };
  selected?: string | null;
}

const DEFAULT_LAYERS = { velocity: true, anomaly: false, coverage: false, dark: false };

function encodeLayers(l: AppState["layers"]): string {
  return [l.velocity ? "v" : "", l.anomaly ? "a" : "", l.coverage ? "c" : "", l.dark ? "d" : ""]
    .filter(Boolean)
    .join("");
}

function decodeLayers(s: string): AppState["layers"] {
  return {
    velocity: s.includes("v"),
    anomaly: s.includes("a"),
    coverage: s.includes("c"),
    dark: s.includes("d"),
  };
}

export function encodeState(s: AppState): string {
  const parts = [
    s.lon.toFixed(5),
    s.lat.toFixed(5),
    s.zoom.toFixed(2),
    encodeLayers(s.layers) || "-",
  ];
  if (s.selected) parts.push(encodeURIComponent(s.selected));
  return parts.join("/");
}

export function decodeState(hash: string): Partial<AppState> | null {
  const clean = hash.replace(/^#/, "");
  if (!clean) return null;
  const parts = clean.split("/");
  if (parts.length < 3) return null;
  const lon = parseFloat(parts[0]);
  const lat = parseFloat(parts[1]);
  const zoom = parseFloat(parts[2]);
  if ([lon, lat, zoom].some((n) => Number.isNaN(n))) return null;
  const layers = parts[3] && parts[3] !== "-" ? decodeLayers(parts[3]) : DEFAULT_LAYERS;
  const selected = parts[4] ? decodeURIComponent(parts[4]) : null;
  return { lon, lat, zoom, layers, selected };
}

export function writeHash(s: AppState): void {
  const encoded = encodeState(s);
  if (typeof window !== "undefined") {
    window.history.replaceState(null, "", `#${encoded}`);
  }
}

export { DEFAULT_LAYERS };
