"use client";
import { alignWords } from "@/lib/align";

/** Word-level diff: kept (plain), removed (strike), added (accent underline). */
export default function DiffView({ original, proposed }: { original: string; proposed: string }) {
  const parts = alignWords(original, proposed);
  return (
    <p className="text-xl leading-relaxed" aria-label={`Suggested change from ${original} to ${proposed}`}>
      {parts.map((p, k) =>
        p.k === "same" ? (
          <span key={k}>{p.t} </span>
        ) : p.k === "del" ? (
          <span key={k} className="line-through text-red-800 bg-red-50 rounded px-1">{p.t} </span>
        ) : (
          <span key={k} className="text-accentdark underline decoration-2 underline-offset-2 bg-emerald-50 rounded px-1">{p.t} </span>
        )
      )}
    </p>
  );
}
