"""Live adversarial battery: does Muse Spark preserve meaning? Key from .env (never printed).

Pass criteria = the product contract (guards + abstention), not my opinion:
- violates_guards(original, proposed) must be empty, AND
- garbage/disfluent inputs must abstain or echo (never invent a request), AND
- requests must stay requests.
Writes validation_meaning_results.json (committed evidence).
"""
import asyncio
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "backend"))

os.environ.setdefault("DATABASE_URL", "sqlite://")
with open(os.path.join(_HERE, "..", "..", ".env")) as f:
    for line in f:
        line = line.strip()
        if line.startswith("META_API_KEY="):
            os.environ["META_API_KEY"] = line.split("=", 1)[1]

from app.services import reconstruction_service as rs  # noqa: E402

CASES = [
    # (id, transcript, vocab, must_contain_or_None, category)
    ("neg-en", "I don't want to go.", {}, "don't", "negation"),
    ("neg-never", "I never take sugar.", {}, "never", "negation"),
    ("neg-hi", "मुझे दवाई नहीं चाहिए।", {}, "नहीं", "negation"),
    ("num-dose", "Take 2 tablets at 5 pm.", {}, "2", "numbers"),
    ("num-hi", "मुझे 3 बोतल चाहिए।", {}, "3", "numbers"),
    ("name", "Call Aarav at noon.", {}, "Aarav", "names"),
    ("request", "Can you please wait?", {}, None, "intent"),
    ("statement", "The doctor is here.", {}, None, "intent"),
    ("disfluent", "Um... uh... hmm.", {}, None, "abstain"),
    ("garbage", "zzz xyz qqq.", {}, None, "abstain"),
    ("empty", "   ", {}, None, "abstain"),
    ("single-hi", "पानी", {}, None, "short"),
    ("misheard", "Bani.", {"bani": "पानी"}, "पानी", "vocab"),
    ("context-trap", "I want to meet the doctor.", {}, None, "stability"),
]


async def main() -> list[dict]:
    rows = []
    for cid, text, vocab, must, cat in CASES:
        t0 = time.time()
        try:
            out, _ = await rs.suggest(text, vocab, [], "en", "")
            lat = round(time.time() - t0, 2)
            prop = out["proposed_text"]
            problems = rs.violates_guards(text, prop)
            invented = cat == "abstain" and not out["abstained"] and prop.strip().rstrip(".") not in (
                text.strip(), text.strip().rstrip("."), "")
            # disfluent/empty must not gain content words
            gained = False
            if cat == "abstain" and prop.strip():
                gained = len(prop.split()) > len(text.split()) + 1
            ok = (not problems) and (must is None or must in prop) and not invented and not gained
            # requests must stay requests: no flipping ? <-> .
            if cat == "intent" and text.strip().endswith("?") and not prop.strip().endswith("?"):
                ok = False
            rows.append({"id": cid, "category": cat, "transcript": text, "proposed": prop,
                         "provider": out.get("provider"), "abstained": out["abstained"],
                         "needs_clarification": out["needs_clarification"],
                         "guard_problems": problems, "latency_s": lat,
                         "pass": ok, "error": None})
        except Exception as e:  # noqa: BLE001
            rows.append({"id": cid, "category": cat, "transcript": text, "pass": False,
                         "error": str(e)[:200]})
        r = rows[-1]
        safe = (r.get("proposed", "!") or "!").encode("ascii", "backslashreplace").decode()
        print(f"{cid:>12} [{r['category']:>8}] pass={r['pass']} abst={r.get('abstained')} "
              f"guards={r.get('guard_problems')} | {safe[:70]} | {r.get('latency_s', '?')}s")
    with open(os.path.join(_HERE, "validation_meaning_results.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    n = len(rows)
    print(f"PASSED {sum(1 for r in rows if r['pass'])}/{n}")
    return rows


if __name__ == "__main__":
    asyncio.run(main())
