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
import PointPanel from "@/components/PointPanel";
import { SearchBox } from "@/components/SearchBox";
import { api } from "@/lib/api";
import { DEFAULT_LAYERS, decodeState, encodeState, writeHash } from "@/lib/permalink";
import type { AoiScanResult, PointProperties } from "@/lib/types";

// MapLibre touches window; load it client-only.
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

type Bbox = [number, number, number, number];

function roundBbox(b: Bbox): string {
  return b.map((n) => n.toFixed(3)).join(",");
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
    const url = map.getCanvas().toDataURL("image/png");
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
        onExportPng={exportPng}
      />

      <Legend coverageVisible={layers.coverage} />

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
          onClose={() => setSelectedId(null)}
        />
      )}

      {aoi && <AoiPanel result={aoi.result} geojson={aoi.geo} onClose={() => setAoi(null)} />}

      <footer className="pointer-events-none absolute bottom-1 right-2 z-10 text-[10px] text-ink-400">
        LITHOS · dry-land motion only · LiCSAR contains modified Copernicus Sentinel data analysed by COMET
      </footer>
    </main>
  );
}
