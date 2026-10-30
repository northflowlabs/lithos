"use client";

import { useEffect, useRef } from "react";
import { velocityColor } from "@/lib/colormap";
import type { PointFeature } from "@/lib/types";

interface Props {
  points: PointFeature[];
  onPick: (id: string) => void;
  onClose: () => void;
}

// The map's points as a list, for anyone not using a mouse. Fastest motion first.
export function PointList({ points, onPick, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Relative-only values are not motion, so they never outrank a measured one.
  const shown = [...points]
    .sort(
      (a, b) =>
        Number(a.properties.relative_only ?? false) - Number(b.properties.relative_only ?? false) ||
        Math.abs(b.properties.best_velocity ?? 0) - Math.abs(a.properties.best_velocity ?? 0),
    )
    .slice(0, 15);

  return (
    <nav
      aria-label="Points in view"
      className="absolute left-4 top-16 z-20 max-h-[60vh] w-[230px] overflow-y-auto rounded-md border border-ink-700 bg-ink-900/95 p-2"
    >
      <div className="mb-1 flex items-center justify-between px-1 text-[10px] uppercase tracking-widest text-ink-200">
        <span>Points in view</span>
        <button ref={closeRef} onClick={onClose} aria-label="Close list" className="px-1 text-sm text-ink-200 hover:text-paper">
          ×
        </button>
      </div>
      {shown.length === 0 && <p className="px-1 text-xs text-ink-200">No points in this view.</p>}
      <ul>
        {shown.map((f) => (
          <li key={f.properties.id}>
            <button
              onClick={() => onPick(f.properties.id)}
              className="flex w-full items-baseline justify-between gap-2 rounded px-1 py-1 text-left text-xs text-ink-200 hover:bg-ink-700"
            >
              <span className="font-mono text-[10px]">{f.properties.id}</span>
              {f.properties.relative_only ? (
                <span>relative only</span>
              ) : (
                <span style={{ color: velocityColor(f.properties.best_velocity) }}>
                  {f.properties.best_velocity?.toFixed(1)} mm/yr
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
