"""Transparent uncertainty indicators (Phase 3).

Every indicator derives from OBSERVABLE evidence only: provider outputs,
their (dis)agreement, recording-quality metrics, transcript length. No
phoneme probabilities, no word-level confidence, no acoustic likelihoods
— no provider exposes them, so this module cannot report them. The
"no_confidence" indicator exists precisely to say that out loud.

An LLM must never manufacture acoustic evidence; these indicators are the
only uncertainty language the reconstruction layer may use.
"""
_RISK_AUDIO = {"mostly_silence", "too_short"}


def _ind(kind: str, severity: str, message: str) -> dict:
    return {"kind": kind, "severity": severity, "message": message}


def summarize(primary: dict, comparison: dict, quality: dict | None) -> list[dict]:
    """Pure function: provider result + comparison + quality → indicators."""
    out = [ _ind("no_confidence", "info",
                "No word-level confidence: no provider exposes it, so none is claimed.")]
    text = (primary.get("text") or "").strip()
    if primary.get("provider") == "manual-entry":
        return [_ind("manual_entry", "info", "Typed by the user — no speech recognition involved."),
                out[0]]
    if comparison.get("verdict") == "single":
        out.append(_ind("single_engine", "info",
                        "One engine transcribed this; there is no second opinion to check it against."))
    if not text:
        out.append(_ind("empty_output", "risk",
                        "ASR returned no words. Treat as abstention — re-record, do not reconstruct."))
        return out
    if len(text.split()) <= 2:
        out.append(_ind("very_short", "watch",
                        "Very short transcript — single words are the most misheard (verified live)."))
    verdict = comparison.get("verdict")
    if verdict == "disagree":
        out.append(_ind("disagreement", "watch",
                        "Two engines heard different words; both readings are preserved below."))
    elif verdict == "both_empty":
        out.append(_ind("empty_output", "risk",
                        "Both engines returned nothing — abstain and re-record."))
    for problem in comparison.get("meaning_divergence", []) or []:
        out.append(_ind("meaning_divergence", "risk",
                        f"Engine readings differ in meaning: {problem}."))
    if comparison.get("language_match") is False:
        out.append(_ind("language_mismatch", "watch",
                        "Engines disagree on language — check code-switching."))
    issues = set((quality or {}).get("issues", []))
    if issues & _RISK_AUDIO:
        out.append(_ind("poor_audio", "risk",
                        f"Recording quality is poor ({', '.join(sorted(issues))}); consider re-recording."))
    elif issues:
        out.append(_ind("audio_quality", "watch",
                        f"Recording has quality notes ({', '.join(sorted(issues))}); listen back if unsure."))
    return out


def pack_evidence(multi: dict, uncertainty: list[dict], manual: bool = False) -> dict:
    """Assemble the storable evidence package (Phase 7): orchestration
    output + uncertainty + the secondary transcript text when one ran."""
    secondary = (multi or {}).get("secondary")
    ev = dict((multi or {}).get("evidence_package", {}))
    ev.update(comparison_verdict=(multi or {}).get("comparison", {}).get("verdict"),
              uncertainty=uncertainty,
              secondary_text=(secondary or {}).get("text") if secondary else None)
    if manual:
        ev["secondary_trigger"] = "not-applicable-manual"
    return ev


def reliability_text(provider: str, model_version: str, language: str,
                     indicators: list[dict], confidence=None) -> str:
    """Evidence-derived reliability note for the reconstruction prompt."""
    conf = f"word-level confidence {confidence}" if confidence is not None else "no word-level confidence scores"
    base = (f"Source: {provider}/{model_version or 'unknown version'}; {conf}; "
            f"detected language {language}. The original audio is the primary evidence — "
            f"this transcript is an imperfect interpretation of it.")
    flags = [i["message"] for i in indicators if i["severity"] in ("watch", "risk")]
    if flags:
        base += " Uncertainty: " + " ".join(flags)
    return base[:1200]
