import Link from "next/link";

export default function Footer() {
  return (
    <footer className="w-full bg-surface-container-lowest py-space-xl">
      <div className="w-full px-margin flex flex-col md:flex-row items-start justify-between gap-gutter max-w-7xl mx-auto">
        <div className="max-w-md">
          <div className="flex items-center gap-space-sm mb-space-sm">
            <span className="font-headline-sm text-headline-sm text-primary">Second Voice</span>
          </div>
          <p className="font-body-md text-body-md text-on-surface mb-space-sm font-medium">Your voice. Your meaning. Your choice.</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">Adaptive voice agency and assistive motor-speech translation platform designed for natural human resonance.</p>
        </div>
        <div className="flex flex-wrap gap-margin">
          <div className="flex flex-col gap-space-sm">
            <span className="font-label-md text-label-md text-on-surface font-semibold uppercase tracking-wider">Navigation</span>
            <Link data-path="overview" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/">Overview</Link>
            <Link data-path="interactive-demo" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/#interactive-demo">Interactive Demo</Link>
            <Link data-path="how-it-works" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/#how-it-works">How It Works</Link>
            <Link data-path="workspace" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/communicate">Workshop</Link>
          </div>
          <div className="flex flex-col gap-space-sm">
            <span className="font-label-md text-label-md text-on-surface font-semibold uppercase tracking-wider">Accessibility</span>
            <Link data-path="accessibility-statement" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/settings">Accessibility Statement</Link>
            <Link data-path="multilingual" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/#interactive-demo">Language Packs</Link>
            <Link data-path="settings" className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface" href="/settings">Calibration &amp; Dwell</Link>
          </div>
        </div>
      </div>
      <div className="w-full px-margin mt-space-lg pt-space-lg flex flex-col sm:flex-row items-center justify-between gap-space-md text-on-surface-variant font-label-sm text-label-sm max-w-7xl mx-auto">
        <p>© 2025 Second Voice. Dignified assistive intelligence.</p>
        <span className="inline-flex items-center gap-space-xs text-primary">
          <span className="material-symbols-outlined text-[16px]">check_circle</span>WCAG 2.2 AAA Compliant
        </span>
      </div>
    </footer>
  );
}
