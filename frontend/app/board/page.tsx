"use client";
import { useEffect, useState } from "react";
import { api, speakBrowser } from "@/lib/api";

const TILES = [
  { icon: "water_drop", title: "I need water", sub: "Quick hydrate request", phrase: "I need water" },
  { icon: "hourglass_top", title: "Please wait for me", sub: "Requesting time", phrase: "Please wait for me" },
  { icon: "chat_bubble", title: "I want to say something", sub: "Hold floor", phrase: "I want to say something" },
  { icon: "pause_circle", title: "I need a break", sub: "Sensory rest", phrase: "I need a break" },
  { icon: "favorite", title: "Thank you", sub: "Gratitude", phrase: "Thank you very much" },
  { icon: "emergency_share", title: "Call Caregiver", sub: "Immediate assist ping", phrase: "Call my caregiver immediately", urgent: true },
];

export default function Board() {
  const [staging, setStaging] = useState("I want to say something");
  const [phrases, setPhrases] = useState<string[]>([]);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    api.memory().then((m) => {
      const saved = (m as { content: string }[]).map((x) => x.content).filter(Boolean);
      if (saved.length) setPhrases(saved);
    }).catch(() => {});
  }, []);

  return (
    <div className="w-full px-margin py-space-xl max-w-7xl mx-auto flex flex-col gap-space-lg">
      <div className="bg-surface-container-high rounded-xl p-space-md">
        <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">Synthesizer Staging</span>
        <p className="font-body-xl text-body-xl text-primary font-medium min-h-[3rem]">{staging}</p>
        <div className="flex gap-space-sm mt-2">
          <button onClick={() => speakBrowser(staging)} className="flex-1 h-14 bg-primary text-on-primary rounded-xl font-semibold flex items-center justify-center gap-2"><span className="material-symbols-outlined">volume_up</span>Vocalize Message</button>
          <button onClick={() => setStaging("... (Touch an AAC tile or type)")} className="w-14 h-14 bg-surface-container rounded-xl" aria-label="Clear"><span className="material-symbols-outlined">backspace</span></button>
        </div>
      </div>
      <div><span className="font-label-sm text-label-sm uppercase tracking-widest text-primary font-semibold">Direct Expression Array</span><h1 className="font-headline-lg text-headline-lg text-on-surface">AAC High-Impact Communication Matrix</h1></div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-space-sm">
        {TILES.map((t) => (
          <button key={t.title} onClick={() => setStaging(t.phrase)} className={t.urgent ? "text-left h-36 bg-error-container text-on-error-container p-space-md rounded-xl" : "text-left h-36 bg-surface-container p-space-md rounded-xl hover:bg-surface-bright"}>
            <span className="material-symbols-outlined text-[24px]">{t.icon}</span>
            <span className="font-headline-sm text-headline-sm block font-semibold">{t.title}</span>
            <span className="font-label-sm text-label-sm opacity-70">{t.sub}</span>
          </button>
        ))}
        {phrases.map((p) => (
          <button key={p} onClick={() => speakBrowser(p)} className="text-left h-36 bg-surface-container p-space-md rounded-xl" aria-label={`Speak: ${p}`}>{p}</button>
        ))}
      </div>
      <form className="bg-surface-container p-space-md rounded-xl flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (!draft.trim()) return; try { await api.addMemory(draft.trim(), "phrase", "en"); } catch {} setPhrases((prev) => [...prev, draft.trim()]); setDraft(""); }}>
        <input aria-label="New board phrase" className="flex-1 bg-surface-container-lowest rounded-lg px-4 py-3 text-on-surface" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Add your own phrase…" />
        <button className="h-12 px-space-lg bg-primary text-on-primary rounded-xl font-semibold" type="submit">Add</button>
      </form>
    </div>
  );
}
