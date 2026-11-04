"""Evidence-first reconstruction engine (the product's core guarantee).

Evidence hierarchy (never equally reliable):
  1. audio     — the original recording; primary evidence (replayable, stored
                 with consent). Only the user heard it directly.
  2. transcript— the ASR system's IMPERFECT INTERPRETATION of the audio
                 (verified live: Hindi पानी misheard as "Bani", छियालीस as
                 Korean). Never ground truth; suspicious readings stay suspect.
  3. personal  — user-approved vocabulary spellings
  4. contextual— conversation history / LLM fluency (weakest; never overrides)
  5. authority — the user's confirm/edit/reject (final, absolute)

Hard rules enforced on EVERY suggestion, including Meta Spark output:
- never drop/flip negation; never change numbers/quantities; never swap a
  name unless the approved vocabulary maps it; never turn uncertain speech
  into a definitive new claim; abstain when too uncertain.
"""
import difflib
import re

from . import muse_spark_service
from ..core.config import settings
from ..core.providers import ProviderStatus, meta_available

NEGATION = {"no", "not", "don't", "dont", "doesn't", "doesnt", "didn't", "didnt", "won't", "wont",
            "can't", "cant", "never", "n't", "nahi", "nahin", "नहीं", "नही", "मत", "नको", "नाही"}
HEDGES = {"maybe", "perhaps", "possibly", "might", "could be", "not sure", "unclear"}
NUM_RE = re.compile(r"\d+")
# Phase 7 semantic sets (deterministic, curated — not inferred).
MODALS = {"can", "could", "should", "would", "must", "might", "shall", "may",
          "सकता", "सकते", "सकती", "चाहिए", "पाहिजे"}
CONDITIONALS = {"if", "unless", "whether", "अगर", "यदि", "जर"}
DATE_RE = re.compile(r"\b\d{1,2}[:/.\-]\d{1,2}([:/.\-]\d{2,4})?\b|\b\d+\s?(am|pm)\b", re.I)
MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december",
          "जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
          "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"}
UNITS = {"mg", "ml", "kg", "km", "cm", "mm", "tablet", "tablets", "pill", "pills",
         "minute", "minutes", "hour", "hours", "day", "days", "week", "weeks",
         "गोली", "गोलियां", "बूंद", "किलो", "मिनट", "घंटे", "घंटा", "दिन", "रुपये", "पैसे"}
MEDICAL = {"doctor", "hospital", "emergency", "ambulance", "pain", "medicine", "pharmacy",
           "help", "allergy", "diabetes", "fever", "injury", "bleeding",
           "डॉक्टर", "अस्पताल", "मदद", "दर्द", "दवा", "दवाई", "बुखार", "चोट",
           "आपातकाल", "doctor", "dawai", "dard", "madad", "hospital"}

# tiny grammar fixes that cannot change meaning (articles/copula/gerund)
_FIXES = [
    (re.compile(r"\bi want meet\b", re.I), "I want to meet"),
    (re.compile(r"\bi want go\b", re.I), "I want to go"),
    (re.compile(r"\bi need help\b", re.I), "I need help."),
    (re.compile(r"\bme go\b", re.I), "I go"),
]


def _negation_set(text: str) -> set[str]:
    toks = set(re.findall(r"[A-Za-z']+|नहीं|नही|मत|नको|नाही", text.lower()))
    out = set()
    for t in toks:
        if t in NEGATION or t.endswith("n't"):
            out.add(t)
    return out


def _numbers(text: str) -> list[str]:
    return NUM_RE.findall(text)


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z']+|[\u0900-\u097F]+", (text or "").lower()))


def _proper_nouns(text: str) -> set[str]:
    """Latin-script capitalized words past sentence start (Devanagari has
    no case — uncovered there, documented). First token skipped: sentence
    position capitalizes ordinary words."""
    toks = re.findall(r"[A-Za-z']+", text or "")
    return {t for t in toks[1:] if t[:1].isupper()}


def _dates(text: str) -> list[str]:
    # finditer group(0): full matches — findall would return only the
    # captured subgroups ("10:30" vs "11:30" would both read ":30").
    found = sorted(m.group(0).lower() for m in DATE_RE.finditer(text or ""))
    months = sorted(_word_set(text) & MONTHS)
    return found + months


GUARD_CATEGORIES = ("negation", "number", "name", "datetime", "modal",
                      "conditional", "unit", "medical")


