"use client";
import { STAGES, type StageId } from "@/lib/stages";

/** Six-step pipeline progress. Presentational — the stage comes from status text. */
export default function StageStepper({ stage }: { stage: StageId }) {
  const activeIdx = STAGES.findIndex((s) => s.id === stage);
  return (
    <ol aria-label="Pipeline progress" className="flex flex-wrap items-center gap-x-2 gap-y-2">
      {STAGES.map((s, i) => {
        const done = i < activeIdx;
        const active = i === activeIdx;
        return (
          <li key={s.id} className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
            <span
              aria-hidden
              className={`w-6 h-6 rounded-full flex items-center justify-center text-[13px] font-bold transition-colors duration-200 ${
                done
                  ? "bg-primary text-on-primary"
                  : active
                    ? "border-2 border-primary text-primary"
                    : "border border-outline-variant text-on-surface-variant"
              }`}
            >
              {done ? "✓" : i + 1}
            </span>
            <span
              className={`font-label-sm text-label-sm ${active ? "text-on-surface font-bold" : done ? "text-on-surface" : "text-on-surface-variant"}`}
            >
              {s.label}
            </span>
            {i < STAGES.length - 1 && <span aria-hidden className="w-4 h-px bg-outline-variant mx-1" />}
          </li>
        );
      })}
    </ol>
  );
}
