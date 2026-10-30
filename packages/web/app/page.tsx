"use client";

import { useQuery } from "@tanstack/react-query";
import type { Map as MlMap } from "maplibre-gl";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AoiPanel from "@/components/AoiPanel";
import { HeroOverlay } from "@/components/HeroOverlay";
import { LayerControls } from "@/components/LayerControls";
import { Legend } from "@/components/Legend";
import type { Layers } from "@/components/MapView";
import { PointList } from "@/components/PointList";
import PointPanel from "@/components/PointPanel";
import { SearchBox } from "@/components/SearchBox";
import { api } from "@/lib/api";
import { ESRI_CREDIT, LICSAR_ACK, OGL_URL } from "@/lib/credits";
import { DEFAULT_LAYERS, decodeState, encodeState, writeHash } from "@/lib/permalink";
import type { AoiScanResult, PointProperties } from "@/lib/types";

// MapLibre touches window; load it client-only.
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

type Bbox = [number, number, number, number];

function roundBbox(b: Bbox): string {
  return b.map((n) => n.toFixed(3)).join(",");
}

// Split a credit so it fits the picture, however narrow the screen it was exported from.
function wrap(ctx: CanvasRenderingContext2D, text: string, width: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(" ")) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

export default function Page() {
  const hero = useQuery({ queryKey: ["hero"], queryFn: api.hero });

  const [view, setView] = useState<{ lon: number; lat: number; zoom: number; bbox: Bbox | null }>({
    lon: 11.39,
    lat: 44.5,
    zoom: 10.5,
    bbox: null,
  });
  const [layers, setLayers] = useState<Layers>(DEFAULT_LAYERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [aoi, setAoi] = useState<{ result: AoiScanResult; geo: { type: "Polygon"; coordinates: number[][][] } } | null>(null);
  const [heroDismissed, setHeroDismissed] = useState(false);
  const [initFromHash, setInitFromHash] = useState(false);
  const [listing, setListing] = useState(false);
  const mapRef = useRef<MlMap | null>(null);

  // Initialise from permalink hash, else from the hero scene center.
  useEffect(() => {
    const decoded = typeof window !== "undefined" ? decodeState(window.location.hash) : null;
    if (decoded && decoded.lon != null) {
      setView((v) => ({ ...v, lon: decoded.lon!, lat: decoded.lat!, zoom: decoded.zoom! }));
      if (decoded.layers) setLayers(decoded.layers);
      if (decoded.selected) setSelectedId(decoded.selected);
      setHeroDismissed(true);
    }
    setInitFromHash(true);
  }, []);

  useEffect(() => {
    if (initFromHash && !view.bbox && hero.data && !decodeState(window.location.hash)) {
      setView((v) => ({ ...v, lon: hero.data.center[0], lat: hero.data.center[1] }));
    }
  }, [hero.data, initFromHash, view.bbox]);

  // Points in the current viewport. The velocity field paints fast (no anomaly
  // computation); anomaly flags are only requested when that layer is enabled, which
  // keeps the hero view under the three-second wow gate.
  const points = useQuery({
    queryKey: ["points", view.bbox ? roundBbox(view.bbox) : null, layers.anomaly],
    queryFn: () => api.points(view.bbox as Bbox, 6000, layers.anomaly),
    enabled: !!view.bbox,
  });

  const coverage = useQuery({
    queryKey: ["coverage-grid"],
    queryFn: api.coverageGrid,
    enabled: layers.coverage,
  });

  const selectedProps: PointProperties | undefined = useMemo(() => {
    if (!selectedId || !points.data) return undefined;
    return points.data.features.find((f) => f.properties.id === selectedId)?.properties;
  }, [selectedId, points.data]);

  const permalink = useMemo(() => {
    if (typeof window === "undefined") return "";
    const enc = encodeState({ ...view, layers, selected: selectedId });
    return `${window.location.origin}${window.location.pathname}#${enc}`;
  }, [view, layers, selectedId]);

  const onMoveEnd = useCallback(
    (lon: number, lat: number, zoom: number, bbox: Bbox) => {
      setView({ lon, lat, zoom, bbox });
    },
    [],
  );

  // Keep the URL in sync for sharing.
  useEffect(() => {
    if (view.bbox) writeHash({ ...view, layers, selected: selectedId });
  }, [view, layers, selectedId]);

  const toggle = (key: keyof Layers) => setLayers((l) => ({ ...l, [key]: !l[key] }));

  const onAoi = async (geo: { type: "Polygon"; coordinates: number[][][] }) => {
    setDrawing(false);
    setSelectedId(null);
    try {
      const result = await api.scanAoi(geo);
      setAoi({ result, geo });
    } catch {
      setAoi({ result: { point_count: 0, note: "Scan failed. Try a smaller area." }, geo });
    }
  };

  const exportPng = () => {
    const map = mapRef.current;
    if (!map) return;
    // The credits must travel with the picture.
    const source = map.getCanvas();
    const canvas = document.createElement("canvas");
    canvas.width = source.width;
    canvas.height = source.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(source, 0, 0);
    const scale = source.width / source.clientWidth;
    const size = 10 * scale;
    ctx.font = `${size}px sans-serif`;
    const lines = [
      LICSAR_ACK,
      `Licence: Open Government Licence v3.0, ${OGL_URL}`,
      `Tiles: ${ESRI_CREDIT}. Map: LITHOS.`,
      ...(hero.data?.caveat ? [hero.data.caveat] : []),
    ].flatMap((text) => wrap(ctx, text, canvas.width - 16 * scale));
    const height = (lines.length + 0.6) * size * 1.3;
    ctx.fillStyle = "rgba(11,14,18,0.8)";
    ctx.fillRect(0, canvas.height - height, canvas.width, height);
    ctx.fillStyle = "#f6f4ef";
    lines.forEach((line, i) => ctx.fillText(line, 8 * scale, canvas.height - height + (i + 1) * size * 1.3));
    const url = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = "lithos-map.png";
    a.click();
  };

  return (
    <main className="relative h-screen w-screen overflow-hidden">
      <MapView
        key={layers.dark ? "dark" : "light"}
        center={[view.lon, view.lat]}
        zoom={view.zoom}
        points={points.data ?? null}
        coverage={coverage.data ?? null}
        layers={layers}
        drawing={drawing}
        selectedId={selectedId}
        onPointClick={(id) => {
          setSelectedId(id);
          setAoi(null);
        }}
        onMoveEnd={onMoveEnd}
        onAoi={onAoi}
        onCancelDraw={() => setDrawing(false)}
        onMapReady={(m) => (mapRef.current = m)}
      />

      <SearchBox
        onPick={(lon, lat) => {
          setHeroDismissed(true);
          mapRef.current?.flyTo({ center: [lon, lat], zoom: 12 });
        }}
      />

      <LayerControls
        layers={layers}
        drawing={drawing}
        onToggle={toggle}
        onDraw={() => setDrawing((d) => !d)}
        onScanView={() => {
          const b = view.bbox;
          if (!b) return;
          onAoi({
            type: "Polygon",
            coordinates: [[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]],
          });
        }}
        onListPoints={() => setListing((l) => !l)}
        onExportPng={exportPng}
      />

      <Legend coverageVisible={layers.coverage} caveat={hero.data?.caveat} />

      {listing && (
        <PointList
          points={points.data?.features ?? []}
          onPick={(id) => {
            setSelectedId(id);
            setAoi(null);
            setListing(false);
          }}
          onClose={() => setListing(false)}
        />
      )}

      {(hero.isError || points.isError || coverage.isError || (heroDismissed && points.data?.features.length === 0)) && (
        <div
          role="status"
          className="pointer-events-none absolute left-1/2 top-16 z-10 w-[280px] max-w-[60vw] -translate-x-[70%] rounded-md border border-ink-700 bg-ink-900/90 px-3 py-2 text-xs text-ink-200 sm:top-4 sm:-translate-x-1/2"
        >
          {hero.isError || points.isError || coverage.isError
            ? "The data could not be loaded. Try again in a moment."
            : "No measured points in this view yet. The coverage layer shows where radar frames exist."}
        </div>
      )}

      {!heroDismissed && hero.data && (
        <HeroOverlay
          name={hero.data.name}
          note={hero.data.note}
          onDismiss={() => setHeroDismissed(true)}
        />
      )}

      {selectedId && (
        <PointPanel
          pointId={selectedId}
          properties={selectedProps}
          permalink={permalink}
          caveat={hero.data?.caveat}
          onClose={() => setSelectedId(null)}
        />
      )}

      {aoi && <AoiPanel result={aoi.result} geojson={aoi.geo} caveat={hero.data?.caveat} onClose={() => setAoi(null)} />}

      <footer className="pointer-events-none absolute bottom-1 right-2 z-10 hidden text-[10px] text-ink-200 sm:block">
        LITHOS · dry-land motion only
      </footer>
    </main>
  );
}
