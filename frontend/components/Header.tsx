"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { loggedIn, setToken } from "@/lib/api";

const PUBLIC_NAV = [
  { label: "Overview", href: "/", path: "overview" },
  { label: "Interactive Demo", href: "/#interactive-demo", path: "interactive-demo" },
  { label: "How It Works", href: "/#how-it-works", path: "how-it-works" },
];

const PRIVATE_NAV = [
  { label: "Workshop", href: "/communicate", path: "workspace" },
  { label: "Settings", href: "/settings", path: "settings" },
];

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const authed = loggedIn();
  const NAV = authed ? [...PUBLIC_NAV, ...PRIVATE_NAV] : PUBLIC_NAV;
  const active = pathname === "/" ? "overview" : pathname.startsWith("/communicate") ? "workspace" : pathname.startsWith("/settings") || pathname.startsWith("/onboarding") ? "settings" : "";

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-surface/85 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <div className="h-20 w-full px-margin flex items-center justify-between gap-space-lg">
        <Link href={authed ? "/communicate" : "/"} className="flex items-center gap-space-md">
          <span className="w-8 h-8 rounded-lg bg-primary text-on-primary flex items-center justify-center font-bold">S</span>
          <span className="font-headline-sm text-headline-sm font-semibold tracking-tight text-on-surface">Second Voice</span>
        </Link>
        <nav className="hidden xl:flex items-center gap-space-sm" aria-label="Main">
          {NAV.map((n) => (
            <Link
              key={n.path}
              data-path={n.path}
              aria-current={active === n.path ? "page" : undefined}
              href={n.href}
              className={
                active === n.path
                  ? "px-space-md py-space-sm transition-colors bg-surface-container text-primary font-semibold rounded-lg"
                  : "px-space-md py-space-sm text-on-surface-variant font-label-md text-label-md hover:bg-surface-container hover:text-on-surface transition-colors rounded-lg"
              }
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-space-md">
          <div className="flex items-center gap-space-xs bg-surface-container-high px-space-sm py-space-xs rounded-full">
            <button aria-label="Adjust Text Size" type="button" onClick={() => {
              const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--font-scale") || "1") || 1;
              document.documentElement.style.setProperty("--font-scale", String(Math.min(1.6, v + 0.1)));
            }} className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface">
              <span className="material-symbols-outlined text-[18px]">format_size</span>
            </button>
            <button aria-label="Toggle High Contrast" type="button" onClick={() => document.documentElement.classList.toggle("high-contrast")} className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface">
              <span className="material-symbols-outlined text-[18px]">contrast</span>
            </button>
            <button aria-label="Toggle Speech Audio" type="button" onClick={() => { try { speechSynthesis.cancel(); } catch {} }} className="w-9 h-9 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface">
              <span className="material-symbols-outlined text-[18px]">volume_up</span>
            </button>
          </div>
          {authed ? (
            <button onClick={() => { setToken(null); router.push("/"); }} className="text-label-md font-label-md text-on-surface-variant hover:text-on-surface">Log out</button>
          ) : (
            <Link href="/login" className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center text-on-surface-variant" aria-label="Profile">
              <span className="material-symbols-outlined text-[18px]">person</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
