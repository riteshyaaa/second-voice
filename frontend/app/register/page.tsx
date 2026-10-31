"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function Register() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = (await api.register(email, password, name)) as { access_token: string };
      setToken(r.access_token);
      router.push("/onboarding");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Registration failed");
    }
  }

  return (
    <div className="max-w-md mx-auto card mt-8">
      <h1 className="font-serif text-3xl">Create your account</h1>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <label className="block">
          <span className="text-lg">Name</span>
          <input aria-label="Name" className="mt-1 w-full text-lg border rounded-lg px-4 py-3" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-lg">Email</span>
          <input aria-label="Email" className="mt-1 w-full text-lg border rounded-lg px-4 py-3" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label className="block">
          <span className="text-lg">Password (8+ characters)</span>
          <input aria-label="Password" className="mt-1 w-full text-lg border rounded-lg px-4 py-3" value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={8} required />
        </label>
        {err && <p role="alert" className="text-red-800 text-lg">{err}</p>}
        <button className="btn-big w-full bg-accent text-white hover:bg-accentdark" type="submit">Create account</button>
      </form>
    </div>
  );
}
