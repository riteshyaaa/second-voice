"use client";
import RequireAuth from "@/components/RequireAuth";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

/** The workshop is the home screen: open the latest session, or start one. */
export default function CommunicateHome() {
  const router = useRouter();
  useEffect(() => {
    (async () => {
      try {
        const sessions = (await api.sessions()) as { id: number }[];
        if (sessions && sessions.length > 0) {
          router.replace(`/communicate/${sessions[0].id}`);
          return;
        }
      } catch {}
      try {
        const prefs = (await api.prefs()) as { preferred_language?: string };
        const s = (await api.createSession(
          `Session ${new Date().toLocaleString()}`,
          (prefs as { preferred_language?: string }).preferred_language || "en",
        )) as { id: number };
        router.replace(`/communicate/${s.id}`);
      } catch {
        router.replace("/login");
      }
    })();
  }, [router]);
  return (
    <RequireAuth>
      <p className="text-lg" role="status">Opening your workshop…</p>
    </RequireAuth>
  );
}
