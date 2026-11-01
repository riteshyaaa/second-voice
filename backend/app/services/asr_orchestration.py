"""Multi-engine ASR orchestration (Phase 2).

Flow: quality assessment → language/segmentation strategy (Phase 3 will
expand this) → primary ASR → CONDITIONAL secondary ASR → comparison →
evidence package.

Cost/latency rules (never call every engine every time):
- Secondary runs only when configured (SECOND_ASR_ENABLED + a registered,
  benchmarked provider) AND justified: explicit request, empty primary
  transcript, or usable/poor recording quality.
- Agreement is recorded, never treated as proof: both engines can share
  the same bias (verified live: short-Hindi English-default).
- Individual provider transcripts are always preserved; nothing is
  silently replaced. Provider + model versions go in the evidence package.
"""
from . import asr_providers
from .reconstruction_service import diff_words, violates_guards

# Quality issues that mean "nothing worth re-recognizing" — a second engine
# on silence or a 0.1 s clip wastes cost for zero information.
_UNUSABLE_QUALITY = {"mostly_silence", "too_short"}


def should_run_secondary(primary_text: str, quality: dict | None, force: bool = False) -> tuple[bool, str]:
    """Decide + explain. Pure function (offline-testable)."""
    ok, detail = asr_providers.second_available()
    if not ok:
        return False, f"single-engine: {detail}"
    if force:
        return True, "explicit-request"
    if not (primary_text or "").strip():
        return False if _quality_says_unusable(quality) else True, \
            "audio-unusable" if _quality_says_unusable(quality) else "primary-empty"
    issues = set((quality or {}).get("issues", []))
    if issues & _UNUSABLE_QUALITY:
        return False, "audio-unusable"
    if issues:
        return True, f"quality-{sorted(issues)[0]}"
    return False, "no-trigger"


def _quality_says_unusable(quality: dict | None) -> bool:
    return bool(set((quality or {}).get("issues", [])) & _UNUSABLE_QUALITY)


def compare_transcripts(primary: dict, secondary: dict | None) -> dict:
    """Pure comparison of two provider result dicts. No network, no models."""
    p_text = (primary.get("text") or "").strip()
    if secondary is None:
        return {"verdict": "single",
                "note": "One engine ran; nothing to agree or disagree with.",
                "primary_empty": not p_text, "secondary_empty": None,
                "language_match": None, "word_diffs": [],
                "meaning_divergence": violates_guards(p_text, p_text)}
    s_text = (secondary.get("text") or "").strip()
    out = {
        "primary_empty": not p_text,
        "secondary_empty": not s_text,
        "language_match": (primary.get("language") == secondary.get("language")),
        "word_diffs": [],
        "meaning_divergence": violates_guards(p_text, s_text),
    }
    if not p_text and not s_text:
        out.update(verdict="both_empty",
                   note="Both engines returned nothing — treat as abstention, prompt re-record, do not reconstruct.")
    elif " ".join(p_text.split()).lower() == " ".join(s_text.split()).lower():
        out.update(verdict="agree",
                   note="Same words from both engines. Recorded as agreement, not proof — shared bias stays possible.")
    else:
        out.update(verdict="disagree", word_diffs=diff_words(p_text, s_text),
                   note="Engines differ; both transcripts preserved for the evidence package and user review.")
    return out


def evidence_package(primary: dict, secondary: dict | None, quality: dict | None, trigger: str) -> dict:
    """Everything Phase 3+ needs, in one place. model_confidence is
    explicitly None: no provider exposes it, and the key exists so nobody
    invents it later."""
    providers = [{"name": primary.get("provider"), "model_version": primary.get("model_version"),
                  "live": not primary.get("fallback", False)}]
    if secondary is not None:
        providers.append({"name": secondary.get("provider"), "model_version": secondary.get("model_version"),
                          "live": not secondary.get("fallback", False)})
    return {
        "audio_quality": quality,
        "providers": providers,
        "secondary_trigger": trigger,
        "model_confidence": None,
        "reliability_note": ("Transcript(s) are unverified ASR interpretations with no word-level "
                             "confidence; the original audio is the primary evidence."),
    }


async def orchestrate(data: bytes, mime: str, language_hint: str = "auto",
                      keywords: list[str] | None = None, quality: dict | None = None,
                      force_secondary: bool = False) -> dict:
    """Run primary (+ conditional secondary) and return the full result.

    {"primary", "secondary" | None, "comparison", "evidence_package"}.
    meta_asr_service.transcribe() returns just ["primary"] — the exact
    pre-Phase-2 shape — so the default path is behavior-identical.
    """
    primary = await asr_providers.primary_provider().transcribe(data, mime, language_hint, keywords)
    run, trigger = should_run_secondary(primary.get("text", ""), quality, force_secondary)
    secondary = None
    if run:
        ok, name = asr_providers.second_available()
        if ok:  # re-checked: config is the only gate that can add engines
            secondary = await asr_providers.get_provider(name).transcribe(data, mime, language_hint, keywords)
            trigger = f"ran-{trigger}"
    return {"primary": primary, "secondary": secondary,
            "comparison": compare_transcripts(primary, secondary),
            "evidence_package": evidence_package(primary, secondary, quality, trigger)}
