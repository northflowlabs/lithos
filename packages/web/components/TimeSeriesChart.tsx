"use client";

import { useMemo } from "react";
import type { AnomalyFlag, TimeSeries } from "@/lib/types";

interface Props {
  series: TimeSeries;
  onset?: string | null;
  flag?: AnomalyFlag | null;
  width?: number;
  height?: number;
}

const MAX_JOIN_MS = 60 * 24 * 3600 * 1000;

// A compact, dependency-free displacement chart. Time on x, displacement (mm) on y.
// Subsidence (negative) reads downward, as a journalist expects.
export default function TimeSeriesChart({ series, onset, width = 320, height = 150 }: Props) {
  const geom = useMemo(() => {
    const pad = { l: 38, r: 8, t: 10, b: 22 };
    const solved = series.samples.flatMap((s) =>
      s.displacement_mm === null ? [] : [{ t: new Date(s.date).getTime(), y: s.displacement_mm }],
    );
    if (solved.length === 0) return null;
    const xs = series.samples.map((s) => new Date(s.date).getTime());
    const ys = solved.map((s) => s.y);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const yPad = (yMax - yMin) * 0.1 || 1;
    const lo = yMin - yPad;
    const hi = yMax + yPad;

    const px = (t: number) => pad.l + ((t - xMin) / (xMax - xMin || 1)) * (width - pad.l - pad.r);
    const py = (v: number) => pad.t + (1 - (v - lo) / (hi - lo || 1)) * (height - pad.t - pad.b);

    // A date with no solution, or a long stretch between dates, is a gap in the line.
    let path = "";
    const dots: { x: number; y: number }[] = [];
    let run: { x: number; y: number }[] = [];
    let previous: number | null = null;
    const closeRun = () => {
      if (run.length === 1) dots.push(run[0]);
      run = [];
    };
    for (const s of series.samples) {
      if (s.displacement_mm === null) {
        closeRun();
        previous = null;
        continue;
      }
      const t = new Date(s.date).getTime();
      const joined = previous !== null && t - previous <= MAX_JOIN_MS;
      if (!joined) closeRun();
      const at = { x: px(t), y: py(s.displacement_mm) };
      path += `${joined ? "L" : "M"}${at.x.toFixed(1)},${at.y.toFixed(1)} `;
      run.push(at);
      previous = t;
    }
    closeRun();

    const zeroY = py(0);
    const onsetX = onset ? px(new Date(onset).getTime()) : null;

    // y gridlines at lo, 0, hi-ish
    const ticks = [hi, (hi + lo) / 2, lo].map((v) => ({ v, y: py(v) }));
    const firstYear = new Date(xMin).getFullYear();
    const lastYear = new Date(xMax).getFullYear();
    const yearTicks: { label: string; x: number }[] = [];
    for (let yr = firstYear; yr <= lastYear; yr++) {
      yearTicks.push({ label: String(yr), x: px(new Date(`${yr}-01-01`).getTime()) });
    }

    return { path, dots, zeroY, onsetX, ticks, yearTicks, pad };
  }, [series, onset, width, height]);

  if (!geom) return <div className="text-xs text-ink-200">No time series.</div>;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={`Displacement time series, ${series.samples.length} dates`}>
      <rect x={0} y={0} width={width} height={height} fill="transparent" />
      {/* y gridlines */}
      {geom.ticks.map((t, i) => (
        <g key={i}>
          <line x1={geom.pad.l} x2={width - geom.pad.r} y1={t.y} y2={t.y} stroke="#283039" strokeWidth={0.5} />
          <text x={4} y={t.y + 3} fontSize={9} fill="#aab3bd">
            {t.v.toFixed(0)}
          </text>
        </g>
      ))}
      {/* zero reference */}
      <line
        x1={geom.pad.l}
        x2={width - geom.pad.r}
        y1={geom.zeroY}
        y2={geom.zeroY}
        stroke="#5b6571"
        strokeWidth={0.8}
        strokeDasharray="3 2"
      />
      {/* onset marker */}
      {geom.onsetX !== null && (
        <g>
          <line x1={geom.onsetX} x2={geom.onsetX} y1={geom.pad.t} y2={height - geom.pad.b} stroke="#e8c547" strokeWidth={1} />
          <text x={geom.onsetX + 3} y={geom.pad.t + 8} fontSize={8} fill="#e8c547">
            onset
          </text>
        </g>
      )}
      {/* x year ticks */}
      {geom.yearTicks.map((t, i) => (
        <text key={i} x={t.x} y={height - 6} fontSize={9} fill="#aab3bd" textAnchor="middle">
          {t.label}
        </text>
      ))}
      <text x={4} y={8} fontSize={8} fill="#aab3bd">
        mm
      </text>
      {/* the series */}
      <path d={geom.path} fill="none" stroke="#e9e6df" strokeWidth={1.4} />
      {geom.dots.map((d, i) => (
        <circle key={i} cx={d.x} cy={d.y} r={1.6} fill="#e9e6df" />
      ))}
    </svg>
  );
}
