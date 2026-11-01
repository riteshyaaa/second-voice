"""Shared Meta HTTP transport: bounded retries + latency observability.

Retry policy: transport errors, 429 and 5xx are retried
(settings.META_RETRIES extra attempts, linear backoff). Other 4xx are
returned immediately — retrying them can never succeed and, for ASR, a
retry would double-charge audio that the server already rejected.
Every attempt is logged (label/model/attempt/duration/status) so latency
and cost (attempts x tokens) are auditable from logs; the Meta API returns
no cost figures, so none are invented.
"""
import asyncio
import time

import httpx

from ..core.config import settings
from ..core.logging import log

RETRYABLE_STATUS = {408, 429, *range(500, 600)}


class MetaHTTPError(Exception):
    def __init__(self, status: int, text: str):
        self.status = status
        self.text = text or ""
        super().__init__(f"Meta HTTP {status}: {self.text[:200]}")


async def meta_post(url: str, *, label: str, model: str, headers: dict,
                    timeout_s: float, content: dict) -> httpx.Response:
    """POST with retries. content is {"json": ...} or {"files": ..., "data": ...}.

    Raises MetaHTTPError for HTTP >= 400, httpx.HTTPError when retries are
    exhausted on transport failures.
    """
    tries = max(1, 1 + settings.META_RETRIES)
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for attempt in range(1, tries + 1):
            start = time.perf_counter()
            try:
                if "json" in content:
                    resp = await client.post(url, headers=headers, json=content["json"])
                else:
                    resp = await client.post(url, headers=headers,
                                             files=content.get("files"), data=content.get("data"))
            except httpx.HTTPError as exc:
                last = exc
                _observe(label, model, attempt, start, "transport", retrying=attempt < tries)
            else:
                retrying = resp.status_code in RETRYABLE_STATUS and attempt < tries
                _observe(label, model, attempt, start, resp.status_code, retrying=retrying)
                if not retrying:
                    if resp.status_code >= 400:
                        raise MetaHTTPError(resp.status_code, resp.text)
                    return resp
                last = MetaHTTPError(resp.status_code, resp.text)
            await asyncio.sleep(settings.META_RETRY_BACKOFF_S * attempt)
    assert last is not None
    raise last


def _observe(label: str, model: str, attempt: int, start: float, status, retrying: bool) -> None:
    log.info("meta_call label=%s model=%s attempt=%d duration_ms=%d status=%s retrying=%s",
             label, model, attempt, int((time.perf_counter() - start) * 1000), status, retrying)
