"use client";

/** Shimmer placeholder block for busy states. Static under reduced-motion (see globals.css). */
export default function Skeleton({ height = 140, label }: { height?: number; label?: string }) {
  return <div className="skeleton w-full" style={{ minHeight: height }} role="status" aria-label={label || "Loading"} />;
}
