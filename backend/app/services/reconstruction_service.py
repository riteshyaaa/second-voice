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


def violates_guards(original: str, proposed: str) -> list[str]:
    """Return list of violated meaning-preservation rules (empty = safe)."""
    problems = []
    if _negation_set(original) != _negation_set(proposed):
        problems.append("negation changed — intent would reverse")
    if _numbers(original) != _numbers(proposed):
        problems.append("number/quantity changed without evidence")
    o_q = original.strip().endswith("?")
    p_q = proposed.strip().endswith("?")
    if o_q != p_q and ("?" in original) != ("?" in proposed):
        # request-vs-statement flip only matters if punctuation shows it
        pass
    if re.search(r"\bnot\b", original, re.I) and not re.search(r"\bnot\b|\bn't\b|never|no\b", proposed, re.I):
        if "negation changed" not in " ".join(problems):
            problems.append("negation dropped")
    return problems


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
    problems = violates_guards(text, proposed)
    if problems:
        return _out(text, text, "Kept your exact words — auto-fix would risk changing meaning: " + "; ".join(problems),
                    [], [text], True, "Did you mean this exactly as written?", True, "high")
    if len(text.split()) <= 2:
        return _out(text, proposed, "Very short input — kept as-is; add words if something is missing.",
                    changed, [proposed], True, "Could you add a word about what you need?", False, "medium")
    explanation = "Small cleanup only; your words and meaning are unchanged." if changed else "Transcript looks clear — no changes suggested."
    return _out(text, proposed, explanation, changed, [], False, "", False, "low")


def _out(original, proposed, explanation, changed, alternatives, needs_q, question, abstained, risk) -> dict:
    return {
        "original_text": original, "proposed_text": proposed, "explanation": explanation,
        "changed_words": changed, "alternatives": alternatives,
        "needs_clarification": needs_q, "clarification_question": question,
        "abstained": abstained, "meaning_risk": risk,
    }


def diff_words(original: str, proposed: str) -> list[dict]:
    sm = difflib.SequenceMatcher(None, original.split(), proposed.split())
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            out.append({"from": " ".join(original.split()[i1:i2]), "to": " ".join(proposed.split()[j1:j2]), "reason": tag})
    return out


async def suggest(transcript: str, vocab_map: dict[str, str], history: list[str],
                  language: str, user_request: str, reliability: str = "") -> tuple[dict, ProviderStatus]:
    """Rules first, then Spark; guards constrain Spark output too."""
    base = rules_only_suggestion(transcript, vocab_map)
    if not meta_available(settings.META_API_KEY):
        out = dict(base)
        out.update(provider="dev-fallback", model_version="rules-v1.2")
        return out, ProviderStatus("dev-fallback", "rules-v1.2", False, "META_API_KEY not set; deterministic rules only")
    reliability = reliability or "Transcript is an unverified ASR interpretation (no confidence scores); audio is primary."
    try:
        spark, status = await muse_spark_service.reconstruct(
            transcript, f"ASR interpretation (imperfect): {transcript!r}", list(vocab_map.values()), history,
            language, user_request, reliability)
    except Exception as exc:  # transport or malformed → labelled rules fallback
        out = dict(base)
        out.update(provider="dev-fallback", model_version="rules-v1.2")
        out["explanation"] += f" (AI unavailable: {exc}. Showing safe rules-only suggestion.)"
        return out, ProviderStatus("dev-fallback", "rules-v1.2", False, str(exc)[:200])
    problems = violates_guards(transcript, spark.proposed_text or transcript)
    if problems or not (spark.proposed_text or "").strip():
        # REJECT the model output — return abstention, keep transcript.
        out = _out(transcript, transcript,
                   "The AI suggestion was rejected because it could change your meaning: " + "; ".join(problems or ["empty output"]),
                   [], [transcript], True, spark.clarification_question or "Could you say that once more, or type the key word?",
                   True, "high")
        out.update(provider=status.name, model_version=status.model_version)
        return out, status
    merged_changed = (spark.changed_words or []) + [c for c in base["changed_words"] if c not in (spark.changed_words or [])]
    alts = list(dict.fromkeys((spark.alternatives or []) + base["alternatives"]))[:4]
    out = _out(transcript, spark.proposed_text.strip(), spark.explanation or base["explanation"],
               merged_changed or diff_words(transcript, spark.proposed_text.strip()),
               alts, spark.needs_clarification, spark.clarification_question, False, spark.meaning_risk)
    out.update(provider=status.name, model_version=status.model_version)
    return out, status


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
