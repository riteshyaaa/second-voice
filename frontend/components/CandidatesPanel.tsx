"use client";
import { groupCandidates, sourceLabel, type Candidate } from "@/lib/candidates";

type Props = {
  candidates?: Candidate[] | null;
  onUse: (text: string) => void;
};

/** Where each suggestion reading came from — usable ones can fill the edit box (still confirmed), flagged ones stay visible with reasons. */
export default function CandidatesPanel({ candidates, onUse }: Props) {
  const { usable, flagged, spans } = groupCandidates(candidates);
  if (usable.length === 0 && flagged.length === 0 && spans.length === 0) return null;
  return (
    <section aria-label="Where the suggestion came from" className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-sm">
      <h2 className="font-label-lg text-label-lg font-bold text-on-surface">Where this came from</h2>
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Each reading is labelled. Flagged ones stay visible with the reason — nothing is hidden.
      </p>
      {usable.length > 0 && (
        <ul className="flex flex-col gap-2">
          {usable.map((c, i) => (
            <li key={`u-${i}`} className="bg-surface-container-lowest rounded-lg p-space-md flex flex-col gap-1">
              <span className="font-label-sm text-label-sm font-bold text-primary">{sourceLabel(c.source)}</span>
              {c.kind === "text" && <p className="text-on-surface text-lg">{c.text}</p>}
              <p className="font-body-sm text-body-sm text-on-surface-variant">{c.explanation}</p>
              {c.kind === "text" && (
                <button
                  type="button"
                  onClick={() => onUse(c.text)}
                  className="min-h-[48px] px-4 rounded-lg bg-surface-container-high text-on-surface font-semibold self-start"
                >
                  Use this text (still needs confirming)
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {flagged.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label="Flagged readings">
          {flagged.map((c, i) => (
            <li key={`f-${i}`} className="bg-surface-container-lowest rounded-lg p-space-md opacity-80">
              <span className="font-label-sm text-label-sm font-bold text-on-surface-variant">
                {sourceLabel(c.source)} — not usable: {(c.guards || []).join("; ") || "withheld"}
              </span>
              {c.kind === "text" && <p className="text-on-surface text-lg">{c.text}</p>}
            </li>
          ))}
        </ul>
      )}
      {spans.length > 0 && (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Uncertain audio regions: {spans.map((s) => `“${s.span}”`).join(", ")}. The engines heard these differently.
        </p>
      )}
    </section>
  );
}
