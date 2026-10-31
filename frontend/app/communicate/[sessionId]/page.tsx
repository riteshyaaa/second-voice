"use client";
import RequireAuth from "@/components/RequireAuth";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import DiffView from "@/components/DiffView";
import { api, speakBrowser, stopBrowserSpeech, API_URL } from "@/lib/api";
import { Recorder } from "@/lib/audio";
import { CLIP_DATA, type ClipKey } from "@/lib/design-system";

type Suggestion = {
  suggestion_id: number; original_text: string; proposed_text: string; explanation: string;
  changed_words: { from: string; to: string; reason: string }[]; alternatives: string[];
  needs_clarification: boolean; clarification_question: string; abstained: boolean;
  meaning_risk: string; provider: string; model_version: string;
};

const QUICK = [
  { icon: "local_drink", label: "I need water", phrase: "I need water, please." },
  { icon: "hourglass_empty", label: "Give me a moment", phrase: "Please give me a moment to respond." },
  { icon: "repeat", label: "Can you repeat that?", phrase: "Could you please repeat that?" },
  { icon: "favorite", label: "Thank you", phrase: "Thank you very much." },
];

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
  const [timbre, setTimbre] = useState("warm");
  const [rate, setRate] = useState(0.9);
  const [pitch, setPitch] = useState(102);
  const rec = useRef(new Recorder());

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 2800);
  }

  const runPipeline = useCallback(async (transcriptId: number, language: string) => {
    setStatus("Understanding…");
    const s = (await api.reconstruct(transcriptId)) as Suggestion;
    setSug(s);
    setEdit(s.proposed_text);
    setLang(language);
    setStatus(s.abstained ? "The system is unsure — please check carefully." : "Review the suggestion. Nothing has been spoken.");
  }, []);

  useEffect(() => {
    const pending = sessionStorage.getItem("sv_pending_audio");
    if (pending && fresh) {
      sessionStorage.removeItem("sv_pending_audio");
      const { audioId, lang: l } = JSON.parse(pending);
      (async () => {
        try {
          const t = (await api.transcribe(audioId, l === "en" ? "auto" : l)) as { transcript_id: number; text_original: string; language: string };
          setTranscript(t.text_original);
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
    setTranscript(c.verbatim);
    setEdit("");
    setSug(null);
    setStatus("Review Ready");
    showToast(`Loaded demo audio ${k}`);
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
        setStatus("Transcribing…");
        const up = (await api.uploadAudio(Number(sessionId), blob)) as { audio_id: number };
        try {
          const t = (await api.transcribe(up.audio_id, "auto")) as { transcript_id: number; text_original: string; language: string };
          (window as unknown as { _tid?: number })._tid = t.transcript_id;
          setTranscript(t.text_original);
          await runPipeline(t.transcript_id, t.language);
        } catch {
          setStatus("Live transcription is unavailable (no API key). Type your sentence below and press Understand.");
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

  function acceptMessage() {
    setAccepted(true);
    setStatus("Authorized for broadcast");
    showToast("Message approved. Gatekeeper unlocked.");
  }

  async function acceptBackend(kind: "accept" | "edit") {
    if (!sug) { acceptMessage(); return; }
    const finalText = kind === "accept" ? sug.proposed_text : edit;
    const c = (await api.confirm({
      suggestion_id: sug.suggestion_id, final_text: finalText, language: lang,
      source: kind === "accept" ? "accepted" : "edited", save_as_learning: true,
    })) as { approved_message_id: number };
    setApprovedId(c.approved_message_id);
    acceptMessage();
  }

  async function reject() {
    if (!sug) { setAccepted(false); showToast("Reverted to raw transcript."); return; }
    await api.feedback({ suggestion_id: sug.suggestion_id, final_text: transcript, kind: "reject" });
    setStatus("Rejected. Your original words are kept; nothing was spoken.");
    setSug(null);
    setAccepted(false);
  }

  async function speak() {
    if (!accepted && !approvedId) return;
    if (approvedId) {
      const r = (await api.synthesize(approvedId)) as { audio_url: string; fallback: boolean };
      setAudioUrl(`${API_URL}${r.audio_url}`);
      if (r.fallback) speakBrowser(edit || sug?.proposed_text || transcript);
      setStatus("Speaking confirmed text.");
    } else {
      speakBrowser(clipClear);
      showToast(`Vocalizing via TTS (${timbre} mode)...`);
    }
  }

  return (
    <RequireAuth>
    <div className="flex flex-col w-full">
      <aside aria-label="Demo Mode Controls" className="w-full bg-surface-container-high px-margin py-space-sm flex flex-wrap items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-sm min-w-0">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary"><span className="material-symbols-outlined text-[18px]">science</span></span>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-space-xs"><span className="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">Demo Mode</span><span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" /></div>
            <span className="font-body-sm text-body-sm text-on-surface truncate">Live Motor-Speech Acoustic Reconstruction Engine</span>
          </div>
        </div>
        <div className="flex items-center gap-space-xs overflow-x-auto py-1" role="tablist" aria-label="Sample clips">
          <span className="font-label-sm text-label-sm text-on-surface-variant hidden lg:inline mr-space-xs">Load Sample Clip:</span>
          {(Object.keys(CLIP_DATA) as ClipKey[]).map((k) => (
            <button key={k} onClick={() => loadClip(k)} className={`px-space-md py-space-xs rounded-full text-label-sm font-label-sm flex items-center gap-space-xs ${clip === k ? "bg-surface text-on-surface" : "bg-surface-container text-on-surface-variant hover:text-on-surface"}`}>
              <span className="material-symbols-outlined text-[16px] text-primary">graphic_eq</span><span>{CLIP_DATA[k].label}</span>
            </button>
          ))}
        </div>
      </aside>

      <div className="w-full px-margin py-space-lg grid grid-cols-1 lg:grid-cols-12 gap-gutter items-start max-w-7xl mx-auto">
        <nav aria-label="Assistive Workspace Navigation" className="lg:col-span-3 flex flex-col gap-space-md">
          <div className="bg-surface-container rounded-xl p-space-md flex flex-col gap-space-xs">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant px-space-sm mb-space-xs font-semibold">Workspace Matrix</span>
            {[["record_voice_over", "Workspace", true], ["grid_view", "AAC Quick Board", false], ["menu_book", "Personal Vocabulary · 148", false], ["history_edu", "Learning Log", false], ["spatial_audio", "Voice & TTS Timbre", false]].map(([icon, label, on]) => (
              <span key={label as string} className={`flex items-center gap-space-md px-space-md py-space-md rounded-lg font-label-lg text-label-lg ${on ? "bg-surface-container-high text-primary" : "text-on-surface-variant"}`}>
                <span className="material-symbols-outlined text-[22px]">{icon}</span><span className="truncate">{label}</span>
              </span>
            ))}
          </div>
          <section aria-labelledby="calib-heading" className="bg-surface-container-low rounded-xl p-space-md flex flex-col gap-space-sm">
            <div className="flex items-center justify-between">
              <h2 className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider font-semibold" id="calib-heading">Active Calibrator</h2>
              <span className="inline-flex items-center gap-1 font-label-sm text-label-sm text-secondary bg-surface-container px-2 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-secondary" />94% Latency Lock</span>
            </div>
            <p className="font-headline-sm text-headline-sm text-on-surface font-bold">Spastic-Ataxic Mod</p>
            <p className="font-body-sm text-body-sm text-on-surface-variant">Acoustic smoothing: 180ms window</p>
            <div className="w-full bg-surface-container rounded-lg p-space-sm"><div className="flex items-center justify-between font-label-sm text-label-sm mb-1"><span>Adaptive Dwell Reticle</span><span className="text-primary font-semibold">750ms</span></div><div className="w-full bg-surface-container-highest h-2 rounded-full overflow-hidden"><div className="bg-primary h-full rounded-full w-3/4" /></div></div>
          </section>
          <section aria-label="Current User Voice Model" className="bg-surface-container-low rounded-xl p-space-md flex items-center gap-space-md">
            <div className="w-10 h-10 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center font-bold">A</div>
            <div className="flex flex-col min-w-0"><span className="font-label-lg text-label-lg text-on-surface font-bold truncate">Aarav Mehta</span><span className="font-body-sm text-body-sm text-on-surface-variant truncate">Primary Voice: Warm Cadence (M-04)</span></div>
          </section>
        </nav>

        <div className="lg:col-span-9 flex flex-col gap-space-lg">
          <section aria-labelledby="stage-heading" className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-lg">
            <div className="flex flex-wrap items-center justify-between gap-space-md">
              <div className="flex items-center gap-space-md">
                <span className="inline-flex p-2 rounded-lg bg-surface-container-high text-primary"><span className="material-symbols-outlined text-[24px]">mic</span></span>
                <div><h1 className="font-headline-md text-headline-md font-bold text-on-surface" id="stage-heading">Live Acoustic Intake</h1><p className="font-body-sm text-body-sm text-on-surface-variant">Continuous sub-phoneme capture calibrated for vocal tension</p></div>
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
                <div className="flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant px-space-xs"><span>Dual Spectrum Visualizer</span><span className="font-bold text-on-surface bg-surface-container-high px-2 py-0.5 rounded font-mono">00:04.28</span></div>
                <svg className="w-full h-24 text-primary bg-surface-container rounded-lg p-2" fill="none" viewBox="0 0 600 80" preserveAspectRatio="none" aria-hidden>
                  <path className="opacity-90" d="M0,40 Q15,10 30,40 T60,40 T90,20 T120,60 T150,40 T180,5 T210,75 T240,40 T270,25 T300,55 T330,40 T360,15 T390,65 T420,40 T450,30 T480,50 T510,40 T540,10 T570,70 T600,40" stroke="currentColor" strokeLinecap="round" strokeWidth="2.5" />
                  <path className="opacity-40" d="M0,40 Q20,30 40,40 T80,40 T120,25 T160,55 T200,40 T240,15 T280,65 T320,40 T360,35 T400,45 T440,40 T480,25 T520,55 T560,40 T600,40" stroke="#a0d0c6" strokeLinecap="round" strokeWidth="1.5" />
                </svg>
                <div className="flex items-center justify-between gap-space-sm">
                  <span className="text-on-surface-variant font-label-sm text-label-sm">Acoustic Lock: <span className="text-primary font-bold">96.4% confidence</span></span>
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
              {sug && <div className="mt-1"><DiffView original={sug.original_text} proposed={sug.proposed_text} /></div>}
            </article>
            <article className="bg-surface-container-high rounded-xl p-space-lg flex flex-col gap-space-sm">
              <div className="flex items-center justify-between"><h2 className="font-label-lg text-label-lg font-bold text-primary">Suggested Clearer Message</h2><span className="font-label-sm text-label-sm bg-primary/10 text-primary px-2.5 py-1 rounded-md font-bold">96% Confident</span></div>
              <div className="flex items-center gap-space-xs bg-surface-container p-1 rounded-lg self-start" role="tablist" aria-label="Script">
                {(["en", "hi", "mr"] as const).map((l) => (
                  <button key={l} onClick={() => setClipLang(l)} className={`px-space-sm py-0.5 rounded text-label-sm font-label-sm ${clipLang === l ? "bg-primary text-on-primary font-bold" : "text-on-surface hover:bg-surface-container-high"}`}>{l === "en" ? "English" : l === "hi" ? "हिन्दी (Hindi)" : "मराठी (Marathi)"}</button>
                ))}
              </div>
              <div className="bg-surface-container-lowest p-space-md rounded-lg min-h-[140px] font-body-xl text-body-xl text-on-surface">{sug ? (edit || sug.proposed_text) : clipClear}</div>
              <p className="font-body-sm text-body-sm text-on-surface-variant"><strong className="text-on-surface">AI Rationale:</strong> {sug ? sug.explanation : CLIP_DATA[clip].rationale}</p>
              {sug && (
                <label className="block"> <span className="text-sm font-semibold">Edit before confirming</span>
                  <textarea aria-label="Edit suggestion" rows={2} className="mt-1 w-full text-base bg-surface-container-lowest border border-surface-container-high rounded-lg px-3 py-2 text-on-surface" value={edit} onChange={(e) => setEdit(e.target.value)} />
                </label>
              )}
            </article>
          </section>

          <section aria-label="Confirmation Decision Panel" className="bg-surface-container rounded-xl p-space-md flex flex-wrap items-center gap-space-md">
            <div className="flex flex-wrap items-center gap-space-sm flex-1">
              <button onClick={() => acceptBackend("accept")} className="min-h-[56px] px-space-lg rounded-xl bg-primary text-on-primary font-label-lg text-label-lg font-bold flex items-center gap-space-sm"><span className="material-symbols-outlined text-[24px]">check_circle</span>Accept &amp; Ready</button>
              <button onClick={() => { const v = prompt("Quick Edit Message Formulation:", edit || clipClear); if (v) { setEdit(v); setAccepted(true); } }} className="min-h-[56px] px-space-lg rounded-xl bg-surface-container-high text-on-surface font-label-lg text-label-lg flex items-center gap-space-sm"><span className="material-symbols-outlined text-[22px]">edit_note</span>Quick Edit</button>
              <button onClick={reject} className="min-h-[56px] px-space-md rounded-xl bg-surface-container-high text-on-surface-variant font-label-lg text-label-lg flex items-center gap-space-sm"><span className="material-symbols-outlined text-[22px]">replay</span>Keep Original</button>
              <button onClick={() => showToast("Saved phrase formulation to personal vocabulary (+1 token)")} className="min-h-[56px] px-space-md rounded-xl bg-surface-container-high text-on-surface-variant font-label-lg text-label-lg flex items-center gap-space-sm"><span className="material-symbols-outlined text-[22px]">bookmark_add</span>Save to Vocabulary</button>
            </div>
            <span className="flex items-center gap-space-xs text-on-surface-variant font-label-sm text-label-sm"><span className="material-symbols-outlined text-[18px]">verified</span>{accepted || approvedId ? <span className="text-primary font-bold">Authorized for broadcast</span> : "Awaiting user confirmation"}</span>
          </section>

          <section aria-labelledby="tts-heading" className="bg-surface-container-high rounded-xl p-space-lg flex flex-col gap-space-md">
            <div className="flex flex-wrap items-center justify-between gap-space-md">
              <div><h2 className="font-headline-sm text-headline-sm font-bold text-on-surface" id="tts-heading">Speech Output Gatekeeper</h2><p className="font-body-sm text-body-sm text-on-surface-variant">Safety lock active: synthesized audio will never broadcast without explicit user authorization</p></div>
              <div className="flex items-center gap-space-xs bg-surface-container px-space-sm py-1.5 rounded-lg">
                <span className="material-symbols-outlined text-secondary text-[20px]">record_voice_over</span>
                <label className="sr-only" htmlFor="timbreSelect">Voice Timbre Preset</label>
                <select id="timbreSelect" value={timbre} onChange={(e) => setTimbre(e.target.value)} className="bg-transparent text-on-surface font-label-sm text-label-sm cursor-pointer">
                  <option className="bg-surface-container" value="warm">Natural Warm (Trained Voice)</option>
                  <option className="bg-surface-container" value="clear">Clear Crisp Assistive</option>
                  <option className="bg-surface-container" value="sonorous">Deep Sonorous</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-md bg-surface-container p-space-md rounded-lg">
              <label className="flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant">Playback Rate (Speed) <span className="text-primary font-bold">{rate.toFixed(2)}x</span><input type="range" min={0.5} max={1.5} step={0.05} value={rate} onChange={(e) => setRate(Number(e.target.value))} className="w-full accent-primary" /></label>
              <label className="flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant">Fundamental Pitch <span className="text-primary font-bold">{pitch} Hz</span><input type="range" min={80} max={160} step={2} value={pitch} onChange={(e) => setPitch(Number(e.target.value))} className="w-full accent-primary" /></label>
              <label className="flex flex-col gap-1 font-label-sm text-label-sm text-on-surface-variant">Speaker Gain <span className="text-primary font-bold">85 dB</span><input type="range" min={40} max={100} step={5} defaultValue={85} className="w-full accent-primary" /></label>
            </div>
            <div className="flex flex-col sm:flex-row items-center gap-space-md">
              <button onClick={speak} disabled={!accepted && !approvedId} className={`w-full flex-1 min-h-[64px] px-space-xl rounded-xl font-label-lg text-label-lg font-bold flex items-center justify-center gap-space-md ${accepted || approvedId ? "bg-primary text-on-primary" : "bg-surface-container-highest text-on-surface-variant/40 cursor-not-allowed"}`}>
                <span className="material-symbols-outlined text-[28px]">volume_up</span>{accepted || approvedId ? "Speak Message Now" : "Speak Message (Locked)"}
              </button>
              {audioUrl && <audio className="w-full" controls src={audioUrl} aria-label="Confirmed speech playback" />}
              <button onClick={() => { stopBrowserSpeech(); setAudioUrl(""); }} className="min-h-[64px] px-space-md rounded-xl bg-surface-container text-on-surface font-label-md text-label-md">Stop</button>
            </div>
          </section>

          <section aria-labelledby="quickboard-heading" className="bg-surface-container rounded-xl p-space-lg flex flex-col gap-space-md">
            <div className="flex items-center gap-space-xs"><span className="material-symbols-outlined text-primary text-[22px]">touch_app</span><h2 className="font-headline-sm text-headline-sm font-bold text-on-surface" id="quickboard-heading">AAC Quick Board Shortcuts</h2></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-sm">
              {QUICK.map((q) => (
                <button key={q.label} onClick={() => { speakBrowser(q.phrase); showToast(`Vocalizing quick phrase: "${q.phrase}"`); }} type="button" className="min-h-[58px] p-space-md rounded-xl bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface font-label-lg text-label-lg flex items-center gap-space-sm text-left">
                  <span className="material-symbols-outlined text-[20px]">{q.icon}</span><span className="truncate">{q.label}</span>
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
