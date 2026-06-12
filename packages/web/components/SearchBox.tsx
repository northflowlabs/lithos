"use client";

import { useState } from "react";

interface Props {
  onPick: (lon: number, lat: number, label: string) => void;
}

interface NominatimResult {
  lon: string;
  lat: string;
  display_name: string;
}

// Geocoder using the free OpenStreetMap Nominatim service. For production scale,
// swap NEXT_PUBLIC for a self-hosted geocoder; the interface stays identical.
export function SearchBox({ onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const search = async (text: string) => {
    if (text.trim().length < 3) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(text)}`,
        { headers: { Accept: "application/json" } },
      );
      const data = (await res.json()) as NominatimResult[];
      setResults(data);
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="absolute top-4 left-4 z-10 w-[300px] max-w-[70vw]">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") search(q);
        }}
        onFocus={() => results.length && setOpen(true)}
        placeholder="Search a place…"
        aria-label="Search for a place"
        className="w-full rounded-md bg-ink-900/90 backdrop-blur border border-ink-700 px-3 py-2 text-sm text-paper placeholder:text-ink-400 focus:border-signal focus:outline-none"
      />
      {open && results.length > 0 && (
        <ul className="mt-1 rounded-md bg-ink-900/95 backdrop-blur border border-ink-700 overflow-hidden">
          {results.map((r, i) => (
            <li key={i}>
              <button
                onClick={() => {
                  onPick(parseFloat(r.lon), parseFloat(r.lat), r.display_name);
                  setOpen(false);
                  setQ(r.display_name.split(",")[0]);
                }}
                className="block w-full text-left px-3 py-2 text-xs text-ink-200 hover:bg-ink-700"
              >
                {r.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {loading && <div className="mt-1 px-3 text-[11px] text-ink-400">Searching…</div>}
    </div>
  );
}
