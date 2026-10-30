"use client";

import { useEffect, useRef } from "react";
import { velocityColor } from "@/lib/colormap";
import { exportCredits } from "@/lib/credits";
import type { AoiScanResult } from "@/lib/types";

interface Props {
  result: AoiScanResult;
  geojson: { type: "Polygon"; coordinates: number[][][] } | null;
  caveat?: string | null;
  onClose: () => void;
}

function downloadJson(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

const HOTSPOT_LABEL: Record<string, string> = {
  subsidence: "Sinking hotspot",
  uplift: "Rising hotspot",
  relatively_stable: "Steadier than its surroundings",
};

export default function AoiPanel({ result, geojson, caveat, onClose }: Props) {
  const empty = result.point_count === 0;
  const closeRef = useRef<HTMLButtonElement>(null);
  const rate = (v: number | null | undefined) => (v == null ? "n/a" : `${v.toFixed(1)} mm/yr`);

  useEffect(() => closeRef.current?.focus(), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const exportGeoJson = () => {
    downloadJson("lithos-aoi.geojson", {
      type: "FeatureCollection",
      properties: {
        point_count: result.point_count,
        anomalous_count: result.anomalous_count ?? null,
        mean_velocity_mm_yr: result.mean_velocity_mm_yr,
        max_subsidence_mm_yr: result.max_subsidence_mm_yr,
        max_uplift_mm_yr: result.max_uplift_mm_yr,
        left_out_count: result.left_out_count,
        note: result.note,
        credits: exportCredits(caveat),
      },
      features: geojson ? [{ type: "Feature", geometry: geojson, properties: {} }] : [],
    });
  };

  return (
    <aside className="animate-slide-in absolute right-0 top-0 z-20 flex h-full w-[360px] max-w-[88vw] flex-col bg-ink-900/95 backdrop-blur shadow-panel border-l border-ink-700">
      <header className="flex items-center justify-between px-4 py-3 border-b border-ink-700">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-ink-400">Area scan</div>
          <div className="text-sm text-paper">{result.point_count} points</div>
        </div>
        <button ref={closeRef} onClick={onClose} aria-label="Close panel" className="text-ink-200 hover:text-paper text-lg px-2">
          ×
        </button>
      </header>

      <div className="panel-scroll flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {empty ? (
          <p className="text-sm text-ink-200">{result.note ?? "No indexed ground-motion points in this area."}</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Mean velocity" value={rate(result.mean_velocity_mm_yr)} color={velocityColor(result.mean_velocity_mm_yr)} />
              <Stat label="Changed behaviour" value={`${result.anomalous_count ?? "n/a"}`} />
              <Stat label="Max subsidence" value={rate(result.max_subsidence_mm_yr)} color={velocityColor(result.max_subsidence_mm_yr)} />
              <Stat label="Max uplift" value={rate(result.max_uplift_mm_yr)} color={velocityColor(result.max_uplift_mm_yr)} />
            </div>

            {result.note && <p className="text-xs text-ink-200">{result.note}</p>}
            {!!result.left_out_count && (
              <p className="text-xs text-ink-200">
                {result.left_out_count} of {result.point_count} points are relative only and left out
                of these figures.
              </p>
            )}
            {caveat && <p className="text-xs text-ink-200">{caveat}</p>}

            {result.cluster_flags && result.cluster_flags.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest text-ink-400 mb-1">Hotspots</div>
                <p className="mb-1.5 text-[11px] text-ink-200">
                  Where mean velocity stands out from this area. It does not show when that began.
                </p>
                <ul className="space-y-1.5">
                  {result.cluster_flags.map((c, i) => (
                    <li key={i} className="rounded border-l-2 border-signal bg-ink-800 px-3 py-2 text-xs text-paper">
                      {HOTSPOT_LABEL[String((c.evidence as { kind?: string }).kind)] ?? "Hotspot"}
                      {c.magnitude_mm_yr != null ? `, local mean ${c.magnitude_mm_yr.toFixed(0)} mm/yr` : ""}.
                      <span className="text-ink-200"> Gi* z = {String((c.evidence as { gi_z?: number }).gi_z ?? "")}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.top_points && result.top_points.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest text-ink-400 mb-1">Most newsworthy points</div>
                <ul className="space-y-1 text-xs">
                  {result.top_points.slice(0, 8).map((p) => (
                    <li key={p.point_id} className="flex items-baseline gap-2">
                      <span className="font-mono text-[10px] text-ink-400">{p.point_id}</span>
                      <span style={{ color: velocityColor(p.velocity_mm_yr) }}>
                        {p.velocity_mm_yr?.toFixed(1)} mm/yr
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              onClick={exportGeoJson}
              className="w-full rounded border border-ink-600 bg-ink-800 px-2 py-1.5 text-xs hover:border-ink-400"
            >
              Export AOI GeoJSON
            </button>
          </>
        )}
      </div>
    </aside>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded border border-ink-700 bg-ink-800 px-3 py-2">
      <div className="text-[10px] uppercase tracking-widest text-ink-400">{label}</div>
      <div className="text-sm font-semibold" style={{ color: color ?? "#e9e6df" }}>
        {value}
      </div>
    </div>
  );
}
