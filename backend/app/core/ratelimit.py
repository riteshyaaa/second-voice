"""Tiny in-memory sliding-window rate limiter (per user + route)."""
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)
LIMITS = {"/api/v1/transcription": (20, 60.0), "/api/v1/reconstruction": (30, 60.0), "/api/v1/speech/": (30, 60.0)}


def rate_limit(request: Request) -> None:
    path = request.url.path
    for prefix, (limit, window) in LIMITS.items():
        if path.startswith(prefix):
            key = f"{prefix}:{request.client.host if request.client else '?'}"
            now = time.time()
            bucket = [t for t in _hits[key] if now - t < window]
            _hits[key] = bucket
            if len(bucket) >= limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded, please wait and retry.")
            bucket.append(now)
            return
