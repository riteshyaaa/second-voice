"""Evaluation metrics: WER / CER + reconstruction guard checks."""
import re


def _words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z\u0900-\u097F']+", s.lower())


def _lev(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(reference: str, hypothesis: str) -> dict:
    r, h = _words(reference), _words(hypothesis)
    if not r:
        return {"wer": 0.0 if not h else 1.0, "ref_words": 0, "errors": len(h)}
    return {"wer": round(_lev(r, h) / len(r), 4), "ref_words": len(r), "errors": _lev(r, h)}


def cer(reference: str, hypothesis: str) -> dict:
    r, h = list(reference), list(hypothesis)
    if not r:
        return {"cer": 0.0 if not h else 1.0}
    return {"cer": round(_lev(r, h) / len(r), 4)}


def guard_report(original: str, proposed: str) -> dict:
    from .reconstruction_service import violates_guards

    problems = violates_guards(original, proposed)
    return {"passed": not problems, "violations": problems}


def preservation_report(reference: str, proposed: str) -> dict:
    """Phase 11: per-category preservation of INTENT (reference vs
    proposed). Use alongside guard_report(original, proposed), which
    measures corruption of the transcript — the two answer different
    questions and both are reported."""
    from .reconstruction_service import GUARD_CATEGORIES, guard_scores

    scores = guard_scores(reference, proposed)
    kept = sum(1 for c in GUARD_CATEGORIES if scores[c])
    return {"scores": scores, "preserved": kept, "of": len(GUARD_CATEGORIES),
            "rate": round(kept / len(GUARD_CATEGORIES), 3)}


def empty_rate(texts: list[str]) -> dict:
    """Phase 11: share of empty transcripts (abstention signal, not error)."""
    texts = texts or []
    empty = sum(1 for t in texts if not (t or "").strip())
    return {"n": len(texts), "empty": empty,
            "rate": round(empty / max(len(texts), 1), 3)}


def span_retention(reference_runs: list[dict], detected_runs: list[dict]) -> dict:
    """Phase 11: code-switch span retention. Runs are [{lang, tokens[]}].
    Token-level recall per language plus the share of language-switch
    boundaries still present (merged spans keep recall but lose the
    boundary — both numbers are reported separately)."""
    def expand(runs):
        return [(s.get("lang", "?"), t.lower()) for s in runs for t in s.get("tokens", [])]

    ref, det = expand(reference_runs), expand(detected_runs)
    ref_by_tok = {}
    for lang, tok in ref:
        ref_by_tok.setdefault(tok, lang)
    per_lang: dict[str, dict] = {}
    for lang in sorted({l for l, _ in ref}):
        toks = [t for l, t in ref if l == lang]
        hit = sum(1 for t in toks if ref_by_tok.get(t) == next((dl for dl, dt in det if dt == t), None))
        per_lang[lang] = {"tokens": len(toks), "kept": hit,
                          "recall": round(hit / max(len(toks), 1), 3)}
    # boundary score: adjacent ref pairs with different langs, still split in detected
    bounds, kept_bounds = 0, 0
    det_langs = [l for l, _ in det]
    det_toks = [t for _, t in det]
    for (l1, t1), (l2, t2) in zip(ref, ref[1:]):
        if l1 == l2:
            continue
        bounds += 1
        if t1 in det_toks and t2 in det_toks:
            i1, i2 = det_toks.index(t1), det_toks.index(t2)
            if abs(i1 - i2) == 1 and det_langs[i1] != det_langs[i2]:
                kept_bounds += 1
    return {"per_language": per_lang,
            "boundaries": {"n": bounds, "kept": kept_bounds,
                           "rate": round(kept_bounds / max(bounds, 1), 3) if bounds else None}}
