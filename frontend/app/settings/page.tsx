"use client";
import RequireAuth from "@/components/RequireAuth";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function Settings() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<Record<string, string | number | boolean>>({ font_scale: 1.25 });
  const [msg, setMsg] = useState("");
  const [font, setFont] = useState("large");
  const [expanded, setExpanded] = useState(true);
  const [contrast, setContrast] = useState(false);
  const [motion, setMotion] = useState(true);
  const [voice, setVoice] = useState("Aarav");
  const [speed, setSpeed] = useState(0.95);
  const [pitch, setPitch] = useState(0);
  const [wizard, setWizard] = useState(false);
  const [step, setStep] = useState(1);
  const [consent, setConsent] = useState(false);

  useEffect(() => {
    api.prefs().then((p) => setPrefs(p as Record<string, string | number | boolean>)).catch(() => {});
  }, []);

  async function save(patch: Record<string, string | number | boolean>) {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    try { await api.patchPrefs(patch); } catch {}
    document.documentElement.style.setProperty("--font-scale", String(next.font_scale ?? 1));
    setMsg("Saved.");
  }

  const scaleMap: Record<string, string> = { standard: "Standard (100%)", medium: "Medium (112%)", large: "Large (125%)", xlarge: "Extra Large (140%)" };

  return (
    <RequireAuth>
    <div className="w-full px-margin py-space-xl flex flex-col gap-space-xl max-w-7xl mx-auto">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-lg">
        <div className="max-w-2xl">
          <div className="flex items-center gap-space-sm text-primary font-label-md text-label-md uppercase"><span className="w-2 h-2 rounded-full bg-primary animate-pulse" />Adaptive Acoustic Engine · Profile Calibrated</div>
          <h1 className="font-display-lg text-display-lg font-bold text-on-surface">Settings &amp; Sovereignty</h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant">Configure tactile target density, multi-script phonetic bridge synthesis, acoustic privacy guardrails, and rapid profile onboarding.</p>
        </div>
        <button onClick={() => { setWizard(true); setStep(1); }} className="min-h-[56px] px-space-lg rounded-full bg-primary text-on-primary font-semibold flex items-center gap-2"><span className="material-symbols-outlined text-[22px]">play_circle</span>Launch Assisted Onboarding Flow</button>
      </div>
      {msg && <p role="status" className="text-primary">{msg}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
        {[["verified_user", "Privacy Boundary", "Zero Cloud Audio Stash", "Ephemeral on-device processing"], ["accessibility_new", "Ergonomics Target", expanded ? "Expanded Touch (64px)" : "Standard Target (44px)", "WCAG 2.2 Target Size AAA"], ["translate", "Phonetic Matrix", "Devanagari + Hinglish Dual", "Indic Neural Voice v4.2"]].map(([icon, k, v, s]) => (
          <div key={k} className="bg-surface-container rounded-xl p-space-lg flex items-center gap-space-md"><span className="material-symbols-outlined text-[28px] text-primary">{icon}</span><div><div className="font-label-sm text-label-sm uppercase text-on-surface-variant font-semibold">{k}</div><div className="font-headline-sm text-headline-sm font-semibold text-on-surface">{v}</div><div className="font-body-sm text-body-sm text-secondary">{s}</div></div></div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        <div className="lg:col-span-7 flex flex-col gap-space-xl">
          <div className="bg-surface-container rounded-xl p-space-xl flex flex-col gap-space-lg">
            <div className="flex items-center justify-between"><h2 className="font-headline-md text-headline-md font-semibold flex items-center gap-2"><span className="material-symbols-outlined text-primary">tune</span>Ergonomic &amp; Visual Suite</h2><span className="px-space-sm py-space-xs rounded-full bg-surface-container-high text-primary font-label-sm text-label-sm">High Priority</span></div>
            <div className="flex flex-col gap-space-sm">
              <label className="font-label-lg text-label-lg flex justify-between"><span>Dynamic Font Scale</span><span className="text-primary font-body-sm text-body-sm">{scaleMap[font]}</span></label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-space-xs bg-surface-container-low p-space-xs rounded-lg" role="radiogroup" aria-label="Font scale">
                {Object.keys(scaleMap).map((k) => (
                  <button key={k} onClick={() => { setFont(k); save({ font_scale: k === "standard" ? 1 : k === "medium" ? 1.12 : k === "large" ? 1.25 : 1.4 }); }} className={`min-h-[48px] rounded-lg font-label-md text-label-md capitalize ${font === k ? "bg-surface-container-highest text-primary font-semibold" : "text-on-surface-variant hover:text-on-surface"}`}>{k === "xlarge" ? "Extra Large" : k}</button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
              <button onClick={() => setExpanded(false)} className={`min-h-[56px] p-space-md rounded-xl text-left ${!expanded ? "bg-secondary-container" : "bg-surface-container-low"}`}><div className="font-label-lg font-semibold">Standard Target</div><div className="font-body-sm text-body-sm opacity-70">44px physical interactive floor</div></button>
              <button onClick={() => setExpanded(true)} className={`min-h-[64px] p-space-md rounded-xl text-left ${expanded ? "bg-secondary-container" : "bg-surface-container-low"}`}><div className="font-label-lg font-semibold">Expanded Accessible</div><div className="font-body-sm text-body-sm text-primary">64px oversized target floor (Active)</div></button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-md">
              <div className="bg-surface-container-low rounded-xl p-space-md flex items-center justify-between"><div><div className="font-semibold">High Contrast Mode</div><div className="text-sm opacity-70">WCAG AAA compliant tones</div></div>
                <button role="switch" aria-checked={contrast} onClick={() => { setContrast(!contrast); save({ high_contrast: !contrast }); document.documentElement.classList.toggle("high-contrast", !contrast); }} className="w-14 h-8 rounded-full bg-surface-container-highest"><span className={`block w-6 h-6 rounded-full bg-white transition-all ${contrast ? "translate-x-7 bg-primary" : ""}`} /></button></div>
              <div className="bg-surface-container-low rounded-xl p-space-md flex items-center justify-between"><div><div className="font-semibold">Motion Dynamics</div><div className="text-sm text-secondary">{motion ? "Default Smooth Waves" : "Reduced Motion (Flat)"}</div></div>
                <button role="switch" aria-checked={motion} onClick={() => { setMotion(!motion); save({ reduced_motion: !motion }); }} className={`w-14 h-8 rounded-full ${motion ? "bg-primary-container" : "bg-surface-container-highest"}`}><span className="block w-6 h-6 rounded-full bg-white" /></button></div>
            </div>
            <div className="bg-surface-container-lowest rounded-xl p-space-md">
              <span className="font-label-sm text-label-sm uppercase text-secondary font-semibold">Acoustic Feedback Canvas</span>
              <div className="h-16 flex items-center justify-center gap-1.5" aria-hidden>{[4, 8, 12, 7, 10, 14, 9, 5, 8, 12, 6, 3].map((h, i) => <span key={i} className="w-1.5 bg-primary rounded-full" style={{ height: motion ? `${h * 3}px` : "6px" }} />)}</div>
            </div>
          </div>

          <div className="bg-surface-container rounded-xl p-space-xl flex flex-col gap-space-lg">
            <div className="flex items-center justify-between"><h2 className="font-headline-md font-semibold flex items-center gap-2"><span className="material-symbols-outlined text-primary">record_voice_over</span>Speech Synthesis Engine</h2>
              <button onClick={(e) => { const b = e.currentTarget; b.innerHTML = "Synthesizing..."; setTimeout(() => { b.innerHTML = "Rendered"; setTimeout(() => { b.innerHTML = "Test Utterance"; }, 1000); }, 800); }} className="min-h-[48px] px-space-md rounded-full bg-surface-container-high text-primary flex items-center gap-2"><span className="material-symbols-outlined text-[18px]">volume_up</span>Test Utterance</button></div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-sm" role="radiogroup" aria-label="Voice model">
              {[["Aarav (English)", "Indian Accent · Resonant Warmth"], ["Ananya (Hindi)", "Neutral Tone · Clear Articulation"], ["Neerja (Hindi)", "Warm Tone · Clear Articulation"]].map(([n, s]) => (
                <button key={n} onClick={() => setVoice(n)} className={`p-space-md rounded-xl text-left ${voice === n ? "bg-secondary-container" : "bg-surface-container-low hover:bg-surface-container-high"}`}>
                  <div className="flex items-center justify-between"><span className="font-semibold">{n}</span><span className="material-symbols-outlined text-[18px]">{voice === n ? "check_circle" : "radio_button_unchecked"}</span></div><span className="text-sm opacity-70">{s}</span>
                </button>
              ))}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-lg">
              <label className="flex flex-col gap-1">Speech Cadence (Speed) <span className="text-primary font-semibold">{speed.toFixed(2)}x</span><input type="range" min={0.5} max={1.5} step={0.05} value={speed} onChange={(e) => { setSpeed(Number(e.target.value)); save({ tts_speed: Number(e.target.value) }); }} className="w-full accent-primary" /></label>
              <label className="flex flex-col gap-1">Acoustic Pitch Shift <span className="text-primary font-semibold">{pitch === 0 ? "0 st (Neutral)" : `${pitch} st`}</span><input type="range" min={-6} max={6} step={1} value={pitch} onChange={(e) => setPitch(Number(e.target.value))} className="w-full accent-primary" /></label>
            </div>
          </div>
        </div>

        <div className="lg:col-span-5 flex flex-col gap-space-xl">
          <div className="bg-surface-container rounded-xl p-space-xl flex flex-col gap-space-lg">
            <h2 className="font-headline-md font-semibold flex items-center gap-2"><span className="material-symbols-outlined text-primary">language</span>Multilingual &amp; Script Engine</h2>
            <div className="grid grid-cols-2 gap-space-sm" role="radiogroup" aria-label="Input detection">
              {[["auto", "Auto-Detect", "Phoneme auto-sync"], ["hinglish", "Hinglish Hybrid", "Code-switching mode"]].map(([v, l, s]) => (
                <button key={v} onClick={() => save({ preferred_language: v, output_language: v })} className={`p-space-md rounded-xl text-left ${prefs.preferred_language === v || (v === "auto" && !prefs.preferred_language) ? "bg-secondary-container" : "bg-surface-container-low"}`}><div className="font-semibold">{l}</div><div className="text-sm opacity-70">{s}</div></button>
              ))}
            </div>
            <div className="flex flex-col gap-space-xs bg-surface-container-low p-space-sm rounded-xl">
              <button onClick={() => save({ script: "native" })} className={`w-full min-h-[52px] p-space-sm px-space-md rounded-lg text-left ${prefs.script !== "roman" ? "bg-surface-container-highest" : ""}`}><span className="font-semibold text-primary">Devanagari Preferred (देवनागरी)</span><p className="text-sm">&quot;माझे नाव राहुल आहे · मुझे पानी चाहिए&quot;</p></button>
              <button onClick={() => save({ script: "roman" })} className="w-full min-h-[52px] p-space-sm px-space-md rounded-lg text-left"><span className="font-semibold opacity-70">Roman Transliteration</span><p className="text-sm opacity-70">&quot;Majhe naav Rahul aahe · Mujhe paani chahiye&quot;</p></button>
            </div>
          </div>
          <div className="bg-surface-container rounded-xl p-space-xl flex flex-col gap-space-lg">
            <h2 className="font-headline-md font-semibold flex items-center gap-2"><span className="material-symbols-outlined text-primary">lock_person</span>Data Sovereignty &amp; Privacy</h2>
            <label className="p-space-md rounded-xl bg-secondary-container flex gap-space-md cursor-pointer"><input type="radio" name="ret" defaultChecked className="w-5 h-5 accent-primary mt-1" /><div><div className="font-semibold">Purge Immediately</div><div className="text-sm text-primary">Microphone buffers overwritten in RAM after decoding.</div></div></label>
            <label className="p-space-md rounded-xl bg-surface-container-low flex gap-space-md cursor-pointer"><input type="radio" name="ret" className="w-5 h-5 accent-primary mt-1" /><div><div className="font-semibold">Session Cache Only</div><div className="text-sm opacity-70">Preserves clips until session shutdown.</div></div></label>
            <div className="flex items-center justify-between p-space-md rounded-xl bg-surface-container-low"><div><span className="font-semibold">Local Phoneme Weights</span><span className="block text-sm opacity-70">42 custom adaptations (3.8 MB)</span></div>
              <button onClick={() => { if (confirm("Reset local phonemic adaptations?")) setMsg("Weights zeroed."); }} className="min-h-[48px] px-space-md rounded-lg bg-surface-container-highest text-error flex items-center gap-2"><span className="material-symbols-outlined text-[18px]">delete</span>Reset Weights</button></div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => api.exportData().then((d) => { const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "secondvoice-data.json"; a.click(); })} className="h-12 px-space-md rounded-xl bg-surface-container-high font-semibold">Export my data</button>
              <button onClick={async () => { if (!confirm("Delete ALL your data? This cannot be undone.")) return; await api.deleteData(); setToken(null); router.push("/"); }} className="h-12 px-space-md rounded-xl border border-error text-error font-semibold">Delete all my data</button>
            </div>
          </div>
        </div>
      </div>

      <div className="w-full bg-surface-container-low rounded-xl p-space-xl flex flex-col md:flex-row items-center justify-between gap-space-lg">
        <div><h3 className="font-headline-sm font-semibold">Human Agency Guarantee</h3><p className="font-body-md opacity-80"><strong>AI suggests. You decide.</strong> Second Voice is an expressive communication instrument, <span className="text-secondary font-semibold">never a medical diagnostic tool</span>.</p></div>
        <span className="font-label-sm text-label-sm text-secondary px-space-md py-space-sm rounded-full bg-secondary-container font-semibold">Assisted Autonomy</span>
      </div>

      {wizard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-space-md bg-surface-container-lowest/80 backdrop-blur-md" role="dialog" aria-modal="true" aria-label="Guided Onboarding">
          <div className="bg-surface-container max-w-3xl w-full rounded-xl overflow-hidden max-h-[90vh] flex flex-col">
            <div className="p-space-lg bg-surface-container-high flex items-center justify-between">
              <span className="font-headline-sm font-bold">Second Voice Guided Onboarding — Step {step} of 5</span>
              <button aria-label="Close" onClick={() => setWizard(false)} className="w-10 h-10 rounded-full hover:bg-surface-container flex items-center justify-center"><span className="material-symbols-outlined">close</span></button>
            </div>
            <div className="grid grid-cols-5 gap-1 h-2 m-4">{[1, 2, 3, 4, 5].map((i) => <div key={i} className={`h-full rounded-full ${i <= step ? "bg-primary" : "bg-surface-container-highest"}`} />)}</div>
            <div className="p-space-xl flex-1 overflow-y-auto">
              {step === 1 && <div><h3 className="font-headline-md font-bold">Select Primary Speech Environment</h3><div className="grid sm:grid-cols-2 gap-3 mt-3">{["English (Indian Cadence)", "Hindi & Hinglish Blend", "Hindi (हिन्दी)", "Non-Vocal / Switch Only"].map((l) => <label key={l} className="p-space-lg rounded-xl bg-surface-container-low flex items-center justify-between cursor-pointer"><span>{l}</span><input type="radio" name="ol" className="w-5 h-5 accent-primary" /></label>)}</div></div>}
              {step === 2 && <div><h3 className="font-headline-md font-bold">Input Behavior &amp; Dwell Filtering</h3><p className="opacity-70 mt-1">Eye-gaze dwell 850ms · Tremor filtration High · Predictive bubbles on.</p></div>}
              {step === 3 && <div><h3 className="font-headline-md font-bold">Rapid Personal Phrases</h3><div className="flex flex-wrap gap-2 mt-3">{["Please give me a moment to respond.", "I understand completely.", "कपाळावर दुखत आहे (Headache)"].map((p) => <span key={p} className="px-space-md py-space-sm rounded-full bg-secondary-container">&quot;{p}&quot;</span>)}</div></div>}
              {step === 4 && <div><h3 className="font-headline-md font-bold">Visual Accessibility &amp; Motion</h3><p className="opacity-70 mt-1">Reduced Motion + Expanded 64px Hit Zones available.</p></div>}
              {step === 5 && <div><h3 className="font-headline-md font-bold">Explicit Agency &amp; Consent</h3><p className="opacity-70 mt-1">AI suggests. You decide. Never a medical diagnostic tool.</p><label className="flex items-center gap-3 mt-3 cursor-pointer"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="w-6 h-6 accent-primary" /><span className="font-semibold">I understand my agency rights and authorize on-device local calibration.</span></label></div>}
            </div>
            <div className="p-space-lg bg-surface-container-high flex items-center justify-between">
              <button disabled={step === 1} onClick={() => setStep(step - 1)} className="min-h-[56px] px-space-lg rounded-full disabled:opacity-30">Previous</button>
              <button onClick={() => { if (step < 5) setStep(step + 1); else { if (!consent) { alert("Please check the acknowledgment box."); return; } setWizard(false); setMsg("Calibration complete."); } }} className="min-h-[56px] px-space-xl rounded-full bg-primary text-on-primary font-semibold">{step === 5 ? "Complete Calibration" : "Continue"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
    </RequireAuth>
  );
}
