import { describe, expect, it } from "vitest";
import { groupCandidates, sourceLabel, type Candidate } from "../lib/candidates";

const text = (over: Partial<Extract<Candidate, { kind: "text" }>> = {}): Candidate => ({
  source: "rules",
  kind: "text",
  text: "Hello.",
  explanation: "r",
  guards: [],
  usable: true,
  ...over,
});

describe("sourceLabel", () => {
  it("names every source in plain words, never an engine id", () => {
    for (const s of ["rules", "vocab", "alternative-asr", "contextual", "acoustic"] as const) {
      expect(sourceLabel(s)).toBeTruthy();
      expect(sourceLabel(s)).not.toContain("whisper");
    }
  });
});

describe("groupCandidates", () => {
  it("orders usable first by source priority, then flagged, then spans", () => {
    const span: Candidate = {
      source: "acoustic", kind: "uncertain-span", span: "Arav",
      reason: "replace", explanation: "e", guards: [], usable: true,
    };
    const out = groupCandidates([
      text({ source: "rules", text: "R." }),
      span,
      text({ source: "contextual", text: "C.", usable: false, guards: ["negation changed"] }),
      text({ source: "vocab", text: "V." }),
    ]);
    expect(out.usable.map((c) => c.source)).toEqual(["vocab", "rules"]);
    expect(out.flagged.map((c) => c.source)).toEqual(["contextual"]);
    expect(out.spans).toEqual([span]);
  });

  it("tolerates missing or malformed input without throwing", () => {
    expect(groupCandidates(undefined)).toEqual({ usable: [], flagged: [], spans: [] });
    expect(groupCandidates(null)).toEqual({ usable: [], flagged: [], spans: [] });
    expect(groupCandidates("nope" as never)).toEqual({ usable: [], flagged: [], spans: [] });
  });
});
