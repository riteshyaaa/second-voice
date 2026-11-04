export type Candidate =
  | {
      source: "rules" | "vocab" | "alternative-asr" | "contextual";
      kind: "text";
      text: string;
      explanation: string;
      guards: string[];
      usable: boolean;
    }
  | {
      source: "acoustic";
      kind: "uncertain-span";
      span: string;
      reason: string;
      explanation: string;
      guards: string[];
      usable: boolean;
    };

const SOURCE_ORDER = ["contextual", "alternative-asr", "vocab", "rules"] as const;

const SOURCE_LABELS: Record<Candidate["source"], string> = {
  rules: "Rules cleanup",
  vocab: "Your approved spellings",
  "alternative-asr": "Second engine hearing",
  contextual: "Context-aware proposal",
  acoustic: "Uncertain audio regions",
};

export function sourceLabel(source: Candidate["source"]): string {
  return SOURCE_LABELS[source];
}

/** Usable text candidates first (source priority), then flagged ones, then spans. */
export function groupCandidates(cands: Candidate[] | undefined | null): {
  usable: Candidate[];
  flagged: Candidate[];
  spans: Extract<Candidate, { kind: "uncertain-span" }>[];
} {
  const list = Array.isArray(cands) ? cands : [];
  const texts = list.filter((c) => c.kind === "text");
  const order = (s: string) => SOURCE_ORDER.indexOf(s as (typeof SOURCE_ORDER)[number]);
  const byText = [...texts].sort((a, b) => {
    if (a.usable !== b.usable) return a.usable ? -1 : 1;
    return order(a.source) - order(b.source);
  });
  return {
    usable: byText.filter((c) => c.usable),
    flagged: byText.filter((c) => !c.usable),
    spans: list.filter((c) => c.kind === "uncertain-span") as Extract<
      Candidate,
      { kind: "uncertain-span" }
    >[],
  };
}
