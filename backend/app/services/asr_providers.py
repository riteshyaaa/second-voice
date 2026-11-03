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
        from .meta_http import MetaHTTPError, meta_post

        try:
            resp = await meta_post(url, label="asr", model=settings.META_ASR_MODEL, headers=headers,
                                   timeout_s=120.0,
                                   content={"files": files, "data": {"request": json.dumps(request_part)}})
        except MetaHTTPError as exc:
            status, text = exc.status, exc.text
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail={"code": "ASR_TRANSPORT", "message": str(exc), "retryable": True})
        else:
            status, text = resp.status_code, resp.text
        if status == 401:
            raise HTTPException(status_code=502, detail={"code": "ASR_UNAUTHORIZED", "message": "Meta API key rejected.", "retryable": False})
        if status == 429:
            raise HTTPException(status_code=502, detail={"code": "ASR_RATE_LIMIT", "message": "Meta ASR rate limited.", "retryable": True})
        if status >= 400:
            raise HTTPException(status_code=502, detail={"code": "ASR_ERROR", "message": text[:500], "retryable": True})
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


class LocalWhisperProvider(ASRProvider):
    """CLARIS P2: on-device Whisper via faster-whisper (CPU-first).

    Lazy: importing this module never imports faster-whisper and never
    downloads weights. The model downloads on first transcribe only.
    Languages map to Whisper codes; anything else (e.g. hinglish) falls
    back to auto-detect. confidence/timestamps stay None — faster-whisper
    log-probs are not calibrated confidences and are never presented as such.
    Vocabulary keywords become an initial prompt (a bias, not a constraint).
    """

    name = "local-whisper"

    def __init__(self, model_id: str):
        if not (model_id or "").strip():
            raise ValueError("LOCAL_ASR_MODEL not set — local Whisper unconfigured")
        self.model_id = model_id.strip()

    @staticmethod
    def _import():
        try:
            import faster_whisper  # type: ignore
        except ImportError as exc:
            raise RuntimeError("faster-whisper not installed") from exc
        return faster_whisper

    def supported_languages(self) -> list[str]:
        return ["auto", "en", "hi"]

    def supported_formats(self) -> list[str]:
        from .audio_service import ALLOWED_MIME

        return sorted(ALLOWED_MIME)

    async def health_check(self) -> dict:
        try:
            self._import()
        except RuntimeError as exc:
            return {"ok": True, "live": False, "detail": str(exc)}
        return {"ok": True, "live": True,
                "detail": f"model {self.model_id} (downloads on first transcribe, never at startup)"}

    def provider_metadata(self) -> dict:
        try:
            self._import()
            live: bool | str = True
        except RuntimeError as exc:
            live = str(exc)
        return {"name": self.name, "model_version": self.model_id, "live": live}

    async def transcribe(self, data: bytes, mime: str, language_hint: str = "auto",
                         keywords: list[str] | None = None) -> dict:
        import asyncio
        import io

        fw = self._import()
        from .audio_service import normalize_to_wav16k

        wav = normalize_to_wav16k(data, mime)
        language = {"auto": None, "en": "en", "hi": "hi"}.get(language_hint, None)
        prompt = " ".join(keywords[:20]) if keywords else None

        def _run():
            import array
            import wave

            import numpy as np

            model = fw.WhisperModel(self.model_id, device=settings.LOCAL_ASR_DEVICE,
                                    compute_type=settings.LOCAL_ASR_COMPUTE)
            # Pass a float32 ndarray directly: avoids the engine's container
            # decoder (PyAV version-sensitive) — input is always our own
            # normalized mono s16le 16 kHz WAV at this point.
            with wave.open(io.BytesIO(wav), "rb") as w:
                frames = w.readframes(w.getnframes())
            samples = array.array("h", frames)
            audio = np.array([s / 32768.0 for s in samples], dtype=np.float32)
            segments, info = model.transcribe(audio, language=language,
                                              initial_prompt=prompt, vad_filter=False)
            return " ".join(s.text.strip() for s in segments).strip(), info.language

        text, detected = await asyncio.to_thread(_run)
        return {
            "text": text,
            "language": detected or (None if language_hint == "auto" else language_hint) or "en",
            "provider": "local-whisper",
            "model_version": self.model_id,
            "confidence": None,
            "timestamps": None,
            "fallback": False,
        }


_LOCAL: dict[str, LocalWhisperProvider] = {}

_REGISTRY: dict[str, ASRProvider] = {"meta-asr": MetaASRProvider()}


def local_provider() -> LocalWhisperProvider:
    """Build (once) the configured local Whisper provider."""
    model_id = (settings.LOCAL_ASR_MODEL or "").strip()
    if not model_id:
        raise ValueError("LOCAL_ASR_MODEL not set — local Whisper unconfigured")
    if model_id not in _LOCAL:
        _LOCAL[model_id] = LocalWhisperProvider(model_id)
    return _LOCAL[model_id]


def get_provider(name: str) -> ASRProvider:
    if name == "local-whisper":
        return local_provider()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown ASR provider: {name}. Configured: {sorted(_REGISTRY) + ['local-whisper']}")


def primary_provider() -> ASRProvider:
    return _REGISTRY["meta-asr"]


def second_available() -> tuple[bool, str]:
    """Whether a benchmarked secondary engine is configured.

    local-whisper counts once P2 bench results exist (see
    docs/claris-phase-2-asr.md); unconfigured/uninstalled states explain
    themselves instead of silently falling back.
    """
    if not settings.SECOND_ASR_ENABLED:
        return False, "SECOND_ASR_ENABLED is false"
    name = (settings.SECOND_ASR_PROVIDER or "").strip()
    if not name:
        return False, "SECOND_ASR_PROVIDER not set"
    if name == "local-whisper":
        try:
            local_provider()._import()
        except (ValueError, RuntimeError) as exc:
            return False, str(exc)
        return True, name
    if name not in _REGISTRY:
        return False, f"provider {name!r} not registered (none benchmarked yet)"
    return True, name
