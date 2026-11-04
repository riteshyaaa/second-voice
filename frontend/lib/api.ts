export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sv_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("sv_token", t);
  else localStorage.removeItem("sv_token");
}

export function loggedIn(): boolean {
  return !!token();
}

async function req(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  if (opts.body && typeof opts.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    setToken(null);
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const msg = (data as { detail?: unknown })?.detail;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg ?? `HTTP ${res.status}`));
  }
  return data as never;
}

export const api = {
  register: (email: string, password: string, display_name = "") =>
    req("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password, display_name }) }),
  login: (email: string, password: string) =>
    req("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => req("/api/v1/auth/me"),
  createSession: (title: string, language = "en") =>
    req("/api/v1/audio/sessions", { method: "POST", body: JSON.stringify({ title, language }) }),
  uploadAudio: async (sessionId: number, blob: Blob) => {
    const t = token();
    const res = await fetch(`${API_URL}/api/v1/audio/sessions/${sessionId}/audio`, {
      method: "POST",
      headers: { ...(t ? { Authorization: `Bearer ${t}` } : {}), "Content-Type": blob.type || "audio/wav" },
      body: blob,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  transcribe: (audio_id: number, language_hint = "auto") =>
    req("/api/v1/transcription", { method: "POST", body: JSON.stringify({ audio_id, language_hint }) }),
  transcribeManual: (audio_id: number, manual_transcript: string, language = "en") =>
    req(`/api/v1/transcription/manual?audio_id=${audio_id}&manual_transcript=${encodeURIComponent(manual_transcript)}&language=${language}`, { method: "POST" }),
  reconstruct: (transcript_id: number, user_request = "") =>
    req("/api/v1/reconstruction", { method: "POST", body: JSON.stringify({ transcript_id, user_request }) }),
  alternatives: (transcript_id: number) =>
    req("/api/v1/reconstruction/alternatives", { method: "POST", body: JSON.stringify({ transcript_id }) }),
  clarify: (suggestion_id: number) => req(`/api/v1/reconstruction/clarify/${suggestion_id}`, { method: "POST" }),
  confirm: (payload: { suggestion_id?: number; transcript_id?: number; final_text: string; language: string; source?: string; save_as_learning?: boolean }) =>
    req("/api/v1/confirmation", { method: "POST", body: JSON.stringify(payload) }),
  feedback: (payload: { suggestion_id?: number; transcript_id?: number; final_text: string; kind?: string; save?: boolean }) =>
    req("/api/v1/feedback", { method: "POST", body: JSON.stringify(payload) }),
  stats: () => req("/api/v1/feedback/stats"),
  synthesize: (approved_message_id: number, voice = "", speed = 1.0) =>
    req("/api/v1/speech/synthesize", { method: "POST", body: JSON.stringify({ approved_message_id, voice, speed }) }),
  previewVoice: async (language: string, voice = "", speed = 1.0) => {
    const t = token();
    const res = await fetch(`${API_URL}/api/v1/speech/preview`, {
      method: "POST",
      headers: { ...(t ? { Authorization: `Bearer ${t}` } : {}), "Content-Type": "application/json" },
      body: JSON.stringify({ language, voice, speed }),
    });
    if (!res.ok) throw new Error(await res.text());
    return { blobUrl: URL.createObjectURL(await res.blob()), provider: res.headers.get("X-TTS-Provider") };
  },
  voices: (language: string) => req(`/api/v1/speech/voices?language=${language}`),
  sessions: () => req("/api/v1/sessions"),
  sessionDetail: (id: number) => req(`/api/v1/sessions/${id}`),
  vocab: () => req("/api/v1/vocabulary"),
  addVocab: (term: string, language = "en", category = "word") =>
    req("/api/v1/vocabulary", { method: "POST", body: JSON.stringify({ term, language, category }) }),
  delVocab: (id: number) => req(`/api/v1/vocabulary/${id}`, { method: "DELETE" }),
  memory: () => req("/api/v1/memory"),
  addMemory: (content: string, kind = "phrase", language = "en") =>
    req("/api/v1/memory", { method: "POST", body: JSON.stringify({ content, kind, language }) }),
  delMemory: (id: number) => req(`/api/v1/memory/${id}`, { method: "DELETE" }),
  prefs: () => req("/api/v1/preferences"),
  patchPrefs: (p: Record<string, unknown>) => req("/api/v1/preferences", { method: "PATCH", body: JSON.stringify(p) }),
  translate: (text: string, target: string) =>
    req("/api/v1/languages/translate", { method: "POST", body: JSON.stringify({ text, target }) }),
  pipelineDemo: (transcript: string) =>
    req("/api/v1/evaluation/pipeline-demo", { method: "POST", body: JSON.stringify({ transcript }) }),
  review: () => req("/api/v1/personalization/review"),
  cards: (category = "", favorites = false) =>
    req(`/api/v1/cards${category ? `?category=${encodeURIComponent(category)}` : ""}${favorites ? `${category ? "&" : "?"}favorites=true` : ""}`),
  addCard: (payload: { label: string; phrase: string; language?: string; emoji?: string; category?: string; label_native?: string }) =>
    req("/api/v1/cards", { method: "POST", body: JSON.stringify(payload) }),
  patchCard: (id: number, payload: Record<string, unknown>) =>
    req(`/api/v1/cards/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delCard: (id: number) => req(`/api/v1/cards/${id}`, { method: "DELETE" }),
  speakCard: (id: number) => req(`/api/v1/cards/${id}/speak`, { method: "POST" }),
  questions: (suggestion_id: number) => req(`/api/v1/reconstruction/questions/${suggestion_id}`),
  answerQuestion: (suggestion_id: number, payload: { question_id: string; kind: string; value?: string }) =>
    req(`/api/v1/reconstruction/questions/${suggestion_id}/answer`, { method: "POST", body: JSON.stringify(payload) }),
  addVocabPhrase: (phrase: string, language = "en") =>
    req("/api/v1/vocabulary", { method: "POST", body: JSON.stringify({ term: phrase, language, category: "phrase" }) }),
  exportData: () => req("/api/v1/account/data", { method: "POST" }),
  deleteData: () => req("/api/v1/account/data", { method: "DELETE" }),
};

export function speechLang(lang: string): string {
  return lang === "hi" ? "hi-IN" : lang === "hinglish" ? "hi-IN" : "en-IN";
}

export type SpeakResult = { ok: boolean; voiceMatched: boolean | null; lang: string };

export type BrowserVoiceLike = { name: string; lang: string };

function voiceScore(v: BrowserVoiceLike, tag: string): number {
  const name = (v.name || "").toLowerCase();
  let s = 0;
  // Exact locale first: keeps the Indian-English accent instead of US/UK.
  if ((v.lang || "").toLowerCase() === tag.toLowerCase()) s += 4;
  // Network / neural voices sound human; legacy SAPI + eSpeak sound robotic.
  if (name.includes("google")) s += 5;
  if (name.includes("natural")) s += 5;
  if (name.includes("neural") || name.includes("online") || name.includes("samantha")) s += 3;
  if (name.includes("espeak") || name.includes("robot")) s -= 10;
  if (name.includes("desktop")) s -= 5;
  return s;
}

/** Best voice for a BCP-47 tag. Ties keep list order, so single-voice
 *  devices behave exactly as before. Pure function — unit tested. */
export function pickBrowserVoice(voices: BrowserVoiceLike[], tag: string): BrowserVoiceLike | null {
  const prefix = tag.slice(0, 2).toLowerCase();
  const pool = voices.filter((v) => (v.lang || "").toLowerCase().startsWith(prefix));
  if (pool.length === 0) return null;
  let best = pool[0];
  let bestScore = -Infinity;
  for (const v of pool) {
    const s = voiceScore(v, tag);
    if (s > bestScore) { best = v; bestScore = s; }
  }
  return best;
}

export function speakBrowser(text: string, lang = "en", rate = 1.0): SpeakResult {
  const tag = speechLang(lang);
  if (typeof window === "undefined" || !("speechSynthesis" in window))
    return { ok: false, voiceMatched: null, lang: tag };
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = tag;
  u.rate = rate;
  // Explicit voice beats lang-tag guessing: Chrome silently drops Devanagari
  // text on many default English voices, which is why Hindi went quiet.
  const vs = window.speechSynthesis.getVoices();
  const match = pickBrowserVoice(vs, tag);
  if (match) u.voice = match as SpeechSynthesisVoice;
  window.speechSynthesis.speak(u);
  // Empty list means voices haven't loaded yet (Chrome loads async) — unknown,
  // not absent. Only report a miss when the list is populated.
  return { ok: true, voiceMatched: vs.length === 0 ? null : !!match, lang: tag };
}

export function stopBrowserSpeech() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}
