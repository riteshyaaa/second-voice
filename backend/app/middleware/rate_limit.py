"""Brute-force guard for auth endpoints: per-IP fixed window.

Single-process in-memory scope: correct for the shipped single-node Docker
Compose deployment; a multi-replica setup would need a shared store (Redis)
and must not rely on this.
"""
import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import settings

_hits: dict[str, list[float]] = {}


def reset() -> None:
    _hits.clear()


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not request.url.path.startswith("/api/v1/auth"):
            return await call_next(request)
        limit = settings.RATE_LIMIT_PER_MINUTE
        if limit <= 0:
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = _hits.setdefault(ip, [])
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= limit:
            return JSONResponse(status_code=429, content={"detail": {
                "code": "RATE_LIMITED",
                "message": "Too many auth attempts; wait a minute and retry.",
                "retryable": True}})
        window.append(now)
        return await call_next(request)
