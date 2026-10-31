"""Live ASR validation on the real-speech corpus. Key read from repo .env (never printed).

Writes results JSON next to this script (validation evidence, committed).
Usage (repo root): .venv/Scripts/python infrastructure/scripts/validate_asr.py
"""
import asyncio
import io
import json
import os
import sys
import time
import urllib.request
import wave

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "backend"))
sys.path.insert(0, _HERE)
from validation_corpus import CORPUS  # noqa: E402

os.environ.setdefault("DATABASE_URL", "sqlite://")
with open(os.path.join(_HERE, "..", "..", ".env")) as f:
    for line in f:
        line = line.strip()
        if line.startswith("META_API_KEY="):
            os.environ["META_API_KEY"] = line.split("=", 1)[1]
        elif line.startswith("META_BASE_URL="):
            os.environ["META_BASE_URL"] = line.split("=", 1)[1]

import miniaudio  # noqa: E402
from app.services import evaluation_service as ev  # noqa: E402
from app.services import language_service as lang  # noqa: E402
from app.services import meta_asr_service as asr  # noqa: E402


def _mono16(pcm: bytes, channels: int) -> bytes:
    if channels == 1:
        return pcm
    import array

    a = array.array("h", pcm)
    mono = array.array("h", (int((a[i] + a[i + 1]) / 2) for i in range(0, len(a) - 1, 2)))
    return mono.tobytes()


def resample_linear(pcm: bytes, src_rate: int, dst_rate: int = 16000) -> bytes:
    """Dependency-free linear-interpolation resampler (int16 mono). Adequate
    for ASR input; not studio quality, and documented as such."""
    import array

    if src_rate == dst_rate:
        return pcm
    a = array.array("h", pcm)
    n_in = len(a)
    n_out = int(round(n_in * dst_rate / src_rate))
    out = array.array("h", [0]) * n_out
    for i in range(n_out):
        pos = i * (n_in - 1) / max(n_out - 1, 1)
        j = int(pos)
        frac = pos - j
        s0, s1 = a[j], a[min(j + 1, n_in - 1)]
        out[i] = int(s0 + (s1 - s0) * frac)
    return out.tobytes()


def to_wav(raw: bytes, name: str, trim_s: float | None = None) -> tuple[bytes, float, int]:
    """Decode wav/ogg → mono 16-bit WAV at 16 kHz (Meta ASR requires
    mono s16le at 16 or 24 kHz; verified live against the API error)."""
    if "?" in name:
        name = name.split("?")[0]
    if name.endswith(".wav"):
        with wave.open(io.BytesIO(raw), "rb") as w:
            n, rate, ch = w.getnframes(), w.getframerate(), w.getnchannels()
            pcm = _mono16(w.readframes(n), ch)
    else:
        dec = miniaudio.decode(raw, output_format=miniaudio.SampleFormat.SIGNED16)
        rate = dec.sample_rate
        pcm = _mono16(bytes(dec.samples), dec.nchannels)
    pcm = resample_linear(pcm, rate, 16000)
    rate = 16000
    total_s = len(pcm) / 2 / rate
    if trim_s and total_s > trim_s:
        pcm = pcm[: int(trim_s * rate) * 2]
        total_s = trim_s
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue(), round(total_s, 2), rate


