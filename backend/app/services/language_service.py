"""Multilingual core: detection, code-switch spans, script prefs, translation.

Detection is heuristic + provider hook. It NEVER auto-translates output:
translation only happens on explicit user request (TranslateIn).
Supports en / hi / hinglish + extensible list from config.
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
# Devanagari lexicon for Hindi (Marathi support removed; Devanagari
# without a Hindi hit defaults to Hindi, stated honestly).
_HINDI_DEV = {
    "मुझे", "मेरा", "मेरी", "मैं", "आप", "तुम", "यह", "ये", "वह", "वो",
    "और", "लेकिन", "क्योंकि", "बहुत", "थोड़ा", "पानी", "खाना", "दवाई",
    "मदद", "धन्यवाद", "शुक्रिया", "चाहिए", "जाना", "आना", "करना", "होगा",
    "था", "थी", "हूं", "है", "क्या", "कैसे", "नहीं", "मत",
}
_EN_COMMON = {
    "the", "and", "please", "want", "need", "going", "doctor", "help",
    "thank", "sorry", "water", "food", "today", "tomorrow", "time",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z\u0900-\u097F]+", text.lower())


def _is_hindi_token(tok: str, low: str) -> bool:
    if low in _HINDI_COMMON:
        return True
    return tok in _HINDI_DEV


def detect_language(text: str) -> dict:
    """Return {language, confidence_note, code_switch, spans,
    languages_present, ambiguous, script}.

    Segment spans tag hi/en per token (Devanagari tokens without a Hindi
    lexicon hit take the sentence decision, which is Hindi). `ambiguous`
    is always False: with only one Devanagari language supported there is
    no close call left to flag.
    """
    if not text or not text.strip():
        return {"language": "en", "confidence_note": "empty input, defaulted",
                "code_switch": False, "spans": [], "languages_present": ["en"],
                "ambiguous": False, "script": "latin"}
    dev = len(_DEVANAGARI.findall(text))
    toks = _tokens(text)
    hi = sum(1 for t in toks if _is_hindi_token(t, t))
    en = sum(1 for t in toks if t in _EN_COMMON)
    dev_ratio = dev / max(len(text), 1)
    script = script_of(text)

    lang: str
    note: str
    if dev_ratio > 0.15 or hi > 0:
        if en >= 2 and hi >= 1:
            lang, note = "hinglish", "lexicon+script heuristic"
        elif hi > 0 or dev_ratio <= 0.15:
            lang, note = "hi", "lexicon+script heuristic"
        else:
            # Devanagari but no Hindi lexicon hit: default to Hindi but
            # say so honestly.
            lang, note = "hi", "devanagari-script default (no lexicon hit)"
    elif hi > 0 and en > 0:
        lang, note = "hinglish", "lexicon heuristic"
    elif hi > 0:
        lang, note = "hi", "lexicon heuristic"
    else:
        return {"language": "en", "confidence_note": "default", "code_switch": False,
                "spans": [], "languages_present": ["en"], "ambiguous": False, "script": script}
    spans = _code_switch_spans(text, dev_lang="hi")
    langs = sorted({s["lang"] for s in spans} | {lang})
    return {
        "language": lang,
        "confidence_note": note,
        "code_switch": len([s for s in spans if s["lang"] == "en"]) > 0 and any(
            s["lang"] == "hi" for s in spans),
        "spans": spans,
        "languages_present": langs,
        "ambiguous": False,
        "script": script,
    }


def _code_switch_spans(text: str, dev_lang: str = "hi") -> list[dict]:
    spans: list[dict] = []
    for m in re.finditer(r"[A-Za-z\u0900-\u097F]+", text):
        tok = m.group(0)
        low = tok.lower()
        if _is_hindi_token(tok, low):
            spans.append({"token": tok, "lang": "hi"})
        elif _DEVANAGARI.search(tok):
            spans.append({"token": tok, "lang": dev_lang})
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


def script_of(text: str) -> str:
    """secondary-script check: native (Devanagari) | latin | mixed."""
    has_dev = bool(_DEVANAGARI.search(text or ""))
    has_lat = bool(re.search(r"[A-Za-z]", text or ""))
    if has_dev and has_lat:
        return "mixed"
    if has_dev:
        return "native"
    return "latin"


def check_script(text: str, preferred: str) -> dict:
    """Compare actual script vs user preference (native|roman|mixed).

    Advisory only: full transliteration needs a benchmarked engine
    (documented next step), so a mismatch is reported, never converted.
    """
    actual = script_of(text)
    want_roman = preferred == "roman"
    match = (actual == "latin") if want_roman else (actual in ("native", "mixed") if preferred == "native" else True)
    return {"script": actual, "preferred": preferred, "match": match}


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


_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def translation_guards(original: str, translated: str) -> list[str]:
    """Advisory checks that translation preserved meaning-carriers.

    Numbers (both scripts), negation (multilingual set), non-emptiness,
    and a lenient length sanity bound. Warnings only — the user still
    confirms which version is spoken. Names across scripts cannot be
    checked deterministically; that stays a documented limitation.
    """
    from .reconstruction_service import NEGATION

    warnings = []
    t = (translated or "").strip()
    if not t:
        return ["empty translation output"]
    o_digits = re.findall(r"\d+", (original or "").translate(_DEV_DIGITS))
    t_digits = re.findall(r"\d+", t.translate(_DEV_DIGITS))
    if o_digits != t_digits:
        warnings.append(f"numbers changed in translation ({o_digits} → {t_digits})")
    pat = r"[A-Za-z']+|[\u0900-\u097F]+"
    o_neg = any(w.lower() in NEGATION or w.lower().endswith("n't") for w in re.findall(pat, original or ""))
    t_neg = any(w.lower() in NEGATION or w.lower().endswith("n't") for w in re.findall(pat, t))
    if o_neg != t_neg:
        warnings.append("negation presence changed in translation")
    ow, tw = len((original or "").split()), len(t.split())
    if ow and not (0.25 <= tw / ow <= 4.0):
        warnings.append("translation length looks suspicious — review before confirming")
    return warnings


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
