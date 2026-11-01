"""Meta ASR entry point — Phase 2 compat facade.

Behavior is unchanged: transcribe() returns the exact pre-Phase-2 primary
dict. The engine itself lives in services/asr_providers.py (MetaASRProvider);
multi-engine orchestration lives in services/asr_orchestration.py.
"""
from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available
from . import asr_orchestration


async def transcribe(data: bytes, mime: str, language_hint: str = "auto", keywords: list[str] | None = None) -> dict:
    """Primary transcript only — identical shape to pre-Phase-2."""
    out = await asr_orchestration.orchestrate(data, mime, language_hint, keywords)
    return out["primary"]


async def transcribe_multi(data: bytes, mime: str, language_hint: str = "auto",
                           keywords: list[str] | None = None, quality: dict | None = None,
                           force_secondary: bool = False) -> dict:
    """Full orchestration: primary + conditional secondary + comparison."""
    return await asr_orchestration.orchestrate(data, mime, language_hint, keywords, quality, force_secondary)


def status() -> ProviderStatus:
    if meta_available(settings.META_API_KEY):
        return ProviderStatus("meta-asr", settings.META_ASR_MODEL, True, "live")
    return ProviderStatus("dev-fallback", "dev-fallback-1", False, "META_API_KEY not set")
