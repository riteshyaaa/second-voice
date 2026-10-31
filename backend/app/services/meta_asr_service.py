"""Muse Voice Transcribe client.

Real integration (verified live 2026-10-31): POST {META_BASE_URL}/asr/transcribe
with multipart parts `request` (JSON: model, audioEncoding, language) and
`audio` (mono s16le WAV at 16/24 kHz — uploads are normalized to that shape).
Without META_API_KEY → labelled dev-fallback (never presented as Meta output).
"""
import json

import httpx
from fastapi import HTTPException

from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available


async def transcribe(data: bytes, mime: str, language_hint: str = "auto", keywords: list[str] | None = None) -> dict:
    keywords = keywords or []
    if not meta_available(settings.META_API_KEY):
        return {
            "text": "",
            "language": "en" if language_hint in ("auto", "en") else language_hint,
            "provider": "dev-fallback",
            "model_version": "dev-fallback-1",
            "confidence": None,
            "timestamps": None,
            "note": "META_API_KEY not configured — record a transcript manually or set the key. Not a Meta response.",
            "fallback": True,
        }
    from .audio_service import normalize_to_wav16k

    try:
        wav = normalize_to_wav16k(data, mime)
    except Exception as exc:
        raise HTTPException(status_code=415, detail={"code": "ASR_DECODE", "message": f"Could not decode audio: {exc}", "retryable": False})
    url = settings.META_BASE_URL.rstrip("/") + "/asr/transcribe"
    headers = {"Authorization": f"Bearer {settings.META_API_KEY}"}
    request_part = {"model": settings.META_ASR_MODEL, "audioEncoding": "WAV"}
    if language_hint and language_hint != "auto":
        request_part["language"] = language_hint
    if keywords:
        request_part["keywords"] = keywords[:50]
    files = {"audio": ("audio.wav", wav, "audio/wav")}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, files=files, data={"request": json.dumps(request_part)})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"code": "ASR_TRANSPORT", "message": str(exc), "retryable": True})
    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail={"code": "ASR_UNAUTHORIZED", "message": "Meta API key rejected.", "retryable": False})
    if resp.status_code == 429:
        raise HTTPException(status_code=502, detail={"code": "ASR_RATE_LIMIT", "message": "Meta ASR rate limited.", "retryable": True})
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail={"code": "ASR_ERROR", "message": resp.text[:500], "retryable": True})
    body = resp.json()
    # Accept common shapes; never invent word-level confidence/timestamps.
    text = body.get("text") or body.get("transcript") or ""
    return {
        "text": text,
        "language": body.get("language") or (None if language_hint == "auto" else language_hint) or "en",
        "provider": "meta-asr",
        "model_version": settings.META_ASR_MODEL,
        "confidence": body.get("confidence"),
        "timestamps": body.get("words") or body.get("timestamps"),
        "fallback": False,
    }


def status() -> ProviderStatus:
    if meta_available(settings.META_API_KEY):
        return ProviderStatus("meta-asr", settings.META_ASR_MODEL, True, "live")
    return ProviderStatus("dev-fallback", "dev-fallback-1", False, "META_API_KEY not set")
