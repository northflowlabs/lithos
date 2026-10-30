"use client";

import { MOTION_STOPS } from "@/lib/colormap";

// Velocity ramp legend, colourblind-safe. Always visible so the map is readable at a glance.
export function Legend({ coverageVisible }: { coverageVisible: boolean }) {
  const gradient = `linear-gradient(to right, ${MOTION_STOPS.map((s) => s.color).join(", ")})`;
  return (
    <div className="absolute bottom-10 left-4 z-10 rounded-md bg-ink-900/85 backdrop-blur px-3 py-2.5 border border-ink-700 text-[10px] text-ink-200 w-[220px]">
      <div className="uppercase tracking-widest text-ink-200 mb-1">Vertical velocity (mm/yr)</div>
      <div className="h-2.5 rounded" style={{ background: gradient }} />
      <div className="flex justify-between mt-1">
        <span>-20 sinking</span>
        <span>0</span>
        <span>+20 rising</span>
      </div>
      {coverageVisible && (
        <div className="mt-2 pt-2 border-t border-ink-700 space-y-1">
          <div className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: "rgba(33,102,172,0.4)" }} />
            <span>Sentinel-1 frames in the archive</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: "rgba(58,63,71,0.7)" }} />
            <span>No frames indexed</span>
          </div>
        </div>
      )}
    </div>
  );
}
