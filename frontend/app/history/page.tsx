"use client";
import RequireAuth from "@/components/RequireAuth";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type S = { id: number; title: string; language: string };

export default function History() {
  const [sessions, setSessions] = useState<S[]>([]);
  const [detail, setDetail] = useState<{ items: { original: string; suggestions: { proposed: string; status: string }[] }[]; approved: { text: string }[] } | null>(null);

  useEffect(() => {
    api.sessions().then((s) => setSessions(s as S[])).catch(() => {});
  }, []);

  return (
    <RequireAuth>
    <div className="space-y-4">
      <h1 className="font-serif text-3xl">Conversation history</h1>
      <div className="grid md:grid-cols-2 gap-4">
        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.id}>
              <button className="card w-full text-left text-lg" onClick={() => api.sessionDetail(s.id).then((d) => setDetail(d as never)).catch(() => {})}>
                <span className="underline">{s.title}</span> <span className="opacity-70 text-base">· {s.language}</span>
              </button>
            </li>
          ))}
          {sessions.length === 0 && <li className="text-lg opacity-70">No sessions yet.</li>}
        </ul>
        <div className="card">
          {!detail ? <p className="text-lg opacity-70">Select a session to see the full audit trail.</p> : (
            <>
              <h2 className="font-serif text-2xl">Audit trail</h2>
              {detail.items.map((it, i) => (
                <div key={i} className="mt-3 border-t pt-2">
                  <p className="text-lg"><strong>Heard:</strong> {it.original}</p>
                  {it.suggestions.map((g, j) => (
                    <p key={j} className="text-lg"><strong>Suggested:</strong> {g.proposed} <em>({g.status})</em></p>
                  ))}
                </div>
              ))}
              <h3 className="mt-3 text-xl font-semibold">Confirmed</h3>
              <ul className="list-disc ml-6 text-lg">{detail.approved.map((a, i) => <li key={i}>{a.text}</li>)}</ul>
            </>
          )}
        </div>
      </div>
      <p><Link className="underline text-lg" href="/dashboard">Back to dashboard</Link></p>
    </div>
    </RequireAuth>
  );
}
