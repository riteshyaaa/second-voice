"""CLARIS P2: same clips through each ASR provider (reproducible benchmark).

Runs inside the backend container (key + deps present):
  docker compose exec backend python scripts/bench_asr.py \\
      --refs bench-clips/refs.jsonl --providers meta-asr,local-whisper

Refs: JSON list of {file, language, reference}. Clips ship in the image so a
rerun reproduces numbers; failures are recorded, never hidden.
"""
import argparse
import asyncio
import json
import mimetypes
import os
import sys
import time

sys.path.insert(0, "/srv")

from app.services import asr_providers, evaluation_service  # noqa: E402


def clip_path(raw: str, base: str) -> str:
    """Refs store repo-relative paths; remap under the in-image bench dir."""
    rel = raw.replace("\\", "/")
    marker = "bench-clips/"
    if marker in rel:
        rel = rel[rel.index(marker) + len(marker):]
    return os.path.join(base, rel)


def load_bytes(path: str) -> tuple[bytes, str]:
    with open(path, "rb") as f:
        data = f.read()
    mime, _ = mimetypes.guess_type(path)
    return data, mime or "audio/wav"


async def bench_one(provider, clip: dict) -> dict:
    from app.services.audio_service import normalize_to_wav16k

    data, mime = load_bytes(clip["file"])
    start = time.perf_counter()
    try:
        data = normalize_to_wav16k(data, mime)
    except Exception as exc:  # noqa: BLE001
        return {"file": clip["file"], "language": clip.get("language", "?"), "hypothesis": "",
                "wer": 1.0, "cer": 1.0, "latency_s": 0.0,
                "failure": f"normalize: {type(exc).__name__}: {exc}"[:300],
                "provider": None, "model": None}
    try:
        out = await provider.transcribe(data, mime, clip.get("language", "auto"))
        text = (out.get("text") or "")
        err = None
    except Exception as exc:  # noqa: BLE001 — failures are data here
        text, err = "", f"{type(exc).__name__}: {exc}"[:300]
    dt = time.perf_counter() - start
    ref = clip.get("reference", "")
    return {"file": clip["file"], "language": clip.get("language", "?"),
            "hypothesis": text, "wer": evaluation_service.wer(ref, text)["wer"],
            "cer": evaluation_service.cer(ref, text)["cer"],
            "latency_s": round(dt, 2), "failure": err,
            "provider": out.get("provider") if err is None else None,
            "model": out.get("model_version") if err is None else None}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", required=True)
    ap.add_argument("--providers", default="meta-asr")
    ap.add_argument("--out", default="")
    ap.add_argument("--base", default="bench-clips")
    args = ap.parse_args()

    refs = json.load(open(args.refs, encoding="utf-8"))
    providers = {}
    for name in args.providers.split(","):
        name = name.strip()
        try:
            providers[name] = asr_providers.get_provider(name)
        except (ValueError, RuntimeError) as exc:
            print(f"SKIP {name}: {exc}")

    rows = []
    for clip in refs:
        clip = dict(clip)
        clip["file"] = clip_path(clip["file"], args.base)
        for name, prov in providers.items():
            r = await bench_one(prov, clip)
            r["engine"] = name
            rows.append(r)
            flag = "FAIL " + r["failure"] if r["failure"] else f"wer={r['wer']:.3f} {r['latency_s']}s"
            print(f"{clip['language']:>3} {os.path.basename(clip['file']):>22} {name:<14} {flag}")

    langs = sorted({r["language"] for r in rows})
    print("\n| engine | lang | n | mean WER | mean CER | mean s | fails |")
    print("|---|---|---|---|---|---|---|")
    summary = []
    for name in providers:
        for lang in langs + ["ALL"]:
            sel = [r for r in rows if r["engine"] == name and (lang == "ALL" or r["language"] == lang)]
            ok = [r for r in sel if not r["failure"]]
            fails = len(sel) - len(ok)
            if ok:
                mw = sum(r["wer"] for r in ok) / len(ok)
                mc = sum(r["cer"] for r in ok) / len(ok)
                ms = sum(r["latency_s"] for r in ok) / len(ok)
            else:
                mw = mc = ms = None
            summary.append({"engine": name, "language": lang, "n": len(sel),
                            "mean_wer": mw, "mean_cer": mc, "mean_latency_s": ms, "fails": fails})
            f = lambda v: f"{v:.3f}" if v is not None else "-"
            print(f"| {name} | {lang} | {len(sel)} | {f(mw)} | {f(mc)} | {f(ms)} | {fails} |")
    if args.out:
        json.dump({"rows": rows, "summary": summary}, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
