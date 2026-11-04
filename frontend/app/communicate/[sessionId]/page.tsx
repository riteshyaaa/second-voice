"use client";
import RequireAuth from "@/components/RequireAuth";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import DiffView from "@/components/DiffView";
import CandidatesPanel from "@/components/CandidatesPanel";
import { api, speakBrowser, stopBrowserSpeech } from "@/lib/api";
import type { Candidate } from "@/lib/candidates";
import { resolveAudioUrl, tapToSpeak, type Card } from "@/lib/cards";
import { Recorder, toWav16kBlob } from "@/lib/audio";
import { CLIP_DATA, type ClipKey } from "@/lib/design-system";

type Suggestion = {
  suggestion_id: number; original_text: string; proposed_text: string; explanation: string;
  changed_words: { from: string; to: string; reason: string }[]; alternatives: string[];
  needs_clarification: boolean; clarification_question: string; abstained: boolean;
  meaning_risk: string; provider: string; model_version: string;
  candidates?: Candidate[];
};

type AsrInfo = {
  provider: string; model_version: string; fallback: boolean;
  uncertainty?: { kind: string; severity: string; message: string }[];
};

type ClarifyOption = { id: string; label: string; source: string };
type ClarifyQuestion = {
  id: string; target: string; question: string; options: ClarifyOption[];
  allows: string[]; severity?: string;
};

