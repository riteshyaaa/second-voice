/** Pipeline stage + status-tone derivation for the workspace UI.
 *  Pure functions — the status strings stay owned by the page, this only
 *  maps them to presentation. Unit-tested. */

export type StageId = "record" | "transcribe" | "understand" | "review" | "confirm" | "speak";

export const STAGES: { id: StageId; label: string }[] = [
  { id: "record", label: "Record" },
  { id: "transcribe", label: "Transcribe" },
  { id: "understand", label: "Understand" },
  { id: "review", label: "Review" },
  { id: "confirm", label: "Confirm" },
  { id: "speak", label: "Speak" },
];

const S = (s: string) => s.toLowerCase();

/** Which pipeline stage the current status text belongs to. */
export function stageForStatus(status: string): StageId {
  const s = S(status);
  if (s.includes("speak")) return "speak";
  if (s.includes("confirm")) return "confirm";
  if (s.includes("preparing") || s.includes("transcrib") || s.includes("transcription failed")) return "transcribe";
  if (s.includes("understand") || s.includes("re-check")) return "understand";
  if (s.includes("recording") || s.includes("microphone")) return "record";
  return "review";
}

export type StatusTone = "idle" | "recording" | "busy" | "ready" | "error";

/** Pill tone for the current status text. */
export function statusTone(status: string): StatusTone {
  const s = S(status);
  if (s.includes("recording active")) return "recording";
  if (
    s.includes("preparing") || s.includes("transcrib") ||
    s.includes("understanding") || s.includes("re-check")
  ) return "busy";
  if (
    s.includes("fail") || s.includes("could not") || s.includes("unavailable") ||
    s.includes("expired") || s.includes("no ") && s.includes("voice") ||
    s.includes("error") || s.includes("locked until")
  ) return "error";
  if (s === "listening" || s === "") return "idle";
  return "ready";
}

/** True while the pipeline is working (transcribe/understand), for skeletons. */
export function isBusyStatus(status: string): boolean {
  return statusTone(status) === "busy";
}

/** m:ss elapsed-time formatting for the recording timer. */
export function formatElapsed(totalSeconds: number): string {
  const t = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}