async def run() -> list[dict]:
    out: list[dict] = []
    wavs: dict[str, bytes] = {}
    import tempfile

    cache = os.path.join(tempfile.gettempdir(), "sv-corpus")
    os.makedirs(cache, exist_ok=True)
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "SecondVoiceValidation/1.0 (assistive-tech research validation; contact via repo)")]
    for item in CORPUS:
        cached = os.path.join(cache, item["id"] + ".bin")
        if os.path.exists(cached):
            with open(cached, "rb") as f:
                raw = f.read()
            dl = 0.0
        else:
            raw, dl = None, 0.0
            for attempt in range(4):
                try:
                    t0 = time.time()
                    with opener.open(item["url"], timeout=60) as r:
                        raw = r.read()
                    dl = round(time.time() - t0, 1)
                    break
                except Exception as e:  # noqa: BLE001 — 429 backoff then continue
                    print(f"{item['id']}: download attempt {attempt + 1} failed ({str(e)[:80]}), backing off")
                    time.sleep(5 * (attempt + 1))
            if raw is None:
                out.append({"id": item["id"], "error": "download failed after retries"})
                continue
            with open(cached, "wb") as f:
                f.write(raw)
        time.sleep(2)  # be polite to upload.wikimedia.org
        trim = 25.0 if item["id"] == "hi_dengue_lead" else None
        wav, dur, rate = to_wav(raw, item["url"], trim)
        wavs[item["id"]] = wav
        t1 = time.time()
        try:
            res = await asr.transcribe(wav, "audio/wav", "auto", [])
            lat = round(time.time() - t1, 2)
            hyp = (res.get("text") or "").strip()
            det = lang.detect_language(hyp) if hyp else {"language": "?", "code_switch": False}
            row = {"id": item["id"], "expected_lang": item["lang"], "ref": item["ref"],
                   "ref_kind": item["ref_kind"], "hypothesis": hyp, "asr_language": res.get("language"),
                   "provider": res.get("provider"), "detected": det["language"],
                   "code_switch": det.get("code_switch"), "duration_s": dur, "sample_rate": rate,
                   "latency_s": lat, "download_s": dl, "error": None}
            if item["ref_kind"] == "exact":
                row["wer"] = ev.wer(item["ref"], hyp)["wer"]
                row["cer"] = ev.cer(item["ref"], hyp)["cer"]
            if item["lang"] in ("hi", "mr") and not row.get("error"):
                # explicit-hint pass: does telling the model the language fix auto-mode English bias?
                t2 = time.time()
                try:
                    res2 = await asr.transcribe(wav, "audio/wav", item["lang"], [])
                    hyp2 = (res2.get("text") or "").strip()
                    row["hinted_hypothesis"] = hyp2
                    row["hinted_latency_s"] = round(time.time() - t2, 2)
                    if item["ref_kind"] == "exact":
                        row["hinted_wer"] = ev.wer(item["ref"], hyp2)["wer"]
                        row["hinted_cer"] = ev.cer(item["ref"], hyp2)["cer"]
                except Exception as e2:  # noqa: BLE001
                    row["hinted_error"] = str(e2)[:200]
        except Exception as e:  # noqa: BLE001 — record, don't stop the battery
            row = {"id": item["id"], "error": str(e)[:200]}
        out.append(row)
        safe_hyp = (row.get("hypothesis", "!") or "!").encode("ascii", "backslashreplace").decode()
        safe_hint = (row.get("hinted_hypothesis", "") or "").encode("ascii", "backslashreplace").decode()
        extra = (f" | ERROR {row['error']}" if row.get("error") else "")
        extra += (f" | hinted={safe_hint[:40]} w={row.get('hinted_wer', '?')}" if safe_hint else "")
        extra += (f" | HINT-ERR {row['hinted_error'][:80]}" if row.get("hinted_error") else "")
        print(f"{row['id']:>18} | hyp={safe_hyp[:60]} | wer={row.get('wer', '-')} | "
              f"lang={row.get('asr_language')}/{row.get('detected')} | {row.get('latency_s', '?')}s" + extra)
    with open(os.path.join(_HERE, "validation_asr_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    # constructed code-switch: real Hindi word + real English phrase (rates must match)
    if "hi_paani" not in wavs or "en_water_caltrop" not in wavs:
        out.append({"id": "cs_constructed", "error": "source clip(s) missing (download throttled), skipped"})
        print("    cs_constructed | SKIPPED (missing source clips)")
        return out
    a = wavs["hi_paani"]
    b = wavs["en_water_caltrop"]
    with wave.open(io.BytesIO(a), "rb") as w:
        ra, pa = w.getframerate(), w.readframes(w.getnframes())
    with wave.open(io.BytesIO(b), "rb") as w:
        rb, pb = w.getframerate(), w.readframes(w.getnframes())
    rate = ra if ra == rb else None
    if rate is None:  # honest skip rather than a resampling hack
        out.append({"id": "cs_constructed", "error": f"rate mismatch {ra} vs {rb}, skipped"})
    else:
        silence = b"\x00\x00" * int(0.4 * rate)
        combo = pa + silence + pb
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(combo)
    if rate is not None:
        t1 = time.time()
        try:
            res = await asr.transcribe(buf.getvalue(), "audio/wav", "auto", [])
            lat = round(time.time() - t1, 2)
            hyp = (res.get("text") or "").strip()
            det = lang.detect_language(hyp) if hyp else {"language": "?", "code_switch": False}
            row = {"id": "cs_constructed", "expected_lang": "hi+en", "ref": "पानी + water caltrop",
                   "ref_kind": "constructed", "hypothesis": hyp, "asr_language": res.get("language"),
                   "provider": res.get("provider"), "detected": det["language"],
                   "code_switch": det.get("code_switch"), "duration_s": round(len(combo) / 2 / rate, 2),
                   "latency_s": lat, "error": None}
        except Exception as e:  # noqa: BLE001
            row = {"id": "cs_constructed", "error": str(e)[:200]}
        out.append(row)
        safe_hyp = (row.get("hypothesis", "!") or "!").encode("ascii", "backslashreplace").decode()
        print(f"{'cs_constructed':>18} | hyp={safe_hyp[:60]} | "
              f"lang={row.get('asr_language')}/{row.get('detected')} cs={row.get('code_switch')}")
    with open(os.path.join(_HERE, "validation_asr_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    asyncio.run(run())