def _guard_checks(original: str, proposed: str,
                  approved_swaps: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Single source of truth: (category, message) violations. Messages are
    stable API (explanations quote them); guard_scores() reads categories.

    approved_swaps ({variant-lower -> canonical}, user-approved vocabulary)
    exempts name pairs the user explicitly mapped: "dropped without
    approved mapping" does not fire when the mapping exists. Omitted (None)
    means no exemptions — the historical strict behavior.
    """
    found: list[tuple[str, str]] = []
    if _negation_set(original) != _negation_set(proposed):
        found.append(("negation", "negation changed — intent would reverse"))
    if _numbers(original) != _numbers(proposed):
        found.append(("number", "number/quantity changed without evidence"))
    o_q = original.strip().endswith("?")
    p_q = proposed.strip().endswith("?")
    if o_q != p_q and ("?" in original) != ("?" in proposed):
        # request-vs-statement flip only matters if punctuation shows it
        pass
    if re.search(r"\bnot\b", original, re.I) and not re.search(r"\bnot\b|\bn't\b|never|no\b", proposed, re.I):
        if "negation changed" not in " ".join(m for _, m in found):
            found.append(("negation", "negation dropped"))
    # Phase 7 semantic preservation (deterministic layer)
    o_names, p_names = _proper_nouns(original), _proper_nouns(proposed)
    p_lower = {p.lower() for p in p_names}
    dropped_names = o_names - p_names
    if approved_swaps:
        dropped_names = {n for n in dropped_names
                         if not (n.lower() in approved_swaps
                                 and str(approved_swaps[n.lower()]).lower() in p_lower)}
    if dropped_names:
        found.append(("name", f"name dropped without approved mapping: {sorted(dropped_names)[0]}"))
    o_dates, p_dates = _dates(original), _dates(proposed)
    if o_dates != p_dates:
        found.append(("datetime", "date/time changed without evidence"))
    o_w, p_w = _word_set(original), _word_set(proposed)
    if (o_w & MODALS) != (p_w & MODALS):
        found.append(("modal", "modal verb changed — ability/permission intent at stake"))
    if bool(o_w & CONDITIONALS) != bool(p_w & CONDITIONALS):
        found.append(("conditional", "conditional changed — hypothetical turned definite or reverse"))
    o_units = sorted(w for w in o_w & UNITS)
    p_units = sorted(w for w in p_w & UNITS)
    if o_units != p_units:
        found.append(("unit", "quantity unit changed without evidence"))
    o_med = o_w & {m.lower() for m in MEDICAL}
    p_med = p_w & {m.lower() for m in MEDICAL}
    if o_med and not p_med:
        found.append(("medical", "medical/emergency term dropped — never remove calls for help"))
    return found


def violates_guards(original: str, proposed: str,
                    approved_swaps: dict[str, str] | None = None) -> list[str]:
    """Return list of violated meaning-preservation rules (empty = safe)."""
    return [m for _, m in _guard_checks(original, proposed, approved_swaps)]


def guard_scores(original: str, proposed: str,
                 approved_swaps: dict[str, str] | None = None) -> dict[str, bool]:
    """Phase 11: per-category preservation (True = preserved)."""
    failed = {c for c, _ in _guard_checks(original, proposed, approved_swaps)}
    return {c: (c not in failed) for c in GUARD_CATEGORIES}


def risk_floor(original: str) -> str:
    """Minimum meaning risk from the original alone: medical/emergency
    content always deserves care, even when the transcript looks clean."""
    if _word_set(original) & {m.lower() for m in MEDICAL}:
        return "medium"
    return "low"


def escalate(out: dict, indicators: list[dict]) -> dict:
    """Uncertainty-gated risk: risk-severity observables lift an
    under-confident 'low', and meaning divergence forces clarification.
    Never lowers anything — abstentions pass through untouched."""
    if out.get("abstained"):
        return out
    sevs = {i.get("severity") for i in indicators or []}
    kinds = {i.get("kind") for i in indicators or []}
    out = dict(out)
    if "risk" in sevs and out.get("meaning_risk") == "low":
        out["meaning_risk"] = "medium"
        out["explanation"] = (out.get("explanation", "") + " Risk raised: recording or recognition evidence is weak.").strip()
    if "meaning_divergence" in kinds and not out.get("needs_clarification"):
        out["needs_clarification"] = True
        out["clarification_question"] = out.get("clarification_question") or "Two readings differ in meaning — which did you intend?"
        if out.get("meaning_risk") == "low":
            out["meaning_risk"] = "medium"
    floor = risk_floor(out.get("original_text", ""))
    order = {"low": 0, "medium": 1, "high": 2}
    if order.get(floor, 0) > order.get(out.get("meaning_risk", "low"), 0):
        out["meaning_risk"] = floor
    return out


def rules_only_suggestion(original: str, vocab_map: dict[str, str]) -> dict:
    """Deterministic, meaning-safe suggestion. Always available offline."""
    text = " ".join(original.split())
    if not text:
        return _out(original, "", "Empty transcript — nothing to reconstruct.", [], [], True, "What would you like to say?", True, "high")
    proposed = text
    changed: list[dict] = []
    # 1. approved vocabulary spellings (personal evidence — allowed to swap)
    for wrong, right in vocab_map.items():
        if wrong.lower() in proposed.lower() and wrong.lower() != right.lower():
            proposed = re.sub(re.escape(wrong), right, proposed, flags=re.I)
            changed.append({"from": wrong, "to": right, "reason": "your approved spelling"})
    # 2. minimal safe grammar fixes
    for pat, rep in _FIXES:
        if pat.search(proposed):
            proposed = pat.sub(rep, proposed)
            changed.append({"from": pat.pattern, "to": rep, "reason": "small grammar fix, meaning unchanged"})
    if not proposed.endswith((".", "?", "!", "।")):
        proposed += "."
    problems = violates_guards(text, proposed, vocab_map)
    if problems:
        return _out(text, text, "Kept your exact words — auto-fix would risk changing meaning: " + "; ".join(problems),
                    [], [text], True, "Did you mean this exactly as written?", True, "high")
    if len(text.split()) <= 2:
        return _out(text, proposed, "Very short input — kept as-is; add words if something is missing.",
                    changed, [proposed], True, "Could you add a word about what you need?", False, "medium")
    explanation = "Small cleanup only; your words and meaning are unchanged." if changed else "Transcript looks clear — no changes suggested."
    return _out(text, proposed, explanation, changed, [], False, "", False, "low")


def _out(original, proposed, explanation, changed, alternatives, needs_q, question, abstained, risk,
         evidence_for=None, evidence_missing=None, uncertainty_reasons=None) -> dict:
    return {
        "original_text": original, "proposed_text": proposed, "explanation": explanation,
        "changed_words": changed, "alternatives": alternatives,
        "needs_clarification": needs_q, "clarification_question": question,
        "abstained": abstained, "meaning_risk": risk,
        "evidence_for": evidence_for or [],  # Phase 7: what supports each change
        "evidence_missing": evidence_missing or [],  # Phase 7: what could not be verified
        "uncertainty_reasons": uncertainty_reasons or [],  # Phase 7: echoed observables
    }


def diff_words(original: str, proposed: str) -> list[dict]:
    sm = difflib.SequenceMatcher(None, original.split(), proposed.split())
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            out.append({"from": " ".join(original.split()[i1:i2]), "to": " ".join(proposed.split()[j1:j2]), "reason": tag})
    return out


async def suggest(transcript: str, vocab_map: dict[str, str], history: list[str],
                  language: str, user_request: str, reliability: str = "",
                  context: dict | None = None) -> tuple[dict, ProviderStatus]:
    """Rules first, then Spark; guards constrain Spark output too.

    Phase 6: when retrieval `context` is provided, Spark gets the scored
    subset (spark_vocabulary/history/pattern_hints) instead of the full
    dumps — deterministic rules still see the full approved map.
    """
    base = rules_only_suggestion(transcript, vocab_map)
    spark_vocab = (context or {}).get("spark_vocabulary", list(vocab_map.values()))
    spark_hist = (context or {}).get("history", history)
    hints = (context or {}).get("pattern_hints", [])
    used = (context or {}).get("context_used", [])
    indicators = (context or {}).get("uncertainty", [])
    secondary_text = (context or {}).get("secondary_text")
    spans = (context or {}).get("language_spans", [])
    if not meta_available(settings.META_API_KEY):
        out = dict(base)
        out.update(provider="dev-fallback", model_version="rules-v1.2")
        if used:
            out["context_used"] = used
        out["candidates"] = label_candidates(transcript, vocab_map, out, secondary_text)
        out = escalate(out, indicators)
        return out, ProviderStatus("dev-fallback", "rules-v1.2", False, "META_API_KEY not set; deterministic rules only")
    reliability = reliability or "Transcript is an unverified ASR interpretation (no confidence scores); audio is primary."
    try:
        spark, status = await muse_spark_service.reconstruct(
            transcript, f"ASR interpretation (imperfect): {transcript!r}", spark_vocab, spark_hist,
            language, user_request, reliability, pattern_hints=hints,
            secondary_transcript=secondary_text, uncertainty_indicators=indicators,
            language_spans=spans)
    except Exception as exc:  # transport or malformed → labelled rules fallback
        out = dict(base)
        out.update(provider="dev-fallback", model_version="rules-v1.2")
        out["explanation"] += f" (AI unavailable: {exc}. Showing safe rules-only suggestion.)"
        out["candidates"] = label_candidates(transcript, vocab_map, out, secondary_text)
        return out, ProviderStatus("dev-fallback", "rules-v1.2", False, str(exc)[:200])
    problems = violates_guards(transcript, spark.proposed_text or transcript, vocab_map)
    if problems or not (spark.proposed_text or "").strip():
        # REJECT the model output — return abstention, keep transcript.
        out = _out(transcript, transcript,
                   "The AI suggestion was rejected because it could change your meaning: " + "; ".join(problems or ["empty output"]),
                   [], [transcript], True, spark.clarification_question or "Could you say that once more, or type the key word?",
                   True, "high")
        out.update(provider=status.name, model_version=status.model_version)
        out["candidates"] = label_candidates(transcript, vocab_map, base, secondary_text,
                                             spark.proposed_text)
        return out, status
    merged_changed = (spark.changed_words or []) + [c for c in base["changed_words"] if c not in (spark.changed_words or [])]
    alts = list(dict.fromkeys((spark.alternatives or []) + base["alternatives"]))[:4]
    out = _out(transcript, spark.proposed_text.strip(), spark.explanation or base["explanation"],
               merged_changed or diff_words(transcript, spark.proposed_text.strip()),
               alts, spark.needs_clarification, spark.clarification_question, False, spark.meaning_risk,
               evidence_for=spark.evidence_for, evidence_missing=spark.evidence_missing,
               uncertainty_reasons=spark.uncertainty_reasons)
    out.update(provider=status.name, model_version=status.model_version)
    out["candidates"] = label_candidates(transcript, vocab_map, base, secondary_text,
                                         spark.proposed_text)
    if used:
        out["context_used"] = used
    return escalate(out, indicators), status


def label_candidates(transcript: str, vocab_map: dict[str, str], base_out: dict,
                     secondary_text: str | None = None,
                     spark_text: str | None = None) -> list[dict]:
    """Source-labelled candidates for one transcript. Pure.

    Sources: rules (deterministic layer), vocab (approved spellings only),
    alternative-asr (second engine reading), contextual (Spark proposal),
    acoustic (regions where engines disagree — flags, not proposals).
    Every text candidate carries its guard verdict; `usable` is False when
    guards fire, and the candidate is kept (labelled) rather than hidden.
    """
    t = " ".join((transcript or "").split())
    cands: list[dict] = []

    def _text(source: str, text: str, explanation: str) -> dict | None:
        text = " ".join(text.split())
        if not text or text == t:
            return None
        guards = violates_guards(t, text, vocab_map)
        cand = {"source": source, "kind": "text", "text": text,
                "explanation": explanation, "guards": guards,
                "usable": not guards}
        cands.append(cand)
        return cand

    base = base_out or {}
    if base.get("proposed_text"):
        made = _text("rules", base["proposed_text"],
                     base.get("explanation", "Deterministic rules layer."))
        if made is not None:
            made["usable"] = made["usable"] and not base.get("abstained", False)

    vocab_only = t
    for wrong, right in (vocab_map or {}).items():
        if wrong.lower() in vocab_only.lower() and wrong.lower() != right.lower():
            vocab_only = re.sub(re.escape(wrong), right, vocab_only, flags=re.I)
    if vocab_only != t:
        _text("vocab", vocab_only, "Your approved spellings applied, nothing else changed.")

    sec = " ".join((secondary_text or "").split())
    if sec and sec != t:
        _text("alternative-asr", sec,
              "What the second engine heard. Kept verbatim; usability is guard-checked.")

    spk = " ".join((spark_text or "").split())
    if spk and spk != t:
        _text("contextual", spk, "Context-aware proposal. Kept verbatim; usability is guard-checked.")

    if sec and sec != t:
        for chunk in diff_words(t, sec):
            if chunk.get("from"):
                cands.append({"source": "acoustic", "kind": "uncertain-span",
                              "span": chunk["from"], "reason": chunk.get("reason", "replace"),
                              "explanation": "The engines heard this region differently — "
                                             "the acoustics here are uncertain.",
                              "guards": [], "usable": True})
    return cands


def alternatives(transcript: str, vocab_map: dict[str, str], count: int = 3) -> list[str]:
    base = rules_only_suggestion(transcript, vocab_map)["proposed_text"]
    cands = [base, transcript.strip(), transcript.strip().rstrip(".") + ", please."]
    if "?" not in transcript:
        cands.append(transcript.strip().rstrip(".") + "?")
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:count]
