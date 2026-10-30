"use client";

import { useState } from "react";

const CITATION = `Northflow Technologies AS (2026). LITHOS: open ground motion intelligence. https://github.com/northflowlabs/lithos`;

const DATA_CITATION = `Lazecky, M.; Maghsoudi, Y. (2022): LiCSAR interferometry products. NERC EDS Centre for Environmental Data Analysis. https://catalogue.ceda.ac.uk/uuid/52cda2e0e6c04272ae15ac836c1e8493. LiCSAR contains modified Copernicus Sentinel data 2021 to 2024 analysed by the Centre for the Observation and Modelling of Earthquakes, Volcanoes and Tectonics (COMET). LiCSAR uses JASMIN, the UK's collaborative data analysis environment (http://jasmin.ac.uk). GNSS: Blewitt et al. (2018), Eos 99.`;

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
        onClick={() => copy(DATA_CITATION, "data")}
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
          href="http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
          target="_blank"
          rel="noreferrer"
        >
          Open Government Licence v3.0
        </a>
      </p>
    </div>
  );
}
