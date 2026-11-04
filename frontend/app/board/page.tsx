"use client";
import RequireAuth from "@/components/RequireAuth";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, stopBrowserSpeech } from "@/lib/api";
import { CARD_CATEGORIES, groupCards, tapToSpeak, type Card } from "@/lib/cards";

export default function Board() {
  const [cards, setCards] = useState<Card[]>([]);
  const [filter, setFilter] = useState("");
  const [staging, setStaging] = useState("Tap a card to speak it.");
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");
  const [label, setLabel] = useState("");
  const [phrase, setPhrase] = useState("");
  const [lang, setLang] = useState("en");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    try {
      setCards((await api.cards()) as Card[]);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load cards.");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function play(url: string) {
    setAudioUrl(url);
    requestAnimationFrame(() => audioRef.current?.play().catch(() => {}));
  }

  async function tap(card: Card) {
    try {
      stopBrowserSpeech();
      const r = await tapToSpeak(card, play);
      setStaging(r.phrase);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not speak this card.");
    }
  }

  async function toggleFav(card: Card) {
    try {
      await api.patchCard(card.id, { favorite: !card.favorite });
      setCards((prev) => prev.map((c) => (c.id === card.id ? { ...c, favorite: !c.favorite } : c)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update favorite.");
    }
  }

  async function remove(id: number) {
    try {
      await api.delCard(id);
      setCards((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete card.");
    }
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim() || !phrase.trim()) return;
    try {
      const c = (await api.addCard({ label: label.trim(), phrase: phrase.trim(), language: lang })) as Card;
      setCards((prev) => [...prev, c]);
      setLabel("");
      setPhrase("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add card.");
    }
  }

  const groups = groupCards(cards.filter((c) => !filter || c.category === filter));

  return (
    <RequireAuth>
    <div className="w-full px-margin py-space-xl max-w-7xl mx-auto flex flex-col gap-space-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface">Communication board</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">Tapping a card confirms it and speaks it through your account history. Nothing speaks before you tap.</p>
      </div>

      <div className="bg-surface-container-high rounded-xl p-space-md">
        <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">Last spoken</span>
        <p className="font-body-xl text-body-xl text-primary font-medium min-h-[3rem]" role="status">{staging}</p>
        <div className="flex gap-space-sm mt-2 items-center">
          {audioUrl && <audio ref={audioRef} className="flex-1" controls src={audioUrl} aria-label="Card speech playback" />}
          <button onClick={() => { stopBrowserSpeech(); audioRef.current?.pause(); setAudioUrl(""); }} className="min-h-[56px] px-space-md bg-surface-container rounded-xl font-semibold" aria-label="Stop speech">Stop</button>
        </div>
      </div>

      {error && <p className="font-body-sm text-body-sm text-error" role="alert">{error}</p>}

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by category">
        <button onClick={() => setFilter("")} className={`min-h-[48px] px-4 rounded-full font-semibold ${!filter ? "bg-primary text-on-primary" : "bg-surface-container"}`}>All</button>
        {CARD_CATEGORIES.map((c) => (
          <button key={c} onClick={() => setFilter(filter === c ? "" : c)} className={`min-h-[48px] px-4 rounded-full font-semibold ${filter === c ? "bg-primary text-on-primary" : "bg-surface-container"}`}>{c}</button>
        ))}
      </div>

      {groups.map((g) => (
        <section key={g.key} aria-label={g.title}>
          <h2 className="font-headline-sm text-headline-sm text-on-surface mb-2">{g.title}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-space-sm">
            {g.cards.map((c) => (
              <div key={c.id} className={`text-left min-h-[9rem] p-space-md rounded-xl flex flex-col gap-1 ${c.category === "emergency" ? "bg-error-container text-on-error-container" : "bg-surface-container"}`}>
                <button onClick={() => tap(c)} className="text-left flex flex-col gap-1 flex-1" aria-label={`Speak: ${c.label}`}>
                  <span className="text-[24px]" aria-hidden>{c.emoji || ""}</span>
                  <span className="font-headline-sm text-headline-sm font-semibold">{c.label}</span>
                  {c.label_native && <span className="font-body-sm text-body-sm opacity-80">{c.label_native}</span>}
                </button>
                <div className="flex gap-2 mt-1">
                  <button onClick={() => toggleFav(c)} aria-pressed={c.favorite} aria-label={c.favorite ? `Remove ${c.label} from favorites` : `Add ${c.label} to favorites`} className="min-h-[44px] min-w-[44px] rounded-lg font-semibold">{c.favorite ? "★" : "☆"}</button>
                  <button onClick={() => remove(c.id)} aria-label={`Delete ${c.label}`} className="min-h-[44px] min-w-[44px] rounded-lg opacity-70">Delete</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      <form className="bg-surface-container p-space-md rounded-xl flex flex-col sm:flex-row gap-2" onSubmit={add}>
        <input aria-label="Card label" className="flex-1 rounded-lg px-4 py-3 min-h-[52px]" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label, e.g. I need water" />
        <input aria-label="Card phrase" className="flex-[2] rounded-lg px-4 py-3 min-h-[52px]" value={phrase} onChange={(e) => setPhrase(e.target.value)} placeholder="Exact phrase to speak" />
        <select aria-label="Card language" value={lang} onChange={(e) => setLang(e.target.value)} className="rounded-lg px-4 py-3 min-h-[52px]">
          <option value="en">English</option>
          <option value="hi">Hindi</option>
        </select>
        <button className="min-h-[52px] px-space-lg bg-primary text-on-primary rounded-xl font-semibold" type="submit">Add card</button>
      </form>
    </div>
    </RequireAuth>
  );
}
