"use client";
import RequireAuth from "@/components/RequireAuth";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, loggedIn } from "@/lib/api";
import { Recorder } from "@/lib/audio";

type Session = { id: number; title: string; language: string };

export default function Dashboard() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [phrases, setPhrases] = useState<{ content: string }[]>([]);
  const [lang, setLang] = useState("en");
  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState("");
  const rec = useRef(new Recorder());

  useEffect(() => {
    if (!loggedIn()) {
      router.push("/login");
      return;
    }
    api.prefs().then((p) => setLang((p as { preferred_language: string }).preferred_language || "en")).catch(() => {});
    api.sessions().then((s) => setSessions(s as Session[])).catch(() => {});
    api.memory().then((m) => setPhrases((m as { content: string }[]).filter((x) => x).slice(0, 8))).catch(() => {});
  }, [router]);

  async function startSession() {
    const s = (await api.createSession(`Session ${new Date().toLocaleString()}`, lang)) as Session;
    router.push(`/communicate/${s.id}`);
  }

  async function quickRecord() {
    try {
      if (!recording) {
        await rec.current.start();
        setRecording(true);
        setStatus("Recording… tap again to stop.");
      } else {
        const blob = await rec.current.stop();
        setRecording(false);
        setStatus("Processing…");
        const s = (await api.createSession(`Session ${new Date().toLocaleString()}`, lang)) as Session;
        const up = (await api.uploadAudio(s.id, blob)) as { audio_id: number };
        sessionStorage.setItem("sv_pending_audio", JSON.stringify({ sessionId: s.id, audioId: up.audio_id, lang }));
        router.push(`/communicate/${s.id}?fresh=1`);
      }
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Microphone unavailable — you can type instead in the workspace.");
      setRecording(false);
    }
  }

  return (
    <RequireAuth>
    <div className="space-y-6">
      <div className="card flex flex-wrap items-center gap-4">
        <button
          onClick={quickRecord}
          aria-label={recording ? "Stop recording" : "Start recording"}
          className={`w-24 h-24 rounded-full text-4xl text-white ${recording ? "bg-red-700" : "bg-accent hover:bg-accentdark"}`}
        >
          {recording ? "■" : "●"}
        </button>
        <div>
          <p className="text-lg">Language: <strong>{lang}</strong> <Link className="underline text-base" href="/settings">(change)</Link></p>
          <p className="text-lg" role="status">{status || "Tap the microphone and speak naturally."}</p>
          <div className="mt-2 flex gap-2">
            <button onClick={startSession} className="btn-big bg-ink text-white">Open workspace</button>
            <button onClick={startSession} className="btn-big border-2 border-ink">Type instead</button>
          </div>
        </div>
      </div>

      <section aria-label="Quick phrases" className="card">
        <h2 className="font-serif text-2xl">Quick phrases</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {["I need help.", "Please wait.", "I need some time.", "Please repeat that.", "Thank you.", "I need a break.",
            ...phrases.map((p) => p.content)].slice(0, 12).map((p) => (
            <span key={p} className="text-lg border border-ink rounded-full px-4 py-2 bg-sand text-ink">{p}</span>
          ))}
        </div>
        <Link className="underline text-lg mt-3 inline-block" href="/board">Edit communication board</Link>
      </section>

      <section aria-label="Recent sessions" className="card">
        <h2 className="font-serif text-2xl">Recent communication</h2>
        <ul className="mt-2 space-y-2">
          {sessions.slice(0, 8).map((s) => (
            <li key={s.id}>
              <Link className="text-lg underline" href={`/communicate/${s.id}`}>{s.title}</Link>
              <span className="ml-2 text-base opacity-70">{s.language}</span>
            </li>
          ))}
          {sessions.length === 0 && <li className="text-lg opacity-70">No sessions yet.</li>}
        </ul>
      </section>
    </div>
    </RequireAuth>
  );
}
