import { describe, expect, it } from "vitest";
import { stageForStatus, statusTone, isBusyStatus, formatElapsed, STAGES } from "../lib/stages";

describe("stageForStatus", () => {
  it("maps the workspace status strings to pipeline stages in order", () => {
    expect(stageForStatus("Listening")).toBe("review");
    expect(stageForStatus("Recording Active")).toBe("record");
    expect(stageForStatus("Preparing audio…")).toBe("transcribe");
    expect(stageForStatus("Transcribing…")).toBe("transcribe");
    expect(stageForStatus("Understanding…")).toBe("understand");
    expect(stageForStatus("Review the suggestion. Nothing has been spoken.")).toBe("review");
    expect(stageForStatus("Confirmed. Only this text can now be spoken.")).toBe("confirm");
    expect(stageForStatus("Speaking confirmed text.")).toBe("speak");
  });

  it("highlights the failed step so the user knows where to retry", () => {
    expect(stageForStatus("Transcription failed: timeout.")).toBe("transcribe");
    expect(stageForStatus("Microphone unavailable — type your sentence below.")).toBe("record");
  });

  it("exposes six ordered stages", () => {
    expect(STAGES.map((s) => s.id)).toEqual(["record", "transcribe", "understand", "review", "confirm", "speak"]);
  });
});

describe("statusTone", () => {
  it("distinguishes idle, recording, busy, ready, and error", () => {
    expect(statusTone("Listening")).toBe("idle");
    expect(statusTone("Recording Active")).toBe("recording");
    expect(statusTone("Transcribing…")).toBe("busy");
    expect(statusTone("Understanding…")).toBe("busy");
    expect(statusTone("Review the suggestion. Nothing has been spoken.")).toBe("ready");
    expect(statusTone("Confirmed. Only this text can now be spoken.")).toBe("ready");
    expect(statusTone("Transcription failed: timeout.")).toBe("error");
    expect(statusTone("Microphone unavailable — type your sentence below.")).toBe("error");
    expect(statusTone("Speak (locked until confirmed)")).toBe("error");
  });

  it("flags busy statuses for skeleton display", () => {
    expect(isBusyStatus("Transcribing…")).toBe(true);
    expect(isBusyStatus("Understanding…")).toBe(true);
    expect(isBusyStatus("Review the suggestion. Nothing has been spoken.")).toBe(false);
  });
});

describe("formatElapsed", () => {
  it("formats seconds as m:ss, clamping negatives", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(7)).toBe("0:07");
    expect(formatElapsed(65)).toBe("1:05");
    expect(formatElapsed(-3)).toBe("0:00");
  });
});
