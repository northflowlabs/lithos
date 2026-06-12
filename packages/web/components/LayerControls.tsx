"use client";

import type { Layers } from "./MapView";

interface Props {
  layers: Layers;
  drawing: boolean;
  onToggle: (key: keyof Layers) => void;
  onDraw: () => void;
  onExportPng: () => void;
}

function Toggle({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={`flex items-center justify-between gap-3 rounded px-2.5 py-1.5 text-xs transition-colors ${
        on ? "bg-ink-700 text-paper" : "bg-ink-800 text-ink-200 hover:bg-ink-700"
      }`}
    >
      <span>{label}</span>
      <span
        className={`inline-block h-3 w-3 rounded-full border ${on ? "bg-signal border-signal" : "border-ink-400"}`}
      />
    </button>
  );
}

export function LayerControls({ layers, drawing, onToggle, onDraw, onExportPng }: Props) {
  return (
    <div className="absolute top-4 right-4 z-10 flex w-[170px] flex-col gap-1 rounded-md bg-ink-900/85 backdrop-blur p-2 border border-ink-700">
      <div className="px-1 text-[10px] uppercase tracking-widest text-ink-400">Layers</div>
      <Toggle on={layers.velocity} label="Velocity" onClick={() => onToggle("velocity")} />
      <Toggle on={layers.anomaly} label="Anomaly flags" onClick={() => onToggle("anomaly")} />
      <Toggle on={layers.coverage} label="Coverage" onClick={() => onToggle("coverage")} />
      <Toggle on={layers.dark} label="Dark basemap" onClick={() => onToggle("dark")} />
      <div className="mt-1 border-t border-ink-700 pt-1">
        <button
          onClick={onDraw}
          className={`w-full rounded px-2.5 py-1.5 text-xs ${
            drawing ? "bg-signal text-ink-900 font-medium" : "bg-ink-800 text-ink-200 hover:bg-ink-700"
          }`}
        >
          {drawing ? "Drag to draw area" : "Draw area"}
        </button>
        <button
          onClick={onExportPng}
          className="mt-1 w-full rounded bg-ink-800 px-2.5 py-1.5 text-xs text-ink-200 hover:bg-ink-700"
        >
          Export PNG
        </button>
      </div>
    </div>
  );
}
