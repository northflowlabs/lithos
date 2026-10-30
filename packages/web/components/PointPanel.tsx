"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, timeSeriesToCsv } from "@/lib/api";
import { velocityColor } from "@/lib/colormap";
import { exportCredits } from "@/lib/credits";
import type { PointProperties } from "@/lib/types";
import { CiteBox } from "./CiteBox";
import TimeSeriesChart from "./TimeSeriesChart";

interface Props {
  pointId: string;
  properties?: PointProperties;
  permalink: string;
  caveat?: string | null;
  onClose: () => void;
}

const ANOMALY_LABEL: Record<string, string> = {
  accelerating_subsidence: "Accelerating subsidence",
  accelerating_uplift: "Accelerating uplift",
  new_onset_subsidence: "New onset subsidence",
  new_onset_uplift: "New onset uplift",
  stabilising: "Stabilising",
  slowing: "Slowing",
  reversal: "Changed direction",
  steady_motion: "Steady motion",
  inconclusive: "No firm trend",
  relative_only: "Relative only, GNSS disagrees",
  stable: "Stable",
};

function confidenceWord(c: number): string {
  if (c >= 0.8) return "high confidence";
  if (c >= 0.55) return "moderate confidence";
  return "low confidence";
}

export default function PointPanel({ pointId, properties, permalink, caveat, onClose }: Props) {
  const ts = useQuery({ queryKey: ["ts", pointId], queryFn: () => api.timeSeries(pointId) });
  const verdict = useQuery({ queryKey: ["verdict", pointId], queryFn: () => api.verdict(pointId) });

  // A permalink can open a point outside the view, so its fields are read from where it lies.
  const lon = ts.data?.lon;
  const lat = ts.data?.lat;
  const located = useQuery({
    queryKey: ["point", pointId],
    enabled: !properties && lon != null && lat != null,
    queryFn: async () => {
      const box: [number, number, number, number] = [lon! - 0.001, lat! - 0.001, lon! + 0.001, lat! + 0.001];
      const near = await api.points(box, 100, false);
      return near.features.find((f) => f.properties.id === pointId)?.properties ?? null;
    },
  });
  const point = properties ?? located.data ?? undefined;
  const relative =
    point?.relative_only || ts.data?.relative_only || verdict.data?.flags?.some((f) => f.type === "relative_only");

  const v = point?.best_velocity ?? verdict.data?.velocity_mm_yr ?? null;
  const flag = verdict.data?.flags?.find((f) => f.type !== "stable") ?? verdict.data?.flags?.[0] ?? null;
  const headline = verdict.data?.headline ?? point?.headline ?? "";
  const failed = ts.isError || verdict.isError;
  const missing = !failed && !ts.isLoading && !verdict.isLoading && v === null && !headline;

  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), [pointId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside className="animate-slide-in absolute right-0 top-0 z-20 flex h-full w-[360px] max-w-[88vw] flex-col bg-ink-900/95 backdrop-blur shadow-panel border-l border-ink-700">
      <header className="flex items-center justify-between px-4 py-3 border-b border-ink-700">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-ink-400">Measurement point</div>
          <div className="font-mono text-sm text-paper">{pointId}</div>
        </div>
        <button
          ref={closeRef}
          onClick={onClose}
          aria-label="Close panel"
          className="text-ink-200 hover:text-paper text-lg leading-none px-2"
        >
          ×
        </button>
      </header>

      <div className="panel-scroll flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {failed && <p className="text-sm text-ink-200">This point could not be loaded. Try again in a moment.</p>}
        {missing && (
          <p className="text-sm text-ink-200">This point is not in the current data. The link may be from an older build.</p>
        )}
        {/* velocity headline number */}
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold" style={{ color: velocityColor(v) }}>
              {v === null ? "n/a" : `${v > 0 ? "+" : ""}${v.toFixed(1)}`}
            </span>
            <span className="text-sm text-ink-200">
              mm/year, vertical{relative ? ", relative only" : ""}
            </span>
          </div>
          {point?.velocity_uncertainty != null && (
            <div className="text-xs text-ink-200">
              ± {point.velocity_uncertainty.toFixed(1)} mm/yr, 95% interval of the trend. It
              leaves out remaining atmosphere and the GNSS tie.
            </div>
          )}
          {caveat && <div className="mt-1 text-xs text-ink-200">{caveat}</div>}
        </div>

        {/* plain-language verdict */}
        {headline && (
          <blockquote className="rounded-md border-l-2 border-signal bg-ink-800 px-3 py-2 text-sm text-paper">
            {headline}
            {flag && (
              <div className="mt-1.5 text-[11px] text-ink-200">
                {ANOMALY_LABEL[flag.type] ?? flag.type} · {confidenceWord(flag.confidence)}
                {flag.onset_date ? ` · onset ${flag.onset_date}` : ""}
              </div>
            )}
          </blockquote>
        )}

        {/* time series */}
        <div>
          <div className="text-[10px] uppercase tracking-widest text-ink-400 mb-1">Displacement history</div>
          {ts.isLoading && <div className="text-xs text-ink-200">Loading…</div>}
          {ts.data && <TimeSeriesChart series={ts.data} onset={flag?.onset_date} flag={flag} />}
        </div>

        {/* metadata */}
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
          <dt className="text-ink-400">Source</dt>
          <dd className="text-ink-200">{point?.source ?? "n/a"}</dd>
          <dt className="text-ink-400">Product</dt>
          <dd className="text-ink-200">{point?.product ?? "n/a"}</dd>
          <dt className="text-ink-400">Window</dt>
          <dd className="text-ink-200">{point?.processing_window ?? "n/a"}</dd>
          <dt className="text-ink-400">Coherence</dt>
          <dd className="text-ink-200">{point?.coherence?.toFixed(2) ?? "n/a"}</dd>
        </dl>

        {/* export */}
        <div className="flex gap-2">
          <button
            disabled={!ts.data}
            onClick={() => {
              if (!ts.data) return;
              const blob = new Blob([timeSeriesToCsv(ts.data, exportCredits(caveat))], { type: "text/csv" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `${pointId}.csv`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="flex-1 text-center rounded border border-ink-600 bg-ink-800 px-2 py-1.5 text-xs hover:border-ink-400 disabled:opacity-40"
          >
            Export CSV
          </button>
        </div>
      </div>

      <footer className="px-4 py-3 border-t border-ink-700">
        <CiteBox permalink={permalink} />
      </footer>
    </aside>
  );
}
