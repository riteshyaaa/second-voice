import { describe, expect, it } from "vitest";
import { alignWords } from "../lib/align";

describe("alignWords", () => {
  it("marks equal words as same", () => {
    expect(alignWords("I need help", "I need help").every((p) => p.k === "same")).toBe(true);
  });

  it("marks insertions as add and keeps meaning words", () => {
    const parts = alignWords("I want meet doctor", "I want to meet the doctor");
    expect(parts.filter((p) => p.k === "add").map((p) => p.t)).toEqual(["to", "the"]);
  });

  it("never hides removed words (negation stays visible)", () => {
    const parts = alignWords("I don't want to go", "I want to go");
    const del = parts.filter((p) => p.k === "del").map((p) => p.t);
    expect(del).toContain("don't");
  });
});
