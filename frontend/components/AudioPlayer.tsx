"use client";
import { useState } from "react";

type Props = {
  src: string;
  label: string;
  kind: "original" | "confirmed";
  /** Lets the page keep its existing play/stop control of the element. */
  audioRef?: React.RefObject<HTMLAudioElement>;
  autoPlay?: boolean;
};

function fmt(sec: number): string {
  if (!isFinite(sec) || sec < 0) return "0:00";
  const t = Math.floor(sec);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

/**
 * Accessible audio player: native controls (full keyboard support) plus a
 * visible state pill, elapsed/total time, and progress. Labels distinguish
 * the user's original recording from generated confirmed speech.
 */
export default function AudioPlayer({ src, label, kind, audioRef, autoPlay }: Props) {
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);

  return (
    <figure className="w-full bg-surface-container-lowest rounded-lg p-space-sm flex flex-col gap-space-xs fade-in" aria-label={label}>
      <figcaption className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 font-label-sm text-label-sm text-on-surface-variant">
          <span
            aria-hidden
            className={`w-2 h-2 rounded-full ${playing ? "bg-primary animate-pulse" : "bg-outline-variant"}`}
          />
          <span className="font-bold text-on-surface">{kind === "original" ? "Your original recording" : "Confirmed speech"}</span>
        </span>
        <span className="font-label-sm text-label-sm text-on-surface-variant tabular-nums" aria-hidden>
          {fmt(t)} / {fmt(dur)}
        </span>
      </figcaption>
      <div
        aria-hidden
        className="h-1 rounded-full bg-surface-container-highest overflow-hidden"
      >
        <div
          className="h-full bg-primary transition-[width] duration-150"
          style={{ width: dur > 0 ? `${Math.min(100, (t / dur) * 100)}%` : "0%" }}
        />
      </div>
      <audio
        ref={audioRef}
        className="w-full"
        controls
        src={src}
        autoPlay={autoPlay}
        aria-label={label}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setT(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
      />
      <span className="sr-only" role="status">
        {playing ? "Playing" : t > 0 ? "Paused" : "Ready"}
      </span>
    </figure>
  );
}
