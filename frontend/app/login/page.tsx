"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, setToken } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("demo@secondvoice.app");
  const [password, setPassword] = useState("demo1234");
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = (await api.login(email, password)) as { access_token: string };
      setToken(r.access_token);
      router.push("/communicate");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Login failed");
    }
  }

  return (
    <div className="max-w-md mx-auto card mt-8">
      <h1 className="font-serif text-3xl">Log in</h1>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <label className="block">
          <span className="text-lg">Email</span>
          <input aria-label="Email" className="mt-1 w-full text-lg border rounded-lg px-4 py-3" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label className="block">
          <span className="text-lg">Password</span>
          <input aria-label="Password" className="mt-1 w-full text-lg border rounded-lg px-4 py-3" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        </label>
        {err && <p role="alert" className="text-red-800 text-lg">{err}</p>}
        <button className="btn-big w-full bg-accent text-white hover:bg-accentdark" type="submit">Log in</button>
      </form>
      <p className="mt-4 text-lg">
        New here? <Link className="underline" href="/register">Create an account</Link>
      </p>
    </div>
  );
}
