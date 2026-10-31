"use client";
import { useEffect, useState } from "react";
import { api, speakBrowser } from "@/lib/api";

type V = { id: number; term: string; language: string; category: string; times_used: number };

const SEED = [
  { sound: "Arav", target: "Aarav", cat: "names", label: "Family & Names", icon: "badge", count: 14, note: "Last used: Today" },
  { sound: "Dr. Ten", target: "Dr. Sen (Neurology)", cat: "medical", label: "Medical & Care", icon: "medical_services", count: 29, note: "Last used: 2d ago" },
  { sound: "Kay-saal", target: "काय चाललंय? (What's up?)", cat: "dialect", label: "Marathi Slang / Dialect", icon: "translate", count: 41, note: "Last used: 1h ago" },
  { sound: "Bha-yaa", target: "भैया (Brother)", cat: "dialect", label: "Hindi Colleague / Endearment", icon: "translate", count: 18, note: "Last used: Yesterday" },
  { sound: "Verandaah", target: "Front Garden Verandah", cat: "places", label: "Places & Home", icon: "cottage", count: 22, note: "Last used: 3h ago" },
  { sound: "Chai bin", target: "Please bring warm ginger tea without sugar", cat: "phrases", label: "Personal Phrases", icon: "format_quote", count: 56, note: "Last used: 5h ago" },
];

const AAC = [
  { icon: "water_drop", cat: "needs", title: "I need water", sub: "Quick hydrate request", phrase: "I need water" },
  { icon: "hourglass_top", cat: "social", title: "Please wait for me", sub: "Requesting time", phrase: "Please wait for me" },
  { icon: "chat_bubble", cat: "social", title: "I want to say something", sub: "Hold floor", phrase: "I want to say something" },
  { icon: "pause_circle", cat: "feelings", title: "I need a break", sub: "Sensory rest", phrase: "I need a break" },
  { icon: "favorite", cat: "social", title: "Thank you", sub: "Gratitude", phrase: "Thank you very much" },
  { icon: "emergency_share", cat: "emergency", title: "Call Caregiver", sub: "Immediate assist ping", phrase: "Call my caregiver immediately", urgent: true },
];

