"use client";
import { useEffect, useRef } from "react";

type Props = {
  analyser: AnalyserNode | null;
  active: boolean;
  label: string;
  bars?: number;
};

/**
 * Live mic-level waveform (canvas bars from an AnalyserNode while recording,
 * calm static bars otherwise). Decorative — the text label carries meaning.
 * Honors prefers-reduced-motion by never animating.
 */
export default function Waveform({ analyser, active, label, bars = 48 }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let raf = 0;
    const data = analyser ? new Uint8Array(analyser.frequencyBinCount) : new Uint8Array(0);

    const draw = (levels: ArrayLike<number> | null) => {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      const bw = w / bars;
      for (let i = 0; i < bars; i++) {
        const v = levels ? (levels[Math.floor((i / bars) * levels.length)] ?? 0) / 255 : 0.06 + 0.05 * Math.abs(Math.sin(i * 0.7));
        const bh = Math.max(3, v * h * 0.92);
        const x = i * bw + bw * 0.22;
        ctx.fillStyle = active ? "#99efe3" : "#3e5a58";
        const y = (h - bh) / 2;
        const r = Math.min(bw * 0.28, 3);
        ctx.beginPath();
        ctx.roundRect(x, y, bw * 0.56, bh, r);
        ctx.fill();
      }
    };

    if (analyser && active && !reduced) {
      const tick = () => {
        analyser.getByteFrequencyData(data as Uint8Array);
        draw(data);
        raf = requestAnimationFrame(tick);
      };
      tick();
    } else {
      draw(analyser && active ? data : null);
    }
    return () => cancelAnimationFrame(raf);
  }, [analyser, active, bars]);

  return (
    <div className="w-full">
      <canvas
        ref={ref}
        width={600}
        height={96}
        className="w-full h-24 rounded-lg bg-surface-container-lowest p-2"
        aria-hidden
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}