export default function Workspace() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const fresh = useSearchParams().get("fresh");
  const [transcript, setTranscript] = useState("");
  const [typed, setTyped] = useState("");
  const [lang, setLang] = useState("en");
  const [clip, setClip] = useState<ClipKey>("A");
  const [clipLang, setClipLang] = useState<"en" | "hi" | "mr">("en");
  const [sug, setSug] = useState<Suggestion | null>(null);
  const [edit, setEdit] = useState("");
  const [status, setStatus] = useState("Listening");
  const [approvedId, setApprovedId] = useState<number | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [recording, setRecording] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [toast, setToast] = useState("");
  const [rate, setRate] = useState(1.0);
  const [voices, setVoices] = useState<string[]>([]);
  const [voice, setVoice] = useState("");
  const [favs, setFavs] = useState<Card[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [vocabCount, setVocabCount] = useState<number | null>(null);
  const [asr, setAsr] = useState<AsrInfo | null>(null);
  const [questions, setQuestions] = useState<ClarifyQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [blockers, setBlockers] = useState<string[]>([]);
  const [replayUrl, setReplayUrl] = useState("");
  const [typedAnswer, setTypedAnswer] = useState<Record<string, string>>({});
  const editRef = useRef<HTMLTextAreaElement | null>(null);
  const audioEl = useRef<HTMLAudioElement | null>(null);
  const rec = useRef(new Recorder());

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 2800);
  }

  const runPipeline = useCallback(async (transcriptId: number, language: string) => {
    setStatus("Understanding…");
    setAccepted(false);
    setApprovedId(null);
    setQuestions([]);
    setAnswers({});
    setBlockers([]);
    setReplayUrl("");
    try {
      const s = (await api.reconstruct(transcriptId)) as Suggestion;
      setSug(s);
      setEdit(s.proposed_text);
      setLang(language);
      setStatus(s.abstained ? "The system is unsure — please check carefully." : "Review the suggestion. Nothing has been spoken.");
      if (s.needs_clarification) await loadQuestions(s.suggestion_id);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not reconstruct.");
    }
  }, []);

  async function loadQuestions(suggestionId: number) {
    try {
      const q = (await api.questions(suggestionId)) as {
        questions: ClarifyQuestion[]; answers: Record<string, unknown>;
        unresolved_blockers: string[]; audio_url: string;
      };
      setQuestions(q.questions || []);
      setAnswers(q.answers || {});
      setBlockers(q.unresolved_blockers || []);
      setReplayUrl(q.audio_url || "");
    } catch {
      setQuestions([]);
    }
  }

  async function answer(qid: string, kind: string, value?: string) {
    if (!sug) return;
    try {
      const r = (await api.answerQuestion(sug.suggestion_id, { question_id: qid, kind, value })) as {
        recorded: unknown; unresolved_blockers: string[];
      };
      setAnswers((prev) => ({ ...prev, [qid]: r.recorded }));
      setBlockers(r.unresolved_blockers || []);
      showToast("Answer recorded.");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Could not record answer.");
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const me = (await api.me()) as { display_name?: string; email?: string };
        setDisplayName(me.display_name || me.email || "");
      } catch {}
      try {
        const v = (await api.vocab()) as unknown[];
        setVocabCount(Array.isArray(v) ? v.length : null);
      } catch {}
      try {
        setFavs(((await api.cards("", true)) as Card[]).slice(0, 4));
      } catch {}
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const v = (await api.voices(lang)) as { voices: (string | { id?: string; name?: string })[] };
        const names = (v.voices || []).map((x) => (typeof x === "string" ? x : x.name || x.id || "")).filter(Boolean);
        setVoices(names);
        setVoice((prev) => (prev && names.includes(prev) ? prev : names[0] || ""));
      } catch {}
    })();
  }, [lang]);

  useEffect(() => {
    const pending = sessionStorage.getItem("sv_pending_audio");
    if (pending && fresh) {
      sessionStorage.removeItem("sv_pending_audio");
      const { audioId, lang: l } = JSON.parse(pending);
      (async () => {
        try {
          const t = (await api.transcribe(audioId, l === "en" ? "auto" : l)) as { transcript_id: number; text_original: string; language: string; provider: string; model_version: string; fallback: boolean; uncertainty: AsrInfo["uncertainty"] };
          setTranscript(t.text_original);
          setAsr({ provider: t.provider, model_version: t.model_version, fallback: t.fallback, uncertainty: t.uncertainty });
          await runPipeline(t.transcript_id, t.language);
        } catch (e) {
          setStatus(e instanceof Error ? e.message : "Transcription failed. Type your sentence below instead.");
          setLang(l);
        }
      })();
    }
  }, [fresh, runPipeline]);

  function loadClip(k: ClipKey) {
    setClip(k);
    setAccepted(false);
    setApprovedId(null);
    const c = CLIP_DATA[k];
    const w = window as unknown as { _tid?: number; _audioId?: number };
    w._tid = undefined;
    w._audioId = undefined;
    setTranscript("");
    setEdit("");
    setSug(null);
    setTyped(c.verbatim);
    setStatus("Demo sample ready — press Understand to run it through the pipeline.");
    showToast(`Loaded demo sample ${k}`);
  }

  const clipClear = clipLang === "hi" ? CLIP_DATA[clip].clearHi : clipLang === "mr" ? CLIP_DATA[clip].clearMr : CLIP_DATA[clip].clearEn;

  async function record() {
    try {
      if (!recording) {
        await rec.current.start();
        setRecording(true);
        setStatus("Recording Active");
      } else {
        const blob = await rec.current.stop();
        setRecording(false);
        let wav: Blob;
        try {
          setStatus("Preparing audio…");
          wav = await toWav16kBlob(blob);
        } catch {
          setStatus("This recording could not be read by your browser. Type your sentence below and press Understand.");
          return;
        }
        setStatus("Transcribing…");
        const up = (await api.uploadAudio(Number(sessionId), wav)) as { audio_id: number };
        try {
          const t = (await api.transcribe(up.audio_id, lang)) as { transcript_id: number; text_original: string; language: string };
          (window as unknown as { _tid?: number })._tid = t.transcript_id;
          setTranscript(t.text_original);
          await runPipeline(t.transcript_id, t.language);
        } catch (e) {
          setStatus(`Transcription failed: ${e instanceof Error ? e.message : "unknown error"}. Your recording is saved — type the sentence below and press Understand.`);
          (window as unknown as { _audioId?: number })._audioId = up.audio_id;
        }
      }
    } catch {
      setStatus("Microphone unavailable — type your sentence below.");
    }
  }

  async function understandTyped() {
    if (!typed.trim()) return;
    setStatus("Understanding…");
    const audioId = (window as unknown as { _audioId?: number })._audioId;
    let transcriptId: number;
    if (audioId) {
      const t = (await api.transcribeManual(audioId, typed, lang)) as { transcript_id: number };
      transcriptId = t.transcript_id;
    } else {
      const up = (await api.uploadAudio(Number(sessionId), new Blob(["x"], { type: "audio/wav" }))) as { audio_id: number };
      const t = (await api.transcribeManual(up.audio_id, typed, lang)) as { transcript_id: number };
      transcriptId = t.transcript_id;
    }
    (window as unknown as { _tid?: number })._tid = transcriptId;
    setTranscript(typed);
    await runPipeline(transcriptId, lang);
  }

  async function acceptBackend(kind: "accept" | "edit") {
    if (!sug) {
      showToast("Record or type a sentence first — there is nothing to confirm yet.");
      return;
    }
    if (blockers.length > 0) {
      showToast(`Answer the ${blockers.length} open clarification question${blockers.length > 1 ? "s" : ""} first — speech is blocked until then.`);
      return;
    }
    try {
      const finalText = kind === "accept" ? sug.proposed_text : edit;
      const c = (await api.confirm({
        suggestion_id: sug.suggestion_id, final_text: finalText, language: lang,
        source: kind === "accept" ? "accepted" : "edited", save_as_learning: true,
      })) as { approved_message_id: number };
      setApprovedId(c.approved_message_id);
      setAccepted(true);
      setStatus("Confirmed. Only this text can now be spoken.");
      showToast("Message confirmed.");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Could not confirm.");
    }
  }

  async function reject() {
    if (!sug) { setAccepted(false); showToast("Reverted to raw transcript."); return; }
    await api.feedback({ suggestion_id: sug.suggestion_id, final_text: transcript, kind: "reject" });
    setStatus("Rejected. Your original words are kept; nothing was spoken.");
    setSug(null);
    setAccepted(false);
  }

  async function speak() {
    if (!approvedId) {
      showToast("Confirm the message first — unconfirmed text is never spoken.");
      return;
    }
    try {
      const r = (await api.synthesize(approvedId, voice, rate)) as { audio_url: string; fallback: boolean };
      const url = resolveAudioUrl(r.audio_url);
      setAudioUrl(url);
      if (r.fallback) speakBrowser(edit || sug?.proposed_text || transcript);
      else requestAnimationFrame(() => audioEl.current?.play().catch(() => {}));
      setStatus("Speaking confirmed text.");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Could not synthesize.");
    }
  }

  function playSample() {
    speakBrowser(clipClear);
    setStatus("Playing a demo sample clip — this is not your message.");
  }

  async function savePhrase() {
    const text = (edit || sug?.proposed_text || "").trim();
    if (!text) {
      showToast("Nothing to save yet.");
      return;
    }
    try {
      await api.addVocabPhrase(text, lang);
      const v = (await api.vocab()) as unknown[];
      if (Array.isArray(v)) setVocabCount(v.length);
      showToast("Saved to your vocabulary.");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Could not save.");
    }
  }

  async function tapFav(card: Card) {
    try {
      stopBrowserSpeech();
      const r = await tapToSpeak(card, (url) => {
        setAudioUrl(url);
        requestAnimationFrame(() => audioEl.current?.play().catch(() => {}));
      });
      showToast(`Spoke (confirmed by tap): "${r.phrase}"`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Could not speak this card.");
    }
  }

  return (
    <RequireAuth>
    <div className="flex flex-col w-full">
      <aside aria-label="Demo sample clips" className="w-full bg-surface-container-high px-margin py-space-sm flex flex-wrap items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-sm min-w-0">
          <div className="flex flex-col min-w-0">
            <span className="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">Samples (demo text, not your words)</span>
            <span className="font-body-sm text-body-sm text-on-surface truncate">Loading a sample fills the type box so you can run the real pipeline on it.</span>
          </div>
        </div>
        <div className="flex items-center gap-space-xs overflow-x-auto py-1" role="group" aria-label="Sample clips">
          <span className="font-label-sm text-label-sm text-on-surface-variant hidden lg:inline mr-space-xs">Load sample:</span>
          {(Object.keys(CLIP_DATA) as ClipKey[]).map((k) => (
            <button key={k} onClick={() => loadClip(k)} className={`min-h-[44px] px-space-md py-space-xs rounded-full text-label-sm font-label-sm ${clip === k ? "bg-surface text-on-surface" : "bg-surface-container text-on-surface-variant hover:text-on-surface"}`}>
              <span>{CLIP_DATA[k].label}</span>
            </button>
          ))}
          <button onClick={playSample} className="min-h-[44px] px-space-md py-space-xs rounded-full text-label-sm font-label-sm bg-surface-container">Play sample aloud</button>
          <span className="font-label-sm text-label-sm text-on-surface-variant hidden lg:inline">Sample text:</span>
          {(["en", "hi", "mr"] as const).map((l) => (
            <button key={l} onClick={() => setClipLang(l)} aria-pressed={clipLang === l} className={`min-h-[44px] px-3 rounded-full text-label-sm font-label-sm ${clipLang === l ? "bg-primary text-on-primary" : "bg-surface-container"}`}>{l === "en" ? "EN" : l === "hi" ? "हिं" : "मर"}</button>
          ))}
        </div>
      </aside>

      <div className="w-full px-margin py-space-lg grid grid-cols-1 lg:grid-cols-12 gap-gutter items-start max-w-7xl mx-auto">
        <nav aria-label="Workspace navigation" className="lg:col-span-3 flex flex-col gap-space-md">
          <div className="bg-surface-container rounded-xl p-space-md flex flex-col gap-space-xs">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant px-space-sm mb-space-xs font-semibold">Go to</span>
            {[
              ["/dashboard", "Dashboard"],
              [`/communicate/${sessionId}`, "Workspace"],
              ["/board", "Communication board"],
              ["/vocabulary", "Vocabulary"],
              ["/learn", "Learning"],
              ["/history", "History"],
              ["/settings", "Settings"],
            ].map(([href, label]) => (
              <Link key={href as string} href={href as string} className="px-space-md py-space-md rounded-lg font-label-lg text-label-lg text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface min-h-[52px] flex items-center">
                <span className="truncate">{label}</span>
              </Link>
            ))}
          </div>
          <section aria-labelledby="how-heading" className="bg-surface-container-low rounded-xl p-space-md flex flex-col gap-space-sm">
            <h2 className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider font-semibold" id="how-heading">How this works</h2>
            <p className="font-body-sm text-body-sm text-on-surface-variant">Record or type, review the suggestion against your original words, confirm, then speak. Unconfirmed text is never spoken.</p>
          </section>
          <section aria-label="Your account" className="bg-surface-container-low rounded-xl p-space-md flex items-center gap-space-md">
            <div className="w-10 h-10 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center font-bold" aria-hidden>{(displayName || "?")[0]?.toUpperCase()}</div>
            <div className="flex flex-col min-w-0"><span className="font-label-lg text-label-lg text-on-surface font-bold truncate">{displayName || "…"}</span><span className="font-body-sm text-body-sm text-on-surface-variant truncate">{vocabCount === null ? "vocabulary…" : `${vocabCount} saved words`}</span></div>
          </section>
        </nav>

        <div className="lg:col-span-9 flex flex-col gap-space-lg">
          <section aria-labelledby="stage-heading" className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-lg">
            <div className="flex flex-wrap items-center justify-between gap-space-md">
              <div className="flex items-center gap-space-md">
                <span className="inline-flex p-2 rounded-lg bg-surface-container-high text-primary"><span className="material-symbols-outlined text-[24px]">mic</span></span>
                <div><h1 className="font-headline-md text-headline-md font-bold text-on-surface" id="stage-heading">Say it your way</h1><p className="font-body-sm text-body-sm text-on-surface-variant">Record, or type if recording is hard today</p></div>
              </div>
              <div className="flex items-center gap-space-xs bg-surface-container-lowest px-space-md py-space-sm rounded-full">
                <span className={`w-2.5 h-2.5 rounded-full animate-pulse ${recording ? "bg-error" : "bg-primary"}`} />
                <span className={`font-label-md text-label-md font-bold uppercase tracking-wider ${recording ? "text-error" : "text-primary"}`} role="status">{status}</span>
              </div>
            </div>
            <div className="flex flex-col lg:flex-row items-center gap-space-lg bg-surface-container-lowest p-space-lg rounded-xl">
              <div className="flex flex-col items-center gap-space-sm">
                <div className="relative">
                  <div className={`absolute -inset-3 rounded-full blur-md animate-pulse ${recording ? "bg-error/30" : "bg-primary/20"}`} />
                  <button aria-label="Toggle Motor-Speech Acoustic Recording" onClick={record} type="button" className="relative w-28 h-28 rounded-full bg-primary text-on-primary flex flex-col items-center justify-center active:scale-95">
                    <span className="material-symbols-outlined text-[44px]">mic</span><span className="font-label-sm text-label-sm font-bold mt-1">{recording ? "STOP" : "HOLD / TAP"}</span>
                  </button>
                </div>
                <span className="font-label-sm text-label-sm text-on-surface-variant">Dwell or Spacebar</span>
              </div>
              <div className="w-full flex-1 flex flex-col gap-space-xs">
                <div className="flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant px-space-xs"><span>{recording ? "Recording…" : "Sound level (display only)"}</span></div>
                <div className="flex items-center gap-2 px-space-xs" role="group" aria-label="Language you will speak">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">I speak:</span>
                  {(["en", "hi", "mr"] as const).map((l) => (
                    <button key={l} type="button" onClick={() => setLang(l)} aria-pressed={lang === l} className={`min-h-[48px] px-4 rounded-full font-semibold text-label-sm font-label-sm ${lang === l ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"}`}>{l === "en" ? "English" : l === "hi" ? "हिन्दी" : "मराठी"}</button>
                  ))}
                </div>
                <svg className="w-full h-24 text-primary bg-surface-container rounded-lg p-2" fill="none" viewBox="0 0 600 80" preserveAspectRatio="none" aria-hidden>
                  <path className="opacity-90" d="M0,40 Q15,10 30,40 T60,40 T90,20 T120,60 T150,40 T180,5 T210,75 T240,40 T270,25 T300,55 T330,40 T360,15 T390,65 T420,40 T450,30 T480,50 T510,40 T540,10 T570,70 T600,40" stroke="currentColor" strokeLinecap="round" strokeWidth="2.5" />
                  <path className="opacity-40" d="M0,40 Q20,30 40,40 T80,40 T120,25 T160,55 T200,40 T240,15 T280,65 T320,40 T360,35 T400,45 T440,40 T480,25 T520,55 T560,40 T600,40" stroke="#a0d0c6" strokeLinecap="round" strokeWidth="1.5" />
                </svg>
                <div className="flex items-center justify-between gap-space-sm">
                  <span className="text-on-surface-variant font-label-sm text-label-sm">Speech recognition is imperfect — your original words are always kept.</span>
                  <div className="flex gap-2">
                    <input aria-label="Type your sentence" className="text-sm bg-surface-container border border-surface-container-high rounded-lg px-3 py-2 text-on-surface" placeholder="Or type…" value={typed} onChange={(e) => setTyped(e.target.value)} />
                    <button onClick={understandTyped} className="h-10 px-space-md rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md">Understand</button>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section aria-label="Speech Reconstruction Comparison" className="grid grid-cols-1 md:grid-cols-2 gap-gutter items-stretch">
            <article className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-sm">
              <div className="flex items-center gap-space-xs"><span className="material-symbols-outlined text-on-surface-variant text-[20px]">hearing</span><h2 className="font-label-lg text-label-lg font-bold text-on-surface">What We Heard</h2></div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">Original un-altered capture. Never overwritten.</p>
              <div className="bg-surface-container-lowest p-space-md rounded-lg min-h-[140px] font-body-xl text-body-xl text-on-surface">{transcript || "No audio recorded yet. Tap microphone or load sample clip above."}</div>
              {asr && (
                <p className="font-body-sm text-body-sm text-on-surface-variant" aria-label="Recognition evidence">
                  Heard by {asr.provider}{asr.fallback ? " (typed fallback — no speech recognition ran)" : ""}. No word-level confidence is claimed.
                  {(asr.uncertainty || []).filter((u) => u.severity !== "info").slice(0, 2).map((u) => ` ${u.message}`).join("")}
                </p>
              )}
              {sug && <div className="mt-1"><DiffView original={sug.original_text} proposed={sug.proposed_text} /></div>}
            </article>
            <article className="bg-surface-container-high rounded-xl p-space-lg flex flex-col gap-space-sm">
              <div className="flex items-center justify-between"><h2 className="font-label-lg text-label-lg font-bold text-primary">Suggested clearer message</h2>{sug && <span className="font-label-sm text-label-sm bg-primary/10 text-primary px-2.5 py-1 rounded-md font-bold">{sug.abstained ? "Unsure — check me" : `${sug.provider} · ${sug.meaning_risk} risk`}</span>}</div>
              <div className="flex items-center gap-space-xs bg-surface-container px-3 py-1 rounded-lg self-start" aria-label="Detected language">
                <span className="font-label-sm text-label-sm text-on-surface-variant">Heard as: <strong className="text-on-surface">{lang === "hi" ? "हिन्दी" : lang === "mr" ? "मराठी" : lang === "hinglish" ? "Hinglish" : "English"}</strong></span>
              </div>
              <div className="bg-surface-container-lowest p-space-md rounded-lg min-h-[140px] font-body-xl text-body-xl text-on-surface">{sug ? (edit || sug.proposed_text) : "Record, type, or load a sample above to get a suggestion here."}</div>
              {sug && <p className="font-body-sm text-body-sm text-on-surface-variant"><strong className="text-on-surface">Why this change:</strong> {sug.explanation}</p>}
              {sug && (
                <label className="block"> <span className="text-sm font-semibold">Edit before confirming</span>
                  <textarea ref={editRef} aria-label="Edit suggestion" rows={2} className="mt-1 w-full text-base bg-surface-container-lowest border border-surface-container-high rounded-lg px-3 py-2 text-on-surface" value={edit} onChange={(e) => setEdit(e.target.value)} />
                </label>
              )}
            </article>
          </section>

          {sug && sug.candidates && (
            <CandidatesPanel
              candidates={sug.candidates}
              onUse={(t) => { setEdit(t); setTimeout(() => editRef.current?.focus(), 0); }}
            />
          )}

          {sug && sug.needs_clarification && (
            <section aria-labelledby="clarify-heading" className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-md">
              <div>
                <h2 className="font-headline-sm text-headline-sm font-bold text-on-surface" id="clarify-heading">A quick check before you confirm</h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant">The system is unsure about {blockers.length > 0 ? `${blockers.length} thing${blockers.length > 1 ? "s" : ""} that could change meaning` : "something"} — speech stays locked until blockers are answered or skipped. Your original audio is below for replay.</p>
              </div>
              {replayUrl && <audio className="w-full" controls src={resolveAudioUrl(replayUrl)} aria-label="Replay your original recording" />}
              {questions.map((q) => (
                <div key={q.id} className="bg-surface-container-lowest rounded-lg p-space-md flex flex-col gap-2">
                  <p className="font-label-lg text-label-lg font-semibold text-on-surface">{q.question}</p>
                  {answers[q.id] !== undefined && <p className="font-body-sm text-body-sm text-primary">Answered — thank you.</p>}
                  {answers[q.id] === undefined && (
                    <>
                      <div className="flex flex-wrap gap-2">
                        {q.options.map((o) => (
                          <button key={o.id} onClick={() => answer(q.id, "select", o.id)} className="min-h-[52px] px-4 rounded-xl bg-surface-container-high font-semibold" title={o.source}>{o.label}</button>
                        ))}
                      </div>
                      <div className="flex flex-col sm:flex-row gap-2">
                        <input aria-label={`Type your answer for: ${q.question}`} className="flex-1 rounded-lg px-3 py-2 min-h-[52px] bg-surface-container border border-surface-container-high" placeholder="Or type the right word…" value={typedAnswer[q.id] || ""} onChange={(e) => setTypedAnswer((p) => ({ ...p, [q.id]: e.target.value }))} />
                        <button onClick={() => answer(q.id, "type", typedAnswer[q.id])} className="min-h-[52px] px-4 rounded-xl bg-surface-container-high font-semibold">Send</button>
                        <button onClick={() => answer(q.id, "skip")} className="min-h-[52px] px-4 rounded-xl font-semibold opacity-70">Skip (keep uncertain)</button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {blockers.length === 0 && questions.length > 0 && (
                <button onClick={() => { const tid = (window as unknown as { _tid?: number })._tid; if (tid) runPipeline(tid, lang); }} className="min-h-[56px] px-space-lg rounded-xl bg-primary text-on-primary font-bold self-start">Re-check with my answers</button>
              )}
            </section>
          )}

          <section aria-label="Confirmation" className="bg-surface-container rounded-xl p-space-md flex flex-wrap items-center gap-space-md">
            <div className="flex flex-wrap items-center gap-space-sm flex-1">
              <button onClick={() => acceptBackend("accept")} disabled={!sug} className="min-h-[56px] px-space-lg rounded-xl bg-primary text-on-primary font-label-lg text-label-lg font-bold disabled:opacity-40 flex items-center gap-2"><span className="material-symbols-outlined" aria-hidden>check_circle</span>Accept suggestion</button>
              <button onClick={() => acceptBackend("edit")} disabled={!sug} className="min-h-[56px] px-space-lg rounded-xl bg-surface-container-high text-on-surface font-label-lg text-label-lg disabled:opacity-40 flex items-center gap-2"><span className="material-symbols-outlined" aria-hidden>edit_note</span>Confirm my edit</button>
              <button onClick={() => editRef.current?.focus()} className="min-h-[56px] px-space-lg rounded-xl bg-surface-container-high text-on-surface font-label-lg text-label-lg flex items-center gap-2"><span className="material-symbols-outlined" aria-hidden>edit</span>Edit first</button>
              <button onClick={reject} className="min-h-[56px] px-space-md rounded-xl bg-surface-container-high text-on-surface-variant font-label-lg text-label-lg flex items-center gap-2"><span className="material-symbols-outlined" aria-hidden>replay</span>Keep original</button>
              <button onClick={savePhrase} className="min-h-[56px] px-space-md rounded-xl bg-surface-container-high text-on-surface-variant font-label-lg text-label-lg flex items-center gap-2"><span className="material-symbols-outlined" aria-hidden>bookmark_add</span>Save to vocabulary</button>
            </div>
            <span className="text-on-surface-variant font-label-sm text-label-sm">{approvedId ? <span className="text-primary font-bold">Confirmed — only this text can be spoken</span> : "Awaiting your confirmation"}</span>
          </section>

          <section aria-labelledby="tts-heading" className="bg-surface-container-high rounded-xl p-space-lg flex flex-col gap-space-md">
            <div className="flex flex-wrap items-center justify-between gap-space-md">
              <div><h2 className="font-headline-sm text-headline-sm font-bold text-on-surface" id="tts-heading">Speak confirmed text</h2><p className="font-body-sm text-body-sm text-on-surface-variant">Only the text you confirmed above can be spoken. The button stays locked until then.</p></div>
              {voices.length > 0 && (
                <div className="flex items-center gap-space-xs bg-surface-container px-space-sm py-1.5 rounded-lg">
                  <label htmlFor="voiceSelect" className="font-label-sm text-label-sm text-on-surface-variant">Voice</label>
                  <select id="voiceSelect" value={voice} onChange={(e) => setVoice(e.target.value)} className="bg-transparent text-on-surface font-label-sm text-label-sm cursor-pointer min-h-[48px]">
                    {voices.map((v) => (
                      <option key={v} className="bg-surface-container" value={v}>{v}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="bg-surface-container p-space-md rounded-lg">
              <label className="flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant">Speaking speed <span className="text-primary font-bold">{rate.toFixed(2)}x</span><input type="range" min={0.5} max={1.5} step={0.05} value={rate} onChange={(e) => setRate(Number(e.target.value))} className="w-full accent-primary" aria-label="Speaking speed" /></label>
            </div>
            <div className="flex flex-col sm:flex-row items-center gap-space-md">
              <button onClick={speak} disabled={!approvedId} className={`w-full flex-1 min-h-[64px] px-space-xl rounded-xl font-label-lg text-label-lg font-bold flex items-center justify-center gap-3 ${approvedId ? "bg-primary text-on-primary" : "bg-surface-container-highest cursor-not-allowed"}`}>
                <span className="material-symbols-outlined text-[28px]" aria-hidden>volume_up</span>{approvedId ? "Speak confirmed text" : "Speak (locked until confirmed)"}
              </button>
              {audioUrl && <audio ref={audioEl} className="w-full" controls src={audioUrl} aria-label="Confirmed speech playback" />}
              <button onClick={() => { stopBrowserSpeech(); audioEl.current?.pause(); setAudioUrl(""); }} className="min-h-[64px] px-space-md rounded-xl bg-surface-container text-on-surface font-label-md text-label-md">Stop</button>
            </div>
          </section>

          <section aria-labelledby="quickboard-heading" className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center justify-between gap-space-xs">
              <h2 className="font-headline-sm text-headline-sm font-bold text-on-surface" id="quickboard-heading">Your favorite cards</h2>
              <Link href="/board" className="font-label-md text-label-md text-primary font-semibold min-h-[48px] flex items-center">Open full board</Link>
            </div>
            {favs.length === 0 && <p className="font-body-sm text-body-sm text-on-surface-variant">No favorites yet — star cards on the <Link href="/board" className="text-primary font-semibold">board</Link> and they appear here. Tapping one speaks it immediately (a tap is your confirmation).</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-sm">
              {favs.map((c) => (
                <button key={c.id} onClick={() => tapFav(c)} type="button" className="min-h-[58px] p-space-md rounded-xl bg-surface-container-high text-on-surface font-label-lg text-label-lg text-left" aria-label={`Speak: ${c.label}`}>
                  <span className="truncate">{c.emoji ? `${c.emoji} ` : ""}{c.label}</span>
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>
      {toast && <div className="fixed bottom-6 right-6 z-50 bg-primary text-on-primary px-space-lg py-space-md rounded-xl font-label-lg text-label-lg font-bold flex items-center gap-space-sm"><span className="material-symbols-outlined text-[22px]">check_circle</span>{toast}</div>}
    </div>
    </RequireAuth>
  );
}
