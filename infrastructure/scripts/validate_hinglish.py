"""Hinglish check with real speech (key from .env, never printed).

No natural Hinglish recordings exist on Wikimedia Commons (searched
2026-10-31: 0 hits). This builds an INTRA-UTTERANCE mixed clip from two real
clips — Hindi dengue lead + English 'water caltrop' inserted mid-stream —
and labels it constructed everywhere. Tests: (1) live ASR transcribes both
spans, (2) reconstruction with preference 'hinglish' preserves the mix.
Writes validation_hinglish_results.json (committed evidence).
"""
import asyncio
import io
import json
import os
import sys
import tempfile
import time
import wave

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "backend"))
sys.path.insert(0, _HERE)
from validate_asr import to_wav  # noqa: E402

os.environ.setdefault("DATABASE_URL", "sqlite://")
with open(os.path.join(_HERE, "..", "..", ".env")) as f:
    for line in f:
        line = line.strip()
        if line.startswith("META_API_KEY="):
            os.environ["META_API_KEY"] = line.split("=", 1)[1]

from app.services import language_service as lang  # noqa: E402
from app.services import meta_asr_service as asr  # noqa: E402
from app.services import reconstruction_service as rs  # noqa: E402

CACHE = os.path.join(tempfile.gettempdir(), "sv-corpus")
RATE = 16000


def frames(path, start_s, end_s):
    with open(path, "rb") as f:
        raw = f.read()
    wav, _, _ = to_wav(raw, path)
    with wave.open(io.BytesIO(wav), "rb") as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1
        pcm = w.readframes(w.getnframes())
    a, b = int(start_s * RATE) * 2, int(end_s * RATE) * 2
    return pcm[a:b]


async def main():
    out: dict = {"constructed": True,
                 "recipe": "dengue[0:8s] + 0.3s silence + water_caltrop + 0.3s silence + dengue[8:16s]",
                 "sources": ["hi_dengue_lead.bin", "en_water_caltrop.bin"]}
    sil = b"\x00\x00" * int(0.3 * RATE)
    combo = frames(os.path.join(CACHE, "hi_dengue_lead.bin"), 0, 8) + sil \
        + frames(os.path.join(CACHE, "en_water_caltrop.bin"), 0, 2) + sil \
        + frames(os.path.join(CACHE, "hi_dengue_lead.bin"), 8, 16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(combo)
    blob = buf.getvalue()
    out["duration_s"] = round(len(combo) / 2 / RATE, 2)

    t0 = time.time()
    res = await asr.transcribe(blob, "audio/wav", "auto", [])
    out["asr_latency_s"] = round(time.time() - t0, 2)
    hyp = (res.get("text") or "").strip()
    out.update(provider=res.get("provider"), asr_language=res.get("language"), hypothesis=hyp)
    det = lang.detect_language(hyp) if hyp else {}
    out.update(detected=det.get("language"), code_switch=det.get("code_switch"))
    low = hyp.lower()
    out["hindi_span_present"] = "डेंगू" in hyp or "बुखार" in hyp
    out["english_span_present"] = "water" in low and "caltrop" in low
    print("ASR:", hyp.encode("ascii", "backslashreplace").decode()[:160])

    t0 = time.time()
    sug, _ = await rs.suggest(hyp, {}, [], "hinglish", "")
    out["suggest_latency_s"] = round(time.time() - t0, 2)
    prop = sug["proposed_text"]
    out.update(suggest_provider=sug.get("provider"), proposed=prop,
               abstained=sug["abstained"], guard_problems=rs.violates_guards(hyp, prop))
    pdet = lang.detect_language(prop)["language"]
    out["proposed_detected"] = pdet
    # preservation: mixed output kept (hinglish), not flattened to pure en/hi, no guard breach
    out["mix_preserved"] = pdet == "hinglish" and not out["guard_problems"]
    print("SUG:", prop.encode("ascii", "backslashreplace").decode()[:160])
    print("mix_preserved:", out["mix_preserved"], "| guards:", out["guard_problems"])
    with open(os.path.join(_HERE, "validation_hinglish_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
