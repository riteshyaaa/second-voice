import { describe, expect, it, vi, beforeEach } from "vitest";
import { groupCards, resolveAudioUrl, tapToSpeak, type Card } from "../lib/cards";
import { api } from "../lib/api";

const card = (over: Partial<Card> = {}): Card => ({
  id: 1, label: "Water", label_native: null, language: "en",
  emoji: "", category: "needs", phrase: "I need water", favorite: false, ...over,
});

describe("groupCards", () => {
  it("puts favorites first, then categories, then unknown ones", () => {
    const groups = groupCards([
      card({ id: 1, category: "needs" }),
      card({ id: 2, category: "personal", favorite: true }),
      card({ id: 3, category: "custom-thing" }),
    ]);
    expect(groups.map((g) => g.key)).toEqual(["favorites", "needs", "other"]);
    expect(groups[0].cards.map((c) => c.id)).toEqual([2]);
  });

  it("drops empty categories and returns [] for no cards", () => {
    expect(groupCards([])).toEqual([]);
    const groups = groupCards([card({ id: 1, category: "emergency" })]);
    expect(groups.map((g) => g.key)).toEqual(["emergency"]);
  });
});

describe("resolveAudioUrl", () => {
  it("prefixes relative backend paths and keeps absolute URLs", () => {
    expect(resolveAudioUrl("/api/v1/speech/audio/3")).toContain("/api/v1/speech/audio/3");
    expect(resolveAudioUrl("https://cdn.example/a.mp3")).toBe("https://cdn.example/a.mp3");
  });
});

describe("cards api client", () => {
  const seen: string[] = [];
  beforeEach(() => {
    seen.length = 0;
    vi.stubGlobal("fetch", async (url: string) => {
      seen.push(url);
      const body = url.includes("/speak")
        ? { audio_url: "/api/v1/speech/audio/9", fallback: false }
        : [{ id: 1 }];
      return { ok: true, status: 200, text: async () => JSON.stringify(body) };
    });
  });

  it("builds category and favorites query strings", async () => {
    await api.cards("needs");
    await api.cards("", true);
    expect(seen[0]).toContain("/api/v1/cards?category=needs");
    expect(seen[1]).toContain("/api/v1/cards?favorites=true");
  });

  it("tapToSpeak plays server audio for confirmed taps", async () => {
    const played: string[] = [];
    const r = await tapToSpeak(card({ id: 7 }), (u) => played.push(u));
    expect(r).toEqual({ phrase: "I need water", fallback: false });
    expect(played).toHaveLength(1);
    expect(seen[0]).toContain("/api/v1/cards/7/speak");
  });

  it("tapToSpeak labels device fallback as fallback (confirmed text only)", async () => {
    vi.stubGlobal("fetch", async () => ({
      ok: true, status: 200, text: async () => JSON.stringify({ audio_url: "", fallback: true }),
    }));
    const r = await tapToSpeak(card({ id: 7 }), () => {});
    expect(r.fallback).toBe(true);
    expect(r.phrase).toBe("I need water");
  });
});
