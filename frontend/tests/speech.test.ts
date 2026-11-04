import { describe, expect, it } from "vitest";
import { speechLang, pickBrowserVoice, type BrowserVoiceLike } from "../lib/api";

describe("speechLang", () => {
  it("maps session languages to BCP-47 voice tags (Hindi and English only)", () => {
    expect(speechLang("en")).toBe("en-IN");
    expect(speechLang("hi")).toBe("hi-IN");
    expect(speechLang("hinglish")).toBe("hi-IN");
  });

  it("falls back to en-IN for unknown languages instead of undefined", () => {
    expect(speechLang("auto")).toBe("en-IN");
    expect(speechLang("")).toBe("en-IN");
  });
});

describe("pickBrowserVoice", () => {
  const v = (name: string, lang: string): BrowserVoiceLike => ({ name, lang });

  it("prefers a natural voice over a robotic one listed first", () => {
    const voices = [
      v("Microsoft David Desktop - English (United States)", "en-US"),
      v("Google US English", "en-US"),
    ];
    expect(pickBrowserVoice(voices, "en-IN")?.name).toBe("Google US English");
  });

  it("avoids eSpeak even when it is the only prefixed match besides a better one", () => {
    const voices = [v("eSpeak", "en"), v("Microsoft Neerja Online (Natural) - English (India)", "en-IN")];
    expect(pickBrowserVoice(voices, "en-IN")?.lang).toBe("en-IN");
  });

  it("prefers the exact locale (en-IN) over en-US on otherwise equal voices", () => {
    const voices = [v("Voice A", "en-US"), v("Voice B", "en-IN")];
    expect(pickBrowserVoice(voices, "en-IN")?.name).toBe("Voice B");
  });

  it("still picks the Hindi voice for Devanagari (silence-fix regression)", () => {
    const voices = [v("Microsoft David Desktop - English (United States)", "en-US"), v("Google हिन्दी", "hi-IN")];
    expect(pickBrowserVoice(voices, "hi-IN")?.name).toBe("Google हिन्दी");
  });

  it("returns null when no voice matches the language, [] when empty", () => {
    expect(pickBrowserVoice([v("Google हिन्दी", "hi-IN")], "en-IN")).toBeNull();
    expect(pickBrowserVoice([], "en-IN")).toBeNull();
  });

  it("keeps list order on ties so single-voice devices behave as before", () => {
    const voices = [v("Voice A", "en-US"), v("Voice B", "en-US")];
    expect(pickBrowserVoice(voices, "en-IN")?.name).toBe("Voice A");
  });
});
