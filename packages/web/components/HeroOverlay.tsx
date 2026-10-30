"use client";

interface Props {
  name: string;
  note?: string;
  onDismiss: () => void;
}

// The headline + one-line promise overlaid on the live hero scene. Dismissible.
// No splash wall between the user and the wow: the map is already behind this.
export function HeroOverlay({ name, note, onDismiss }: Props) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-24 z-10 flex justify-center px-4 sm:bottom-auto sm:top-0">
      <div className="pointer-events-auto max-w-xl rounded-xl sm:mt-16 bg-ink-900/80 backdrop-blur px-6 py-5 border border-ink-700 text-center shadow-panel">
        <h1 className="text-2xl font-semibold tracking-tight text-paper">
          See the ground move.
        </h1>
        <p className="mt-1.5 text-sm text-ink-200">
          Ground motion measured by radar satellites, for anyone to read. Click a point for its
          history and a plain-language summary.
        </p>
        <p className="mt-2 text-[11px] text-ink-200">
          Showing: {name}
        </p>
        {note && <p className="mt-1 text-[11px] text-ink-200">{note}</p>}
        <button
          onClick={onDismiss}
          className="pointer-events-auto mt-3 rounded-full bg-signal px-4 py-1.5 text-xs font-medium text-ink-900 hover:brightness-110"
        >
          Explore the map
        </button>
      </div>
    </div>
  );
}
