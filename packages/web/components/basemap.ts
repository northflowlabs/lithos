import type { StyleSpecification } from "maplibre-gl";

// Esri ArcGIS Online canvas tiles, which need no API key. Either can be replaced with
// NEXT_PUBLIC_BASEMAP_LIGHT or NEXT_PUBLIC_BASEMAP_DARK ({z}/{x}/{y} or {z}/{y}/{x} URL).
const esri = (service: string) => `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/${service}/MapServer/tile/{z}/{y}/{x}`;
const LIGHT = process.env.NEXT_PUBLIC_BASEMAP_LIGHT || esri("World_Light_Gray_Base");
const DARK = process.env.NEXT_PUBLIC_BASEMAP_DARK || esri("World_Dark_Gray_Base");

const ATTRIBUTION =
  'Tiles &copy; <a href="https://www.esri.com">Esri</a>, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors. Ground motion: COMET LiCSAR, contains modified Copernicus Sentinel data.';

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
        // The canvas tiles stop at zoom 16; MapLibre scales them up beyond that.
        maxzoom: 16,
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": dark ? "#0b0e12" : "#e9e6df" } },
      { id: "basemap", type: "raster", source: "basemap" },
    ],
  };
}
