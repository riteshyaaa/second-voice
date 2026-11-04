"use client";
import RequireAuth from "@/components/RequireAuth";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Stats = {
  words_learned: number; corrections_approved: number; suggestions_accepted: number;
  suggestions_rejected: number; suggestions_total: number; acceptance_rate: number;
  languages_used: Record<string, number>;
  frequent_phrases: { phrase: string; count: number }[];
  top_vocabulary: { term: string; times_used: number }[];
};

type Review = {
  vocabulary: { id: number; term: string; language: string; status: string; source: string; times_used: number; actions: string[] }[];
  correction_patterns: { rank: number; from: string; to: string; count: number; ambiguous: boolean; sources: string[] }[];
  suggestion_stats: { suggestions_total: number; suggestions_accepted: number; suggestions_rejected: number; acceptance_rate: number; false_personalizations: number; unwanted_rate: number };
  calibration_clips: { id: number; prompt_text: string; consent_granted: boolean; status: string }[];
  calibration_note: string;
};

export default function Learn() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [sample, setSample] = useState("I want meet doctor");
  const [demo, setDemo] = useState<Record<string, { text?: string; explanation?: string; provider?: string; note?: string }> | null>(null);

  useEffect(() => {
    api.stats().then((s) => setStats(s as Stats)).catch(() => {});
    api.review().then((r) => setReview(r as Review)).catch(() => {});
  }, []);

  return (
    <RequireAuth>
    <div className="space-y-5 max-w-3xl">
      <h1 className="font-serif text-3xl">What the system has learned</h1>
      <p className="text-lg">Only from words and corrections you approved. Remove anything, any time.</p>
      {!stats ? <p className="text-lg">Loading…</p> : (
        <div className="grid sm:grid-cols-3 gap-3">
          {[
            ["Words learned", stats.words_learned],
            ["Corrections approved", stats.corrections_approved],
            ["Acceptance rate", `${Math.round(stats.acceptance_rate * 100)}% (${stats.suggestions_accepted}/${stats.suggestions_total})`],
          ].map(([k, v]) => (
            <div key={k as string} className="card"><p className="text-base opacity-70">{k}</p><p className="font-serif text-3xl">{v}</p></div>
          ))}
        </div>
      )}
      {stats && (
        <>
          <section className="card">
            <h2 className="font-serif text-2xl">Languages used</h2>
            <p className="text-lg mt-1">{Object.entries(stats.languages_used).map(([l, n]) => `${l}: ${n}`).join(" · ") || "—"}</p>
          </section>
          <section className="card">
            <h2 className="font-serif text-2xl">Top vocabulary</h2>
            <ul className="list-disc ml-6 text-lg">{stats.top_vocabulary.map((v) => <li key={v.term}>{v.term} (used {v.times_used}×)</li>)}</ul>
          </section>
        </>
      )}
      {review && review.correction_patterns.length > 0 && (
        <section className="card">
          <h2 className="font-serif text-2xl">Corrections you repeat, ranked</h2>
          <p className="text-lg mt-1">Most-used first. The system applies these automatically — remove the underlying correction to stop one.</p>
          <ol className="mt-2 space-y-2 text-lg">
            {review.correction_patterns.map((p) => (
              <li key={`${p.from}-${p.to}`}>
                <span className="font-semibold">#{p.rank} “{p.from}” → “{p.to}”</span> ({p.count}×)
                {p.ambiguous && <span> — ambiguous: this has led to more than one reading</span>}
              </li>
            ))}
          </ol>
        </section>
      )}
      {review && (
        <section className="card">
          <h2 className="font-serif text-2xl">Your vocabulary</h2>
          {review.vocabulary.length === 0 && <p className="text-lg mt-1">Nothing saved yet.</p>}
          <ul className="mt-1 space-y-1 text-lg">
            {review.vocabulary.map((v) => (
              <li key={v.id}>{v.term} <span className="opacity-70">({v.language}, {v.status}, used {v.times_used}×)</span></li>
            ))}
          </ul>
          <p className="text-lg mt-2 opacity-70">Edit or remove entries on the vocabulary page. Calibration: {review.calibration_note}</p>
        </section>
      )}
      <section className="card" aria-label="Evaluation demo">
        <h2 className="font-serif text-2xl">Evaluation: one sample, four pipelines</h2>
        <div className="mt-2 flex gap-2">
          <input aria-label="Sample transcript" className="flex-1 text-lg border rounded-lg px-4 py-3" value={sample} onChange={(e) => setSample(e.target.value)} />
          <button className="btn-big bg-ink text-white" onClick={() => api.pipelineDemo(sample).then((d) => setDemo(d as never)).catch(() => {})}>Compare</button>
        </div>
        {demo && (
          <dl className="mt-3 space-y-2 text-lg">
            <div><dt className="font-semibold">1 · Baseline ASR</dt><dd>{demo.baseline_asr?.text}</dd></div>
            <div><dt className="font-semibold">2 · Context-heavy</dt><dd>{demo.context_heavy?.text}</dd></div>
            <div><dt className="font-semibold">3 · Evidence-first</dt><dd>{demo.evidence_first?.text} — {demo.evidence_first?.explanation}</dd></div>
            <div><dt className="font-semibold">4 · Personalized ({demo.personalized?.provider})</dt><dd>{demo.personalized?.text}</dd></div>
            <p className="opacity-70">You remain in control: none of these speak until confirmed.</p>
          </dl>
        )}
      </section>
    </div>
    </RequireAuth>
  );
}
