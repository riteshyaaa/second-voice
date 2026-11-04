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

export function speakBrowser(text: string, lang = "en-US", rate = 1.0) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = rate;
  window.speechSynthesis.speak(u);
  return true;
}

export function stopBrowserSpeech() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}
