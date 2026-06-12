import type { StyleSpecification } from "maplibre-gl";

const LIGHT =
  process.env.NEXT_PUBLIC_BASEMAP_LIGHT || "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png";
const DARK =
  process.env.NEXT_PUBLIC_BASEMAP_DARK || "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png";

const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>. Ground motion: Copernicus EGMS &amp; COMET LiCSAR.';

// A minimal raster basemap style. No Mapbox token, no vendor lock-in. The data layers
// (points, coverage) are added programmatically on top.
export function basemapStyle(dark: boolean): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: {
        type: "raster",
        tiles: [dark ? DARK : LIGHT],
        tileSize: 256,
        attribution: ATTRIBUTION,
        maxzoom: 19,
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": dark ? "#0b0e12" : "#e9e6df" } },
      { id: "basemap", type: "raster", source: "basemap" },
    ],
  };
}
