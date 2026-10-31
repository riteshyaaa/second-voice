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
