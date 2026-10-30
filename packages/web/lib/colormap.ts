// Colourblind-safe diverging ramp for line-of-sight / vertical velocity (mm/yr).
// Blue = rising (uplift), grey = stable, red = sinking (subsidence). Matches the
// ethos of EGMS's colourblind mode: a perceptually balanced RdBu-style ramp.

export const MOTION_STOPS: { v: number; color: string }[] = [
  { v: -20, color: "#b2182b" }, // strong subsidence
  { v: -10, color: "#d6604d" },
  { v: -4, color: "#f4a582" },
  { v: 0, color: "#cfcfcf" }, // stable
  { v: 4, color: "#92c5de" },
  { v: 10, color: "#4393c3" },
  { v: 20, color: "#2166ac" }, // strong uplift
];

// Where a value sits along the ramp, from 0 to 1.
export function rampOffset(v: number): number {
  const lo = MOTION_STOPS[0].v;
  return (v - lo) / (MOTION_STOPS[MOTION_STOPS.length - 1].v - lo);
}

// A MapLibre "interpolate" colour expression keyed on a numeric property.
export function velocityColorExpression(property: string): unknown {
  const stops: unknown[] = [];
  for (const s of MOTION_STOPS) {
    stops.push(s.v, s.color);
  }
  return ["interpolate", ["linear"], ["coalesce", ["get", property], 0], ...stops];
}

// CSS color for a single velocity value (panel, legend, chart).
export function velocityColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "#8a8f98";
  const stops = MOTION_STOPS;
  if (v <= stops[0].v) return stops[0].color;
  if (v >= stops[stops.length - 1].v) return stops[stops.length - 1].color;
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    if (v >= a.v && v <= b.v) {
      const t = (v - a.v) / (b.v - a.v);
      return lerpHex(a.color, b.color, t);
    }
  }
  return "#8a8f98";
}

function lerpHex(a: string, b: string, t: number): string {
  const pa = hexToRgb(a);
  const pb = hexToRgb(b);
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * t);
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * t);
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * t);
  return `rgb(${r}, ${g}, ${bl})`;
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
