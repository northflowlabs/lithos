"use client";

import { useState } from "react";
import { cedaCitation, GNSS_CREDIT, LICSAR_ACK, OGL_URL } from "@/lib/credits";

const CITATION = `Northflow Technologies AS (2026). LITHOS: open ground motion intelligence. https://github.com/northflowlabs/lithos`;

// The "cite this" affordance. Success for LITHOS is citations, not stars, so make
// attribution one click away everywhere it matters.
export function CiteBox({ permalink }: { permalink?: string }) {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setCopied(null);
    }
  };

  return (
    <div className="text-[11px] text-ink-200 space-y-1.5">
      <button
        onClick={() => copy(CITATION, "cite")}
        className="w-full text-left rounded border border-ink-600 bg-ink-800 px-2 py-1.5 hover:border-ink-400 transition-colors"
      >
        <span className="text-ink-200">Cite LITHOS</span>
        <span className="float-right text-signal">{copied === "cite" ? "copied" : "copy"}</span>
      </button>
      <button
        onClick={() => copy(`${cedaCitation()} ${LICSAR_ACK} ${GNSS_CREDIT}`, "data")}
        className="w-full text-left rounded border border-ink-600 bg-ink-800 px-2 py-1.5 hover:border-ink-400 transition-colors"
      >
        <span className="text-ink-200">Cite the data</span>
        <span className="float-right text-signal">{copied === "data" ? "copied" : "copy"}</span>
      </button>
      {permalink && (
        <button
          onClick={() => copy(permalink, "link")}
          className="w-full text-left rounded border border-ink-600 bg-ink-800 px-2 py-1.5 hover:border-ink-400 transition-colors"
        >
          <span className="text-ink-200">Copy permalink</span>
          <span className="float-right text-signal">{copied === "link" ? "copied" : "copy"}</span>
        </button>
      )}
      <p className="text-[10px]">
        LiCSAR data:{" "}
        <a
          className="underline"
          href={OGL_URL}
          target="_blank"
          rel="noreferrer"
        >
          Open Government Licence v3.0
        </a>
      </p>
    </div>
  );
}
