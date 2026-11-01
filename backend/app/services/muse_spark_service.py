"""Muse Spark — contextual reconstruction layer (structured JSON, validated).

Sends clearly separated inputs; returns structured suggestions. Malformed
model output → one retry → rules-only fallback (labelled, never faked).
"""
import json

from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available
from . import prompts


class SparkSuggestion(BaseModel):
    proposed_text: str = ""
    explanation: str = ""
    changed_words: list[dict] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""
    meaning_risk: str = "low"
    evidence_for: list[str] = Field(default_factory=list)  # Phase 7
    evidence_missing: list[str] = Field(default_factory=list)
    uncertainty_reasons: list[str] = Field(default_factory=list)


def _endpoint() -> str:
    # Responses API: Meta's recommended surface; lets us cap reasoning effort
    # so thinking tokens can't starve the structured answer (verified live).
    return settings.META_BASE_URL.rstrip("/") + "/responses"


def _payload(system: str, user_obj: dict, max_tokens: int = 2500, effort: str = "low") -> dict:
    return {
        "model": settings.META_SPARK_MODEL,
        "instructions": system,
        "input": json.dumps(user_obj, ensure_ascii=False),
        "reasoning": {"effort": effort},
        "max_output_tokens": max_tokens,
        "temperature": 0.2,
    }


def _extract_text(body: dict) -> str:
    parts: list[str] = []
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") in ("output_text", "text") and block.get("text"):
                parts.append(block["text"])
    return "".join(parts)


async def _call(payload: dict) -> dict:
    from .meta_http import MetaHTTPError, meta_post

    headers = {"Authorization": f"Bearer {settings.META_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = await meta_post(_endpoint(), label="spark", model=settings.META_SPARK_MODEL,
                               headers=headers, timeout_s=90.0, content={"json": payload})
    except MetaHTTPError as exc:
        if exc.status == 401:
            raise RuntimeError("Meta API key rejected (401).")
        if exc.status == 429:
            raise RuntimeError("Meta rate limit (429).")
        raise RuntimeError(f"Meta Spark error {exc.status}: {exc.text[:300]}")
    body = resp.json()
    if body.get("status") not in ("completed", None):
        raise ValueError(f"response {body.get('status')}: {(body.get('incomplete_details') or {})}")
    content = _extract_text(body)
    if not content.strip():
        raise ValueError("empty content (reasoning consumed the token budget?)")
    return json.loads(content)


async def reconstruct(
    transcript: str,
    asr_note: str,
    vocabulary: list[str],
    history: list[str],
    language: str,
    user_request: str,
    reliability: str = "",
    pattern_hints: list[str] | None = None,
    secondary_transcript: str | None = None,
    uncertainty_indicators: list[dict] | None = None,
    language_spans: list[dict] | None = None,
) -> tuple[SparkSuggestion, ProviderStatus]:
    """Returns (suggestion, status). Raises RuntimeError when Meta fails."""
    if not meta_available(settings.META_API_KEY):
        raise RuntimeError("META_API_KEY not configured")
    user_obj = {
        "asr_transcript": transcript,
        "asr_interpretation": asr_note,
        "transcript_reliability": reliability or "No word-level confidence available; treat as uncertain.",
        "approved_vocabulary": vocabulary[:50],
        "correction_patterns": (pattern_hints or [])[:5],
        "secondary_transcript": secondary_transcript,
        "uncertainty_indicators": uncertainty_indicators or [],
        "language_spans": language_spans or [],
        "communication_history": history[-5:],
        "language_preference": language,
        "user_request": user_request,
    }
    last_err: Exception | None = None
    for _ in range(2):  # one retry for malformed JSON
        try:
            raw = await _call(_payload(prompts.RECONSTRUCTION_SYSTEM, user_obj))
            return SparkSuggestion(**raw), ProviderStatus("meta-spark", settings.META_SPARK_MODEL, True, "live")
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_err = exc
    raise RuntimeError(f"Spark returned malformed output twice: {last_err}")


async def translate(text: str, target: str) -> tuple[str, ProviderStatus]:
    if not meta_available(settings.META_API_KEY):
        raise RuntimeError("META_API_KEY not configured")
    raw = await _call(_payload(prompts.TRANSLATION_SYSTEM, {"text": text, "target": target},
                                max_tokens=1500))
    return raw.get("translated_text", text), ProviderStatus("meta-spark", settings.META_SPARK_MODEL, True, "live")
