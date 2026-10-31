"use client";
import { useState } from "react";
import Link from "next/link";
import { LANG_DATA, type LangKey } from "@/lib/design-system";

const STAGES = [
  { n: "01", icon: "record_voice_over", h: "Speak Naturally", p: "No forced cadence or robotic pronunciation. Use your natural breath pattern." },
  { n: "02", icon: "graphic_eq", h: "Speech Recognition", p: "Custom acoustic model decodes non-standard phonemes and vocal tremors." },
  { n: "03", icon: "psychology", h: "Contextual AI", p: "Analyzes conversational setting, time, and environment for high-probability intent." },
  { n: "04", icon: "menu_book", h: "Vocabulary Retrieval", p: "Integrates user-defined personal phrases, family names, and local dialect terms." },
  { n: "05", icon: "auto_fix_high", h: "AI Reconstruction", p: "Generates grammatically coherent candidates honoring speaker tone and intent." },
  { n: "06", icon: "security", h: "User Reviews & Confirms", p: "The engine pauses. The user validates via touch, switch, or eye-gaze. Absolute consent.", gatekeeper: true },
  { n: "07", icon: "volume_up", h: "Verified TTS", p: "High-fidelity voice synthesis articulates the confirmed message seamlessly." },
];

export default function Overview() {
  const [confirmed, setConfirmed] = useState(true);
  const [speaking, setSpeaking] = useState("");
  const [lang, setLang] = useState<LangKey>("hinglish");
  const [streaming, setStreaming] = useState(false);
  const d = LANG_DATA[lang];

  function heroSpeak() {
    if (!confirmed) return;
    setSpeaking("Speaking Verified Audio...");
    setTimeout(() => {
      setSpeaking("Played Successfully");
      try {
        const u = new SpeechSynthesisUtterance("मुझे पानी चाहिए. I would like some water, please.");
        u.rate = 0.95;
        speechSynthesis.speak(u);
      } catch {}
      setTimeout(() => setSpeaking(""), 2000);
    }, 1200);
  }

  function demoSpeak() {
    setStreaming(true);
    try {
      const u = new SpeechSynthesisUtterance(d.clean.replace(/[""]/g, ""));
      u.rate = 0.95;
      speechSynthesis.speak(u);
    } catch {}
    setTimeout(() => setStreaming(false), 1500);
  }

  return (
    <div className="flex flex-col w-full">
      {/* HERO */}
      <section className="relative w-full overflow-hidden bg-surface py-space-xl lg:py-28 px-margin">
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[720px] h-[360px] bg-primary/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-gutter items-center relative z-10">
          <div className="lg:col-span-7 flex flex-col gap-space-lg">
            <div className="inline-flex items-center gap-space-xs self-start px-space-md py-space-xs rounded-full bg-surface-container-high text-primary">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="font-label-sm text-label-sm font-semibold tracking-wider uppercase">Assistive Phonetic Intelligence</span>
            </div>
            <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight">Your voice deserves to be <span className="text-primary italic">understood.</span></h1>
            <p className="font-body-xl text-body-xl text-on-surface-variant max-w-2xl">Meet Second Voice — a multilingual AI communication companion that helps people with dysarthria express their thoughts more clearly, while keeping every word in their control.</p>
            <div className="flex items-center gap-space-sm text-secondary">
              <span className="material-symbols-outlined text-[20px]">verified_user</span>
              <span className="font-label-lg text-label-lg font-semibold tracking-wide">Your words. Your decisions. Always.</span>
            </div>
            <div className="flex flex-wrap items-center gap-space-md pt-space-xs">
              <Link href="#interactive-demo" className="min-h-[56px] px-space-xl inline-flex items-center justify-center gap-space-sm rounded-full bg-primary text-on-primary font-label-lg text-label-lg font-bold">Experience Second Voice <span className="material-symbols-outlined text-[20px]">arrow_forward</span></Link>
              <Link href="#how-it-works" className="min-h-[56px] px-space-xl inline-flex items-center justify-center gap-space-sm rounded-full bg-surface-container-high text-on-surface font-label-lg text-label-lg"><span className="material-symbols-outlined text-[20px]">play_circle</span>See how it works</Link>
            </div>
            <div className="grid grid-cols-3 gap-space-md pt-space-lg max-w-xl">
              <div className="flex flex-col"><span className="text-display-lg-mobile text-primary font-bold">100%</span><span className="font-label-sm text-label-sm text-on-surface-variant">User Consent Gate</span></div>
              <div className="flex flex-col"><span className="text-display-lg-mobile text-on-surface font-bold">&lt;350ms</span><span className="font-label-sm text-label-sm text-on-surface-variant">Phoneme Inference</span></div>
              <div className="flex flex-col"><span className="text-display-lg-mobile text-on-surface font-bold">4+</span><span className="font-label-sm text-label-sm text-on-surface-variant">Native Indian Dialects</span></div>
            </div>
          </div>
          <div className="lg:col-span-5">
            <div className="bg-surface-container rounded-xl p-space-lg shadow-2xl">
              <div className="flex items-center justify-between pb-space-md mb-space-md bg-surface-container-high/60 -mx-space-lg -mt-space-lg px-space-lg pt-space-md">
                <div className="flex items-center gap-space-sm"><span className="w-3 h-3 rounded-full bg-primary animate-ping" /><span className="font-label-md text-label-md font-semibold text-primary">Listening...</span></div>
                <div className="flex items-center gap-space-xs text-on-surface-variant font-label-sm text-label-sm"><span className="material-symbols-outlined text-[16px]">mic</span><span>Acoustic Rig v3</span></div>
              </div>
              <div className="py-space-md flex flex-col items-center gap-space-sm bg-surface-container-lowest/80 rounded-lg px-space-md mb-space-md">
                <div className="w-full flex items-center justify-between h-14 gap-1 px-space-xs" aria-hidden>
                  {[3, 8, 12, 6, 10, 14, 9, 5, 11, 7, 4].map((h, i) => (
                    <span key={i} className="w-1.5 bg-primary rounded-full animate-pulse" style={{ height: `${h * 4}px` }} />
                  ))}
                </div>
                <div className="flex items-center justify-between w-full text-on-surface-variant font-label-sm text-label-sm"><span>Phonetic Envelope Capture</span><span className="text-primary font-semibold">SNR: +18.4 dB</span></div>
              </div>
              <div className="flex flex-col gap-space-xs mb-space-md">
                <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">What we heard (Raw motor stream)</span>
                <div className="bg-surface-container-low p-space-md rounded-lg flex items-center gap-space-sm">
                  <span className="material-symbols-outlined text-secondary text-[20px]">hearing</span>
                  <p className="font-body-md text-body-md text-on-surface italic">&quot;Mujhe wa-ter chai-ye&quot;</p>
                </div>
              </div>
              <div className="flex flex-col gap-space-xs mb-space-lg">
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-primary">AI-Proposed Reconstruction</span>
                  <span className="bg-secondary-container text-on-secondary font-label-sm text-label-sm px-space-xs py-0.5 rounded">98.4% Match</span>
                </div>
                <div className="bg-surface-container-high p-space-md rounded-lg">
                  <p className="font-body-lg text-body-lg text-on-surface font-semibold">&quot;मुझे पानी चाहिए / I would like some water, please.&quot;</p>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">Preserved Intent: Polite Hydration Request</p>
                </div>
              </div>
              <div className="bg-surface-container-low p-space-md rounded-lg flex flex-col gap-space-sm mb-space-md">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-space-xs">
                    <input checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="w-5 h-5 accent-primary rounded cursor-pointer" id="heroConfirmCheck" type="checkbox" />
                    <label className="font-label-md text-label-md font-semibold text-primary cursor-pointer select-none" htmlFor="heroConfirmCheck">Confirmed by User</label>
                  </div>
                  <span className="material-symbols-outlined text-primary text-[20px]">check_circle</span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">The speech engine remains locked until you tap or dwell-confirm this transcription.</p>
              </div>
              <button onClick={heroSpeak} disabled={!confirmed} id="heroSpeakBtn" type="button" className={`w-full min-h-[56px] px-space-lg font-label-lg text-label-lg font-bold rounded-full flex items-center justify-center gap-space-sm ${confirmed ? "bg-primary text-on-primary" : "opacity-40 cursor-not-allowed bg-surface-container-high text-on-surface-variant"}`}>
                <span className="material-symbols-outlined text-[24px]">volume_up</span>
                <span>{speaking || "Speak Verified Message"}</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* PHILOSOPHY */}
      <section className="w-full bg-surface-container-lowest py-space-xl lg:py-28 px-margin">
        <div className="max-w-7xl mx-auto flex flex-col gap-space-xl">
          <div className="max-w-3xl flex flex-col gap-space-sm">
            <span className="font-label-sm text-label-sm uppercase font-semibold text-primary tracking-widest">Our Founding Philosophy</span>
            <h2 className="font-display-lg text-display-lg text-on-surface leading-tight">&quot;Sometimes, knowing what you want to say isn&apos;t the hard part. <span className="text-primary italic">Being understood is.</span>&quot;</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter items-start">
            <div className="lg:col-span-6 flex flex-col gap-space-md">
              <p className="font-body-xl text-body-xl text-on-surface-variant">Dysarthria alters muscle coordination in the tongue, larynx, and diaphragm. It changes the cadence and articulation of phonemes, but it never diminishes the complexity, wit, and depth of the mind speaking them.</p>
              <p className="font-body-lg text-body-lg text-on-surface-variant">For decades, standard AAC devices offered cold, canned phrases or rigid mechanical keyboards. Mainstream speech recognition simply fails, classifying dysarthric speech as noise.</p>
              <div className="bg-surface-container p-space-lg rounded-xl flex items-start gap-space-md mt-space-sm">
                <span className="material-symbols-outlined text-primary text-[28px]">lightbulb</span>
                <div className="flex flex-col gap-space-xs">
                  <span className="font-label-lg text-label-lg text-on-surface font-semibold">Human Agency Above Automated Guesswork</span>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">Second Voice listens for your individual acoustic anchors and phonemic habits. We train the AI to bridge into your unique motor-speech cadence — not force you to fit an algorithm.</p>
                </div>
              </div>
            </div>
            <div className="lg:col-span-6 flex flex-col gap-space-md bg-surface-container rounded-xl p-space-lg lg:p-space-xl shadow-xl">
              <div className="flex items-center gap-space-sm text-secondary"><span className="material-symbols-outlined text-[24px]">balance</span><span className="font-label-sm text-label-sm font-semibold tracking-wider uppercase">Inviolable Product Principle</span></div>
              <blockquote className="font-headline-lg text-headline-lg text-on-surface font-semibold leading-snug">&quot;AI may help someone express their thoughts, but it must <span className="text-primary underline underline-offset-8 decoration-primary/40">never take ownership</span> of those thoughts.&quot;</blockquote>
              {[["No Autonomous Speech:", "Second Voice will never synthesize, play, or broadcast words without an explicit user physical tap or eye-dwell confirmation."], ["Preserving Nuance & Humor:", "Reconstruction prioritizes your personal vernacular, idioms, and multilingual code-switching."], ["Dignified Independence:", "You choose the voice timbre, emotional prosody, and language blend for every setting."]].map(([h, p]) => (
                <div key={h} className="flex items-start gap-space-sm"><span className="material-symbols-outlined text-primary text-[20px] mt-1">check_circle</span><p className="font-body-md text-body-md text-on-surface-variant"><strong className="text-on-surface">{h}</strong> {p}</p></div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* 7-STAGE */}
      <section className="w-full bg-surface py-space-xl lg:py-28 px-margin" id="how-it-works">
        <div className="max-w-7xl mx-auto flex flex-col gap-space-xl">
          <div className="flex flex-col gap-space-xs text-center items-center max-w-2xl mx-auto">
            <span className="font-label-sm text-label-sm uppercase font-semibold text-primary tracking-widest">Architectural Integrity</span>
            <h2 className="font-headline-lg text-headline-lg text-on-surface">The 7-Stage Communication Pipeline</h2>
            <p className="font-body-md text-body-md text-on-surface-variant">From natural acoustic vocalization to room-filling, verified speech. Every stage is engineered for transparency and safety.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-space-sm items-stretch">
            {STAGES.map((s) => (
              <div key={s.n} className={s.gatekeeper ? "bg-surface-container-high lg:scale-105 rounded-xl p-space-md flex flex-col justify-between shadow-xl relative ring-2 ring-primary" : "bg-surface-container rounded-lg p-space-md flex flex-col justify-between hover:bg-surface-container-high transition-colors"}>
                {s.gatekeeper && <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-on-primary px-space-xs py-0.5 rounded-full font-label-sm text-label-sm font-bold uppercase tracking-wider whitespace-nowrap">Crucial Gatekeeper</div>}
                <div className="flex flex-col gap-space-xs pt-space-xs">
                  <span className="font-label-sm text-label-sm text-primary font-bold">{s.n}</span>
                  <span className={`material-symbols-outlined ${s.gatekeeper ? "text-primary text-[28px]" : "text-on-surface text-[24px]"}`}>{s.icon}</span>
                  <h3 className={`font-label-lg text-label-lg font-semibold ${s.gatekeeper ? "text-primary font-bold" : "text-on-surface"}`}>{s.h}</h3>
                  <p className={`font-body-sm text-body-sm ${s.gatekeeper ? "text-on-surface" : "text-on-surface-variant"}`}>{s.p}</p>
                </div>
                <div className={`mt-space-md pt-space-xs font-label-sm text-label-sm ${s.gatekeeper ? "text-primary font-semibold" : "text-on-surface-variant"}`}>{s.gatekeeper ? "User Sovereignty" : `Step ${parseInt(s.n)} of 7`}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* MULTILINGUAL DEMO */}
      <section className="w-full bg-surface-container-lowest py-space-xl lg:py-28 px-margin" id="interactive-demo">
        <div className="max-w-7xl mx-auto flex flex-col gap-space-xl">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
            <div className="flex flex-col gap-space-xs max-w-xl">
              <span className="font-label-sm text-label-sm uppercase font-semibold text-primary tracking-widest">Real-Time Linguistic Resonance</span>
              <h2 className="font-headline-lg text-headline-lg text-on-surface">Multilingual Live Switcher Demo</h2>
              <p className="font-body-md text-body-md text-on-surface-variant">Explore how Second Voice interprets dysarthric phonetic patterns across regional languages while keeping intent intact.</p>
            </div>
            <div className="flex items-center gap-space-xs bg-surface-container p-1 rounded-full overflow-x-auto" role="tablist" aria-label="Language">
              {(Object.keys(LANG_DATA) as LangKey[]).map((k) => (
                <button key={k} role="tab" aria-selected={lang === k} onClick={() => setLang(k)} className={`lang-tab px-space-md py-space-sm rounded-full font-label-md text-label-md font-semibold capitalize ${lang === k ? "bg-primary text-on-primary" : "text-on-surface-variant hover:text-on-surface"}`}>{k === "hinglish" ? "Hinglish" : k === "hindi" ? "हिंदी (Hindi)" : k === "marathi" ? "मराठी (Marathi)" : "English"}</button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter items-stretch">
            <div className="lg:col-span-6 bg-surface-container rounded-xl p-space-lg flex flex-col justify-between gap-space-lg">
              <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">Acoustic Input (Atypical Motor Pattern)</span>
              <span className="px-space-xs py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm self-start">{d.badge}</span>
              <div className="bg-surface-container-low p-space-md rounded-lg">
                <div className="flex items-center justify-between text-on-surface-variant font-label-sm text-label-sm"><span>Vocal Tremor &amp; Syllable Elongation</span><span className="text-primary font-semibold">{d.confidence}</span></div>
                <div className="h-10 flex items-center justify-center gap-1.5 overflow-hidden mt-2" aria-hidden>{[4, 8, 6, 10, 7, 3, 9, 5, 4].map((h, i) => <span key={i} className="w-1 bg-primary rounded-full animate-pulse" style={{ height: `${h * 3}px` }} />)}</div>
              </div>
              <p className="font-headline-sm text-headline-sm text-on-surface font-mono bg-surface-container-lowest p-space-md rounded-lg italic">{d.raw}</p>
              <p className="flex items-center gap-space-sm text-on-surface-variant font-body-sm text-body-sm"><span className="material-symbols-outlined text-[18px]">verified</span>Phonemic bridge recognizes aspirated consonants and irregular breath pauses.</p>
            </div>
            <div className="lg:col-span-6 bg-surface-container-high rounded-xl p-space-lg flex flex-col justify-between gap-space-lg">
              <span className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-primary">Automated Dignified Reconstruction</span>
              <div className="bg-surface-container p-space-md rounded-lg">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Proposed Expression:</span>
                <p className="font-headline-md text-headline-md text-on-surface font-bold">{d.clean}</p>
                <p className="font-body-md text-body-md text-secondary">{d.translation}</p>
              </div>
              <div className="flex flex-wrap gap-space-xs">{d.alternates.map((a) => <span key={a} className="px-space-md py-space-xs bg-surface-container rounded-full text-on-surface font-label-sm text-label-sm">{a}</span>)}</div>
              <div className="flex flex-col sm:flex-row items-center gap-space-sm">
                <button onClick={demoSpeak} type="button" className={`w-full sm:w-auto min-h-[56px] px-space-lg font-label-lg text-label-lg font-bold rounded-full flex items-center justify-center gap-space-sm ${streaming ? "animate-pulse bg-primary text-on-primary" : "bg-primary text-on-primary"}`}>
                  <span className="material-symbols-outlined text-[20px]">volume_up</span><span>{streaming ? "Audio Streaming..." : d.btnText}</span>
                </button>
                <span className="flex items-center gap-space-xs text-on-surface-variant font-label-sm text-label-sm"><span className="material-symbols-outlined text-[18px]">lock</span>Requires confirmation dwell</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CONSENT PILLAR */}
      <section className="w-full bg-surface py-space-xl lg:py-28 px-margin">
        <div className="max-w-7xl mx-auto flex flex-col gap-space-xl">
          <div className="text-center max-w-3xl mx-auto"><span className="font-label-sm text-label-sm uppercase font-semibold text-primary tracking-widest">Safety &amp; Sovereignty By Design</span>
            <h2 className="font-headline-lg text-headline-lg text-on-surface">The Three-Stage Consent Pillar</h2>
            <p className="font-body-md text-body-md text-on-surface-variant">Assistive technology should empower, never impersonate. No thought is articulated without deliberate authorization.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
            {[["model_training", "Phase 1", "AI Suggestion Only", "The neural system proposes multiple candidate phrases based on phoneme parsing and personal history. These remain completely silent proposals.", false], ["touch_app", "Phase 2 (The Gate)", "User Confirmation", "The user physically selects, eye-dwells, or triggers their switch controller to approve or edit the proposed statement.", true], ["campaign", "Phase 3", "Spoken Output", "The confirmed text is rendered into speech using natural prosody, calibrated for the immediate room acoustics.", false]].map(([icon, phase, h, p, gate]) => (
              <div key={h as string} className={gate ? "bg-surface-container-high rounded-xl p-space-lg shadow-xl ring-1 ring-primary/40" : "bg-surface-container rounded-xl p-space-lg shadow-md"}>
                <div className={`w-12 h-12 rounded-full flex items-center justify-center ${gate ? "bg-primary/20 text-primary" : "bg-surface-container-high text-primary"}`}><span className="material-symbols-outlined text-[24px]">{icon}</span></div>
                <span className={`font-label-sm text-label-sm font-semibold uppercase ${gate ? "text-primary" : "text-secondary"}`}>{phase}</span>
                <h3 className={`font-headline-sm text-headline-sm ${gate ? "text-primary" : "text-on-surface"}`}>{h}</h3>
                <p className={`font-body-md text-body-md ${gate ? "text-on-surface" : "text-on-surface-variant"}`}>{p}</p>
              </div>
            ))}
          </div>
          <div className="bg-surface-container-low rounded-xl p-space-lg flex flex-col md:flex-row gap-space-lg">
            <div className="flex flex-col gap-space-xs flex-1"><span className="font-label-md text-label-md font-semibold text-on-surface">Local Caching &amp; Zero Cloud Leaks</span><p className="font-body-sm text-body-sm text-on-surface-variant">Audio and phrasebooks are processed on-device or within strict transient memory. Raw biometric voice data is never sold or retained for third-party training.</p></div>
            <div className="flex flex-col gap-space-xs flex-1"><span className="font-label-md text-label-md font-semibold text-on-surface">Assistive Platform Disclaimer</span><p className="font-body-sm text-body-sm text-on-surface-variant">Second Voice is an augmentative communication (AAC) interface. It is not a diagnostic medical device or a clinical substitute for speech-language pathology.</p></div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="w-full bg-surface-container py-space-xl px-margin">
        <div className="max-w-5xl mx-auto rounded-2xl bg-surface-container-high p-space-lg md:p-space-xl flex flex-col md:flex-row items-center justify-between gap-space-lg shadow-2xl">
          <div className="flex flex-col gap-space-sm max-w-xl">
            <h2 className="font-headline-lg text-headline-lg text-on-surface">Restore natural conversational cadence today.</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">Available for wheelchair-mounted rigs, iPads, Android tablets, and adaptive eye-gaze workstations.</p>
          </div>
          <Link href="/register" className="min-h-[56px] px-space-xl bg-primary text-on-primary font-label-lg text-label-lg font-bold rounded-full flex items-center justify-center gap-space-sm">Get Started Free <span className="material-symbols-outlined text-[20px]">arrow_forward</span></Link>
        </div>
      </section>
    </div>
  );
}
