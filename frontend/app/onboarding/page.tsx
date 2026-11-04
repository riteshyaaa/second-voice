"use client";
import RequireAuth from "@/components/RequireAuth";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const STEPS = ["Language & Phonetics", "Input Pacing & Dwell", "Personal Vocabulary Setup", "Accessibility & Motion", "Explicit Autonomy & Consent"];

export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [lang, setLang] = useState("en");
  const [script, setScript] = useState("native");
  const [names, setNames] = useState("");
  const [consent, setConsent] = useState(false);

  async function finish() {
    if (!consent) { alert("Please check the acknowledgment box."); return; }
    await api.patchPrefs({ preferred_language: lang, output_language: lang, script });
    for (const term of names.split(",").map((s) => s.trim()).filter(Boolean)) {
      await api.addVocab(term, lang, "name");
    }
    router.push("/communicate");
  }

  return (
    <RequireAuth>
    <div className="w-full px-margin py-space-xl max-w-3xl mx-auto">
      <div className="bg-surface-container rounded-xl overflow-hidden">
        <div className="p-space-lg bg-surface-container-high"><span className="font-headline-sm font-bold">Second Voice Guided Onboarding — Step {step} of 5: {STEPS[step - 1]}</span></div>
        <div className="grid grid-cols-5 gap-1 h-2 m-4">{[1, 2, 3, 4, 5].map((i) => <div key={i} className={`h-full rounded-full ${i <= step ? "bg-primary" : "bg-surface-container-highest"}`} />)}</div>
        <div className="p-space-xl min-h-[300px]">
          {step === 1 && (
            <div><h1 className="font-headline-md font-bold">Select Primary Speech Environment</h1>
              <div className="mt-3 grid grid-cols-2 gap-2" role="radiogroup" aria-label="Preferred language">
                {[["en", "English"], ["hi", "हिन्दी (Hindi)"], ["hinglish", "Hinglish"]].map(([v, l]) => (
                  <button key={v} role="radio" aria-checked={lang === v} onClick={() => setLang(v)} className={`min-h-[56px] rounded-xl border-2 ${lang === v ? "border-primary bg-primary/10" : "border-surface-container-high"}`}>{l}</button>
                ))}
              </div>
              <div className="flex gap-2 mt-3" role="radiogroup" aria-label="Script">{[["native", "देवनागरी"], ["roman", "Roman"], ["mixed", "Mixed"]].map(([v, l]) => <button key={v} onClick={() => setScript(v)} className={`min-h-[48px] px-4 rounded-xl border-2 ${script === v ? "border-primary" : "border-surface-container-high"}`}>{l}</button>)}</div>
            </div>
          )}
          {step === 2 && <div><h2 className="font-headline-md font-bold">Input Behavior &amp; Dwell Filtering</h2><p className="mt-2 opacity-70">Eye-gaze dwell 850ms · Tremor filtration High · Predictive bubbles on.</p></div>}
          {step === 3 && (
            <div><h2 className="font-headline-md font-bold">Rapid Personal Phrases</h2>
              <div className="flex flex-wrap gap-2 mt-3">{["Please give me a moment to respond.", "I understand completely."].map((p) => <span key={p} className="px-4 py-2 rounded-full bg-secondary-container">&quot;{p}&quot;</span>)}</div>
              <label className="block mt-4"><span className="font-semibold">Names the system often gets wrong (optional, comma-separated)</span>
                <input aria-label="Important names" className="mt-2 w-full bg-surface-container-lowest rounded-lg px-4 py-3 text-on-surface" placeholder="Aarav, Sunita…" value={names} onChange={(e) => setNames(e.target.value)} /></label>
            </div>
          )}
          {step === 4 && <div><h2 className="font-headline-md font-bold">Visual Accessibility &amp; Motion</h2><p className="mt-2 opacity-70">Reduced Motion + Expanded 64px Hit Zones. Change anytime in Settings.</p></div>}
          {step === 5 && <div><h2 className="font-headline-md font-bold">Explicit Agency &amp; Consent</h2><p className="mt-2 opacity-70">AI suggests. You decide. Never a medical diagnostic tool.</p>
            <label className="flex items-center gap-3 mt-3 cursor-pointer"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="w-6 h-6 accent-primary" /><span className="font-semibold">I understand my agency rights and authorize on-device local calibration.</span></label></div>}
        </div>
        <div className="p-space-lg bg-surface-container-high flex items-center justify-between">
          <button disabled={step === 1} onClick={() => setStep(step - 1)} className="min-h-[56px] px-space-lg rounded-full disabled:opacity-30">Previous</button>
          {step < 5 ? <button onClick={() => setStep(step + 1)} className="min-h-[56px] px-space-xl rounded-full bg-primary text-on-primary font-semibold">Continue</button>
          : <button onClick={finish} className="min-h-[56px] px-space-xl rounded-full bg-primary text-on-primary font-semibold">Complete Calibration</button>}
        </div>
      </div>
    </div>
    </RequireAuth>
  );
}
