"""Multilingual core: detection, code-switch spans, script prefs, translation.

Detection is heuristic + provider hook. It NEVER auto-translates output:
translation only happens on explicit user request (TranslateIn).
Supports en / hi / hinglish / mr + extensible list from config.
"""
import re

from ..core.config import SUPPORTED_LANGUAGES

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_HINDI_COMMON = {
    "hai", "nahi", "nahin", "kya", "kaise", "main", "mein", "mera", "meri", "aap",
    "tum", "yeh", "yah", "woh", "aur", "lekin", "kyunki", "bahut", "thoda",
    "paani", "khana", "doctor", "dawai", "madad", "dhanyavad", "shukriya",
    "chahiye", "jana", "aana", "karna", "hoga", "tha", "thi", "hoon",
}
_MARATHI_COMMON = {
    "ahe", "nahi", "kay", "kasa", "kashi", "mala", "tula", "tumhala", "aamhi",
    "aani", "pan", "khup", "thoda", "pani", "jevan", "aushadh", "madat",
    "dhanyavad", "pahije", "jaych", "yaych", "karaych", "aaho", "aahe",
}
_EN_COMMON = {
    "the", "and", "please", "want", "need", "going", "doctor", "help",
    "thank", "sorry", "water", "food", "today", "tomorrow", "time",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z\u0900-\u097F]+", text.lower())


def detect_language(text: str) -> dict:
    """Return {language, confidence_note, code_switch, spans}."""
    if not text or not text.strip():
        return {"language": "en", "confidence_note": "empty input, defaulted", "code_switch": False, "spans": []}
    dev = len(_DEVANAGARI.findall(text))
    toks = _tokens(text)
    n = max(len(toks), 1)
    hi = sum(1 for t in toks if t in _HINDI_COMMON)
    mr = sum(1 for t in toks if t in _MARATHI_COMMON)
    en = sum(1 for t in toks if t in _EN_COMMON)
    dev_ratio = dev / max(len(text), 1)

    if dev_ratio > 0.15 and hi + mr == 0:
        # Devanagari but no lexicon hit → treat by script: default Hindi
        return {"language": "hi", "confidence_note": "devanagari-script", "code_switch": en > 0, "spans": []}
    if dev_ratio > 0.15 or hi > 0:
        if en >= 2 and hi >= 1:
            lang = "hinglish"
        elif mr > hi:
            lang = "mr"
        else:
            lang = "hi"
        return {
            "language": lang,
            "confidence_note": "lexicon+script heuristic",
            "code_switch": en > 0 and (hi > 0 or mr > 0),
            "spans": _code_switch_spans(text),
        }
    if mr > hi and mr > 0:
        return {"language": "mr", "confidence_note": "lexicon heuristic", "code_switch": en > 0, "spans": []}
    if hi > 0 and en > 0:
        return {"language": "hinglish", "confidence_note": "lexicon heuristic", "code_switch": True, "spans": _code_switch_spans(text)}
    if hi > 0:
        return {"language": "hi", "confidence_note": "lexicon heuristic", "code_switch": False, "spans": []}
    return {"language": "en", "confidence_note": "default", "code_switch": False, "spans": []}


def _code_switch_spans(text: str) -> list[dict]:
    spans: list[dict] = []
    for m in re.finditer(r"[A-Za-z\u0900-\u097F]+", text):
        tok = m.group(0)
        low = tok.lower()
        if _DEVANAGARI.search(tok) or low in _HINDI_COMMON or low in _MARATHI_COMMON:
            spans.append({"token": tok, "lang": "hi"})
        else:
            spans.append({"token": tok, "lang": "en"})
    # compress to runs
    runs: list[dict] = []
    for s in spans:
        if runs and runs[-1]["lang"] == s["lang"]:
            runs[-1]["tokens"].append(s["token"])
        else:
            runs.append({"lang": s["lang"], "tokens": [s["token"]]})
    return runs


def normalize(text: str, language: str) -> str:
    text = " ".join(text.split())
    return text


# Minimal explicit-translation phrasebook. Real deployment may call Spark for
# translation; this deterministic table keeps tests offline-safe and is
# returned labelled provider="phrasebook".
_PHRASEBOOK = {
    ("hi", "en"): {
        "मुझे मदद चाहिए": "I need help.",
        "मुझे पानी चाहिए": "I need water.",
        "धन्यवाद": "Thank you.",
        "कृपया रुकिए": "Please wait.",
        "मुझे डॉक्टर से मिलना है": "I need to see the doctor.",
    },
    ("en", "hi"): {
        "i need help.": "मुझे मदद चाहिए।",
        "thank you.": "धन्यवाद।",
        "please wait.": "कृपया रुकिए।",
        "i need water.": "मुझे पानी चाहिए।",
    },
}

_HINGLISH_TO_HI = {"mujhe": "मुझे", "madad": "मदद", "chahiye": "चाहिए", "paani": "पानी", "dhanyavad": "धन्यवाद", "shukriya": "शुक्रिया", "kya": "क्या", "hai": "है", "nahi": "नहीं"}
_HINGLISH_TO_EN = {"mujhe": "I", "madad": "help", "chahiye": "need", "paani": "water", "dhanyavad": "thank you", "shukriya": "thank you"}


def translate_explicit(text: str, target: str) -> dict:
    """Explicit translation only. Returns {text, provider, note}."""
    if target not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported target language: {target}")
    src = detect_language(text)["language"]
    table = _PHRASEBOOK.get((src, target), {})
    key = text.strip()
    if key in table:
        return {"text": table[key], "provider": "phrasebook", "note": "exact match"}
    low = key.lower().rstrip(".")
    for k, v in table.items():
        if k.lower().rstrip(".") == low:
            return {"text": v, "provider": "phrasebook", "note": "case-insensitive match"}
    if src == "hinglish" and target == "hi":
        out = " ".join(_HINGLISH_TO_HI.get(t.lower(), t) for t in key.split())
        return {"text": out, "provider": "phrasebook", "note": "token map"}
    if src == "hinglish" and target == "en":
        out = " ".join(_HINGLISH_TO_EN.get(t.lower(), t) for t in key.split())
        return {"text": out, "provider": "phrasebook", "note": "token map"}
    # Transparent: no silent MT — caller (Spark service) may upgrade when live.
    return {"text": text, "provider": "phrasebook", "note": f"no mapping {src}->{target}; original preserved"}