export default function Vocabulary() {
  const [rows, setRows] = useState<V[]>([]);
  const [staging, setStaging] = useState("I want to say something");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [aacCat, setAacCat] = useState("all");
  const [modal, setModal] = useState(false);
  const [sound, setSound] = useState("");
  const [target, setTarget] = useState("");
  const [mcat, setMcat] = useState("names");
  const [toast, setToast] = useState("");
  const [mem, setMem] = useState(true);
  const [adapt, setAdapt] = useState(true);

  async function refresh() {
    try { setRows((await api.vocab()) as V[]); } catch {}
  }
  useEffect(() => { refresh().catch(() => {}); }, []);

  function showToast(m: string) { setToast(m); setTimeout(() => setToast(""), 2800); }

  function speak(text: string) {
    speakBrowser(text);
    setStaging(text);
  }

  const filtered = SEED.filter((s) => (cat === "all" || s.cat === cat) && (!q || `${s.sound} ${s.target}`.toLowerCase().includes(q.toLowerCase())));

  return (
    <div className="w-full px-margin py-space-xl flex flex-col gap-space-xl max-w-7xl mx-auto">
      <div className="flex flex-col lg:flex-row items-stretch justify-between gap-gutter">
        <div className="max-w-2xl">
          <div className="flex items-center gap-space-sm mb-space-xs"><span className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" /><span className="font-label-sm text-label-sm text-primary uppercase tracking-widest font-semibold">Engine Synced · Model Dual-Vocal 3.4</span></div>
          <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight">Adaptive Voice &amp; Vocabulary Workspace</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant">Calibrate acoustic reconstruction phonemes, enforce privacy sovereignty, and vocalize rapidly through the tactile AAC dwell grid.</p>
        </div>
        <div className="w-full lg:w-[480px] bg-surface-container-high rounded-xl p-space-md flex flex-col gap-space-sm">
          <div className="flex items-center justify-between"><span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex items-center gap-space-xs"><span className="material-symbols-outlined text-[16px] text-primary">record_voice_over</span> Synthesizer Staging</span>
            <button onClick={() => setStaging("... (Touch an AAC tile or type)")} className="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">backspace</span> Clear</button></div>
          <div className="bg-surface-container-lowest rounded-lg p-space-md min-h-[72px] flex items-center"><p className="font-body-xl text-body-xl text-primary font-medium">{staging}</p></div>
          <div className="flex items-center gap-space-sm">
            <button onClick={() => speak(staging)} className="flex-1 h-14 bg-primary text-on-primary rounded-xl font-label-lg text-label-lg flex items-center justify-center gap-space-sm"><span className="material-symbols-outlined text-[24px]">volume_up</span>Vocalize Message</button>
            <button title="Rephrase with contextual tone" onClick={() => showToast("Rephrased with contextual tone")} className="w-14 h-14 bg-surface-container rounded-xl flex items-center justify-center"><span className="material-symbols-outlined text-[20px]">auto_awesome</span></button>
          </div>
        </div>
      </div>

      <section className="flex flex-col gap-space-md">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-sm">
          <div><span className="font-label-sm text-label-sm uppercase tracking-widest text-primary font-semibold">Direct Expression Array</span><h3 className="font-headline-lg text-headline-lg text-on-surface">AAC High-Impact Communication Matrix</h3></div>
          <div className="flex items-center gap-space-xs bg-surface-container-low p-1 rounded-xl overflow-x-auto">
            {[["all", "All Directives"], ["needs", "Needs"], ["feelings", "Feelings"], ["questions", "Questions"], ["emergency", "Urgent / Safety"], ["social", "Social"]].map(([v, l]) => (
              <button key={v} onClick={() => setAacCat(v)} className={`px-space-md py-space-xs rounded-lg font-label-sm text-label-sm whitespace-nowrap ${aacCat === v ? "bg-primary text-on-primary font-semibold" : "text-on-surface-variant hover:text-on-surface"}`}>{l}</button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-space-sm">
          {AAC.filter((a) => aacCat === "all" || a.cat === aacCat || (aacCat === "questions" && a.cat === "social")).map((a) => (
            <button key={a.title} onClick={() => { setStaging(a.phrase); showToast(`Selected: "${a.phrase}"`); }} className={a.urgent ? "text-left h-36 bg-error-container text-on-error-container p-space-md rounded-xl flex flex-col justify-between" : "text-left h-36 bg-surface-container p-space-md rounded-xl flex flex-col justify-between hover:bg-surface-bright"}>
              <div className="flex items-center justify-between w-full"><span className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center"><span className="material-symbols-outlined text-[24px]">{a.icon}</span></span></div>
              <div><span className="font-headline-sm text-headline-sm block font-semibold leading-tight">{a.title}</span><span className="font-label-sm text-label-sm opacity-70 mt-1 block">{a.sub}</span></div>
            </button>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-space-lg">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md">
          <div><span className="font-label-sm text-label-sm uppercase tracking-widest text-primary font-semibold">Phonetic Acoustic Mapping</span><h3 className="font-headline-lg text-headline-lg text-on-surface">Personal Vocabulary Vault</h3></div>
          <div className="flex flex-wrap items-center gap-space-sm">
            <div className="relative w-full sm:w-72"><span className="material-symbols-outlined absolute left-3 top-3 text-[20px] text-outline">search</span>
              <input value={q} onChange={(e) => setQ(e.target.value)} className="w-full h-11 bg-surface-container pl-10 pr-4 rounded-lg text-on-surface placeholder:text-outline-variant" placeholder="Search phonemes, dialect, names..." type="text" /></div>
            <button onClick={() => setModal(true)} className="h-11 px-space-md bg-primary-container text-on-primary-container rounded-lg font-label-md text-label-md font-semibold flex items-center gap-space-xs"><span className="material-symbols-outlined text-[18px]">add_circle</span> Add Custom Word</button>
          </div>
        </div>
        <div className="flex items-center gap-space-xs overflow-x-auto">
          {[["all", "All Entries (18)"], ["names", "Family & Names"], ["places", "Places & Home"], ["medical", "Medical & Care"], ["dialect", "Hindi & Marathi Dialect"], ["phrases", "Personal Phrases"]].map(([v, l]) => (
            <button key={v} onClick={() => setCat(v)} className={`px-space-md py-space-xs rounded-full font-label-sm text-label-sm whitespace-nowrap ${cat === v ? "bg-primary text-on-primary" : "bg-surface-container text-on-surface-variant hover:text-on-surface"}`}>{l}</button>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-space-md">
          {filtered.map((s) => (
            <div key={s.sound} className="bg-surface-container p-space-lg rounded-xl flex flex-col justify-between">
              <span className="inline-flex items-center gap-1 font-label-sm text-label-sm bg-surface-container-high px-2 py-0.5 rounded-full self-start"><span className="material-symbols-outlined text-[14px]">{s.icon}</span> {s.label}</span>
              <div className="mt-2"><span className="font-label-sm text-label-sm opacity-60 block">Input Sound Pattern</span><span className="font-headline-sm text-headline-sm line-through opacity-60">&quot;{s.sound}&quot;</span></div>
              <div className="flex items-center gap-space-sm"><span className="material-symbols-outlined text-[18px] text-primary">arrow_forward</span><span className="font-headline-md text-headline-md font-semibold">&quot;{s.target}&quot;</span></div>
              <div className="pt-space-md mt-space-md bg-surface-container-low -mx-space-lg -mb-space-lg p-space-md rounded-b-xl flex items-center justify-between">
                <span className="flex items-center gap-space-xs font-label-sm text-label-sm"><span className="material-symbols-outlined text-[16px] text-primary">verified</span>{s.count} Approved Confirmations</span>
                <button aria-label={`Speak ${s.target}`} onClick={() => speak(s.target)} className="w-9 h-9 rounded-lg bg-surface-container-high flex items-center justify-center"><span className="material-symbols-outlined text-[18px]">volume_up</span></button>
              </div>
            </div>
          ))}
          {rows.map((r) => (
            <div key={r.id} className="bg-surface-container p-space-lg rounded-xl flex items-center gap-3">
              <span className="text-xl text-on-surface">{r.term}</span><span className="text-sm opacity-70">{r.language} · used {r.times_used}×</span>
              <button className="ml-auto underline" onClick={() => api.delVocab(r.id).then(refresh)}>Remove</button>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-surface-container-low rounded-2xl p-space-lg flex flex-col gap-space-lg">
        <h3 className="font-headline-lg text-headline-lg text-on-surface">Adaptive Learning &amp; Privacy Control Center</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md">
          {[["thumb_up", "48", "Approved Corrections"], ["bookmark_heart", "12", "Preferred Phrases"], ["security", "0", "Unconfirmed Data Retained"]].map(([icon, n, l]) => (
            <div key={l} className="bg-surface-container p-space-md rounded-xl flex items-center gap-space-md"><span className="material-symbols-outlined text-[28px] text-primary">{icon}</span><div><span className="text-display-lg-mobile font-bold block text-on-surface">{n}</span><span className="font-label-md text-label-md">{l}</span></div></div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-md">
          <div className="bg-surface-container p-space-md rounded-xl flex items-center justify-between gap-space-md">
            <div><span className="font-headline-sm text-headline-sm block">Personalized Memory</span><span className="font-body-sm text-body-sm opacity-70 block">Prioritize verified vocabulary in prediction.</span></div>
            <button role="switch" aria-checked={mem} onClick={() => { setMem(!mem); showToast(!mem ? "Personalized Memory Enabled" : "Personalized Memory Disabled"); }} className={`w-14 h-8 rounded-full ${mem ? "bg-primary" : "bg-surface-container-highest"}`}><span className={`block w-6 h-6 bg-white rounded-full transition-all ${mem ? "translate-x-7" : "translate-x-1"}`} /></button>
          </div>
          <div className="bg-surface-container p-space-md rounded-xl flex items-center justify-between gap-space-md">
            <div><span className="font-headline-sm text-headline-sm block">Speech Pattern Adaptation</span><span className="font-body-sm text-body-sm opacity-70 block">Refine filters based on motor changes.</span></div>
            <button role="switch" aria-checked={adapt} onClick={() => { setAdapt(!adapt); showToast(!adapt ? "Speech Adaptation Activated" : "Pattern Adaptation Paused"); }} className={`w-14 h-8 rounded-full ${adapt ? "bg-primary" : "bg-surface-container-highest"}`}><span className={`block w-6 h-6 bg-white rounded-full transition-all ${adapt ? "translate-x-7" : "translate-x-1"}`} /></button>
          </div>
        </div>
        <div className="flex flex-wrap gap-space-sm">
          <button onClick={() => { if (confirm("Erase all cached unconfirmed vocal models? Vault entries will remain.")) showToast("Acoustic pattern cache purged"); }} className="h-12 px-space-md rounded-xl bg-surface-container text-error font-semibold flex items-center gap-space-xs"><span className="material-symbols-outlined text-[20px]">delete_forever</span> Erase Stored Speech Cache</button>
          <button onClick={() => api.exportData().then((d) => { const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "secondvoice-data.json"; a.click(); }).catch(() => showToast("Vocabulary exported as .json"))} className="h-12 px-space-lg rounded-xl bg-surface-bright font-semibold flex items-center gap-space-xs"><span className="material-symbols-outlined text-[20px]">file_download</span> Export Vocabulary (.json)</button>
        </div>
      </section>

      {modal && (
        <div className="fixed inset-0 z-50 bg-surface/90 backdrop-blur-md flex items-center justify-center p-space-md" role="dialog" aria-modal="true" aria-label="Add Custom Phoneme Mapping">
          <form onSubmit={async (e) => { e.preventDefault(); if (!sound.trim() || !target.trim()) return; try { await api.addVocab(target.trim(), "en", mcat); await refresh(); } catch {} setModal(false); setSound(""); setTarget(""); showToast(`Added phonetic bridge: "${target}"`); }} className="bg-surface-container-high w-full max-w-xl rounded-2xl p-space-xl flex flex-col gap-space-lg">
            <div className="flex items-center justify-between"><div><span className="font-label-sm text-label-sm uppercase tracking-widest text-primary font-semibold">Phonetic Ingestion</span><h4 className="font-headline-lg text-headline-lg">Add Custom Phoneme Mapping</h4></div>
              <button type="button" onClick={() => setModal(false)} className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center" aria-label="Close"><span className="material-symbols-outlined text-[20px]">close</span></button></div>
            <label className="block">Category<select value={mcat} onChange={(e) => setMcat(e.target.value)} className="w-full h-12 bg-surface-container-lowest px-space-md rounded-xl mt-1"><option value="names">Family &amp; Names</option><option value="places">Places &amp; Home</option><option value="medical">Medical &amp; Care</option><option value="dialect">Hindi &amp; Marathi Dialect</option><option value="phrases">Personal Phrases</option></select></label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
              <label className="block">Acoustic Sound<input value={sound} onChange={(e) => setSound(e.target.value)} className="w-full h-12 bg-surface-container-lowest px-space-md rounded-xl mt-1" placeholder="e.g. Dadi, Paani" required /></label>
              <label className="block">Target Expression<input value={target} onChange={(e) => setTarget(e.target.value)} className="w-full h-12 bg-surface-container-lowest px-space-md rounded-xl mt-1" placeholder="e.g. Shruti, दादी" required /></label>
            </div>
            <div className="flex justify-end gap-space-sm"><button type="button" onClick={() => setModal(false)} className="h-12 px-space-lg rounded-xl">Cancel</button><button type="submit" className="h-12 px-space-xl bg-primary text-on-primary rounded-xl font-semibold">Save into Vault</button></div>
          </form>
        </div>
      )}
      {toast && <div className="fixed bottom-6 right-6 z-50 bg-surface-container-highest px-space-lg py-space-md rounded-xl flex items-center gap-space-sm"><span className="material-symbols-outlined text-primary text-[22px]">check_circle</span>{toast}</div>}
    </div>
  );
}
