"use client";

import maplibregl, { type GeoJSONSource, type Map as MlMap } from "maplibre-gl";
import { useCallback, useEffect, useRef } from "react";
import { velocityColorExpression } from "@/lib/colormap";
import type { CoverageProperties, FeatureCollection, PointProperties } from "@/lib/types";
import { basemapStyle } from "./basemap";

type PointFC = FeatureCollection<{ type: "Point"; coordinates: [number, number] }, PointProperties>;
type CoverageFC = FeatureCollection<{ type: "Polygon"; coordinates: number[][][] }, CoverageProperties>;

export interface Layers {
  velocity: boolean;
  anomaly: boolean;
  coverage: boolean;
  dark: boolean;
}

interface MapViewProps {
  center: [number, number];
  zoom: number;
  points: PointFC | null;
  coverage: CoverageFC | null;
  layers: Layers;
  drawing: boolean;
  selectedId: string | null;
  onPointClick: (id: string) => void;
  onMoveEnd: (lon: number, lat: number, zoom: number, bbox: [number, number, number, number]) => void;
  onAoi: (polygon: { type: "Polygon"; coordinates: number[][][] }) => void;
  onMapReady: (map: MlMap) => void;
}

const EMPTY_FC = { type: "FeatureCollection", features: [] } as const;

export default function MapView(props: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const drawStart = useRef<[number, number] | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  const currentBbox = useCallback((map: MlMap): [number, number, number, number] => {
    const b = map.getBounds();
    return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  }, []);

  // --- init once ---------------------------------------------------------------
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: basemapStyle(props.layers.dark),
      center: props.center,
      zoom: props.zoom,
      attributionControl: { compact: true },
      preserveDrawingBuffer: true, // needed for PNG export
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    map.on("load", () => {
      map.addSource("points", { type: "geojson", data: EMPTY_FC as never });
      map.addSource("coverage", { type: "geojson", data: EMPTY_FC as never });
      map.addSource("aoi", { type: "geojson", data: EMPTY_FC as never });

      // Coverage: available (subtle) vs empty (hatched grey), honest by construction.
      map.addLayer({
        id: "coverage-fill",
        type: "fill",
        source: "coverage",
        layout: { visibility: "none" },
        paint: {
          "fill-color": ["case", ["get", "available"], "#2166ac", "#3a3f47"],
          "fill-opacity": ["case", ["get", "available"], 0.12, 0.32],
          "fill-outline-color": ["case", ["get", "available"], "#4393c3", "#5b6571"],
        },
      });

      // Velocity points.
      map.addLayer({
        id: "points-circle",
        type: "circle",
        source: "points",
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            8, 2.5,
            12, 4.5,
            15, 7,
          ],
          "circle-color": velocityColorExpression("best_velocity") as never,
          "circle-stroke-width": 0.4,
          "circle-stroke-color": "rgba(0,0,0,0.35)",
          "circle-opacity": 0.92,
        },
      });

      // Anomaly halo: ring notable points.
      map.addLayer({
        id: "points-anomaly",
        type: "circle",
        source: "points",
        layout: { visibility: "none" },
        filter: ["all", ["has", "anomaly_type"], ["!=", ["get", "anomaly_type"], "stable"]],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 5, 14, 11],
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-width": 1.6,
          "circle-stroke-color": "#e8c547",
          "circle-opacity": 1,
        },
      });

      // Selected point highlight.
      map.addLayer({
        id: "points-selected",
        type: "circle",
        source: "points",
        filter: ["==", ["get", "id"], "___none___"],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 7, 14, 13],
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-width": 2.4,
          "circle-stroke-color": "#ffffff",
        },
      });

      // AOI rectangle while drawing / after scan.
      map.addLayer({
        id: "aoi-fill",
        type: "fill",
        source: "aoi",
        paint: { "fill-color": "#e8c547", "fill-opacity": 0.08 },
      });
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aoi",
        paint: { "line-color": "#e8c547", "line-width": 1.5, "line-dasharray": [2, 1] },
      });

      map.on("click", "points-circle", (e) => {
        const f = e.features?.[0];
        if (f) propsRef.current.onPointClick(f.properties?.id as string);
      });
      map.on("mouseenter", "points-circle", () => {
        if (!propsRef.current.drawing) map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "points-circle", () => {
        map.getCanvas().style.cursor = "";
      });

      // Rectangle AOI draw (no extra dependency).
      map.on("mousedown", (e) => {
        if (!propsRef.current.drawing) return;
        e.preventDefault();
        drawStart.current = [e.lngLat.lng, e.lngLat.lat];
        map.dragPan.disable();
      });
      map.on("mousemove", (e) => {
        if (!propsRef.current.drawing || !drawStart.current) return;
        updateAoiRect(map, drawStart.current, [e.lngLat.lng, e.lngLat.lat]);
      });
      map.on("mouseup", (e) => {
        if (!propsRef.current.drawing || !drawStart.current) return;
        const poly = rectPolygon(drawStart.current, [e.lngLat.lng, e.lngLat.lat]);
        drawStart.current = null;
        map.dragPan.enable();
        propsRef.current.onAoi(poly);
      });

      map.on("moveend", () => {
        const c = map.getCenter();
        propsRef.current.onMoveEnd(c.lng, c.lat, map.getZoom(), currentBbox(map));
      });

      propsRef.current.onMapReady(map);
      // Initial extent callback so the page can fetch points.
      const c = map.getCenter();
      propsRef.current.onMoveEnd(c.lng, c.lat, map.getZoom(), currentBbox(map));
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- react to data/layer changes ---------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    (map.getSource("points") as GeoJSONSource | undefined)?.setData(
      (props.points ?? EMPTY_FC) as never,
    );
  }, [props.points]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    (map.getSource("coverage") as GeoJSONSource | undefined)?.setData(
      (props.coverage ?? EMPTY_FC) as never,
    );
  }, [props.coverage]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("points-circle")) return;
    map.setLayoutProperty("points-circle", "visibility", props.layers.velocity ? "visible" : "none");
    map.setLayoutProperty("points-anomaly", "visibility", props.layers.anomaly ? "visible" : "none");
    map.setLayoutProperty("coverage-fill", "visibility", props.layers.coverage ? "visible" : "none");
  }, [props.layers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("points-selected")) return;
    map.setFilter("points-selected", ["==", ["get", "id"], props.selectedId ?? "___none___"]);
  }, [props.selectedId]);

  // Dark-mode basemap swap is handled by remounting MapView with a key in page.tsx,
  // which re-runs init with the right basemapStyle at the current center/zoom.

  return <div ref={containerRef} className="absolute inset-0" aria-label="Ground-motion map" />;
}

function rectPolygon(a: [number, number], b: [number, number]) {
  const minLon = Math.min(a[0], b[0]);
  const maxLon = Math.max(a[0], b[0]);
  const minLat = Math.min(a[1], b[1]);
  const maxLat = Math.max(a[1], b[1]);
  return {
    type: "Polygon" as const,
    coordinates: [
      [
        [minLon, minLat],
        [maxLon, minLat],
        [maxLon, maxLat],
        [minLon, maxLat],
        [minLon, minLat],
      ],
    ],
  };
}

function updateAoiRect(map: MlMap, a: [number, number], b: [number, number]) {
  const src = map.getSource("aoi") as GeoJSONSource | undefined;
  src?.setData({ type: "Feature", geometry: rectPolygon(a, b), properties: {} } as never);
}
