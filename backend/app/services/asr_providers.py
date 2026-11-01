"""ASR provider interface + registry (Phase 2).

Every recognizer sits behind ASRProvider so engines can be compared,
replaced, or added without touching the transcription flow. No behavior
change by default: MetaASRProvider holds the exact logic (and output
shape) previously in meta_asr_service, and orchestration runs Meta-only
unless a secondary engine is both configured AND justified.

A second engine must be benchmarked before adoption (see
docs/phase-2-asr-orchestration.md) — no engine is added here.
"""
import json
from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException

from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available


class ASRProvider(ABC):
    """Contract every speech recognizer must satisfy."""

    name: str = "unnamed"

    @abstractmethod
    async def transcribe(self, data: bytes, mime: str, language_hint: str = "auto",
                         keywords: list[str] | None = None) -> dict:
        """Return {text, language, provider, model_version, confidence,
        timestamps, fallback(, note)}. confidence/timestamps are None unless
        the provider truly exposes them — never invented."""

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Language hints this engine accepts (codes incl. 'auto')."""

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Upload MIME types accepted (pre-normalization)."""

    @abstractmethod
    async def health_check(self) -> dict:
        """Lightweight liveness: {ok, live, detail}. No audio sent."""

    @abstractmethod
    def provider_metadata(self) -> dict:
        """Stable identity for evidence/provenance records."""


class MetaASRProvider(ASRProvider):
    """Muse Voice Transcribe (verified live 2026-10-31).

    POST {META_BASE_URL}/asr/transcribe with multipart `request` (JSON:
    model, audioEncoding, language, keywords) + `audio` (mono s16le WAV).
    Without META_API_KEY → labelled dev-fallback (never Meta output).
    """

    name = "meta-asr"

    async def transcribe(self, data: bytes, mime: str, language_hint: str = "auto",
                         keywords: list[str] | None = None) -> dict:
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

    def supported_languages(self) -> list[str]:
        from ..core.config import SUPPORTED_LANGUAGES

        return ["auto", *SUPPORTED_LANGUAGES]

    def supported_formats(self) -> list[str]:
        from .audio_service import ALLOWED_MIME

        return sorted(ALLOWED_MIME)

    async def health_check(self) -> dict:
        if meta_available(settings.META_API_KEY):
            return {"ok": True, "live": True, "detail": f"key configured; model {settings.META_ASR_MODEL}"}
        return {"ok": True, "live": False, "detail": "META_API_KEY not set (dev-fallback)"}

    def provider_metadata(self) -> dict:
        return {"name": self.name, "model_version": settings.META_ASR_MODEL,
                "live": meta_available(settings.META_API_KEY)}


_REGISTRY: dict[str, ASRProvider] = {"meta-asr": MetaASRProvider()}


def get_provider(name: str) -> ASRProvider:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown ASR provider: {name}. Configured: {sorted(_REGISTRY)}")


def primary_provider() -> ASRProvider:
    return _REGISTRY["meta-asr"]


def second_available() -> tuple[bool, str]:
    """Whether a benchmarked secondary engine is configured (none yet)."""
    if not settings.SECOND_ASR_ENABLED:
        return False, "SECOND_ASR_ENABLED is false"
    name = (settings.SECOND_ASR_PROVIDER or "").strip()
    if not name:
        return False, "SECOND_ASR_PROVIDER not set"
    if name not in _REGISTRY:
        return False, f"provider {name!r} not registered (none benchmarked yet)"
    return True, name
