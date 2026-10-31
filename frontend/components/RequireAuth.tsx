"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { loggedIn } from "@/lib/api";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ok, setOk] = useState(false);

  useEffect(() => {
    if (!loggedIn()) router.replace("/login");
    else setOk(true);
  }, [router]);

  if (!ok) return null;
  return <>{children}</>;
}
