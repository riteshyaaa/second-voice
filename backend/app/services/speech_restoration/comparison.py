"""CLARIS Phase 5: evidence comparison across restoration stages.

Compares what each pipeline stage actually produced — original transcript,
normalized-derivative transcript, S2U units — and marks what does not
exist (enhanced audio, restored waveform) as unavailable with reasons.
Pure functions; the API layer fetches artifacts and runs ASR.

Units are codes, not words: they appear as evidence with statistics, never
as a transcript side in a word comparison. No restoration-quality claim is
made without a vocoder (Phase 3).
"""
from . import pipeline
from ..reconstruction_service import diff_words, violates_guards


def compare_texts(a_text: str, b_text: str, a_label: str, b_label: str) -> dict:
    """Word-level comparison of two transcript sides. Pure."""
    a = (a_text or "").strip()
    b = (b_text or "").strip()
    if not a and not b:
        return {"sides": [a_label, b_label], "verdict": "both_empty",
                "word_diffs": [], "meaning_divergence": [],
                "note": "Neither side produced text — treat as abstention, not agreement."}
    if not a or not b:
        return {"sides": [a_label, b_label], "verdict": "either_empty",
                "word_diffs": [], "meaning_divergence": violates_guards(a, b),
                "note": f"Only one side produced text; no agreement claim."}
    if " ".join(a.split()).lower() == " ".join(b.split()).lower():
        return {"sides": [a_label, b_label], "verdict": "agree",
                "word_diffs": [], "meaning_divergence": violates_guards(a, b),
                "note": "Same words from both sides. Recorded as agreement, not proof."}
    return {"sides": [a_label, b_label], "verdict": "disagree",
            "word_diffs": diff_words(a, b), "meaning_divergence": violates_guards(a, b),
            "note": "Sides differ; both transcripts preserved for user review."}


def build_report(*, original: dict | None, normalized: dict | None,
                 units: dict | None, stages: list[dict]) -> dict:
    """Assemble the side-by-side evidence report.

    Each artifact: {"artifact", "status": ready|failed|unavailable,
    "reason"?, ...payload}. Pairwise text comparisons only run where both
    sides are ready.
    """
    artifacts = []
    for label, payload in (("original", original), ("normalized", normalized)):
        if payload is None:
            artifacts.append({"artifact": label, "status": "unavailable",
                              "reason": "not produced in this comparison run"})
        elif payload.get("error"):
            artifacts.append({"artifact": label, "status": "failed",
                              "reason": payload["error"]})
        else:
            artifacts.append({"artifact": label, "status": "ready",
                              "text": payload.get("text", ""),
                              "language": payload.get("language"),
                              "provider": payload.get("provider"),
                              "model_version": payload.get("model_version")})
    if units is None:
        artifacts.append({"artifact": "s2u_units", "status": "unavailable",
                          "reason": "job has no units evidence"})
    else:
        artifacts.append({"artifact": "s2u_units", "status": "ready",
                          "n_units": len(units.get("units", [])),
                          "checkpoint": units.get("checkpoint"),
                          "beam": units.get("beam"),
                          "latency_s": units.get("latency_s"),
                          "first_units": list(units.get("units", []))[:12],
                          "note": "Discrete codes, not words — evidence only."})
    artifacts.append({"artifact": "enhanced_audio", "status": "unavailable",
                      "reason": pipeline.ENHANCE_UNAVAILABLE})
    artifacts.append({"artifact": "restored_waveform", "status": "unavailable",
                      "reason": pipeline.VOCODE_UNAVAILABLE})

    comparisons = []
    by = {a["artifact"]: a for a in artifacts}
    if by["original"]["status"] == "ready" and by["normalized"]["status"] == "ready":
        comparisons.append(compare_texts(by["original"]["text"], by["normalized"]["text"],
                                         "original", "normalized"))
    return {"artifacts": artifacts, "comparisons": comparisons,
            "note": ("Audio is the primary evidence; transcripts are imperfect "
                     "interpretations. Units are codes, not words. No waveform "
                     "means no restoration-quality claim.")}
