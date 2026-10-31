"""Muse Wonder — routed advanced reasoning only (never on the hot path).

Router: Wonder is invoked only when reconstruction flags complex ambiguity
(needs_clarification + negation/number at stake or >=2 competing readings)
or the user explicitly taps 'Ask for clarification'.
"""
import json

import httpx

from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available
from . import prompts

NEGATION = {"no", "not", "don't", "dont", "doesn't", "doesnt", "won't", "wont", "never", "n't", "nahi", "nahin", "nahī", "नहीं", "नही", "मत"}


def should_route(transcript: str, suggestion: dict) -> bool:
    if not suggestion.get("needs_clarification"):
        return False
    toks = set(transcript.lower().split())
    if toks & {w.lower() for w in NEGATION}:
        return True
    if any(ch.isdigit() for ch in transcript):
        return True
    return len(suggestion.get("alternatives", [])) >= 2


async def resolve(transcript: str, candidates: list[str], context: list[str]) -> tuple[dict, ProviderStatus]:
    if not meta_available(settings.META_API_KEY):
        raise RuntimeError("META_API_KEY not configured")
    payload = {
        "model": settings.META_WONDER_MODEL,
        "instructions": prompts.CLARIFICATION_SYSTEM,
        "input": json.dumps({"transcript": transcript, "candidates": candidates[:4], "context": context[-5:]}),
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 4000,
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {settings.META_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(settings.META_BASE_URL.rstrip("/") + "/responses", headers=headers, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"Muse Wonder error {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    texts = []
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") in ("output_text", "text") and block.get("text"):
                texts.append(block["text"])
    content = "".join(texts)
    if not content.strip():
        raise RuntimeError("Muse Wonder returned no content")
    raw = json.loads(content)
    return raw, ProviderStatus("meta-wonder", settings.META_WONDER_MODEL, True, "live")
