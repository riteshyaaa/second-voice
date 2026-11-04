"""CLARIS Phase 4: S2U units microservice (research-only, no LICENSE upstream).

Serves the reproduced CLARIS-Inference speech-to-unit path over HTTP so the
backend stays torch-free. One checkpoint loaded once at startup.

Endpoints:
  GET  /healthz  -> {ok, checkpoint, device, units_available}
  POST /units     -> raw WAV body (+ ?beam=N) -> {units, frames, ...}

Waveform synthesis is intentionally absent: the Code HiFi-GAN checkpoint
was never published (Phase 3 report). This service never claims otherwise.
"""
import io
import os
import sys
import time
import types

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

CLARIS_DIR = "/opt/claris"
CHECKPOINT = os.environ.get("CLARIS_CHECKPOINT", "wtimit_44spkrs_trained.pt")
BEAM_DEFAULT = int(os.environ.get("CLARIS_BEAM", "5"))
DEVICE = "cpu"

sys.path.insert(0, CLARIS_DIR)

# --- Upstream-compat shims (documented, ours). torchaudio>=2.9 removed
# sox_effects and sequence_generator.py has a stale fairseq import.
# Inputs here are always 16 kHz mono WAV, so neither path is exercised.
import torchaudio as _ta  # noqa: E402

if not hasattr(_ta, "sox_effects"):
    _sox = types.ModuleType("torchaudio.sox_effects")

    def _missing(*a, **k):
        raise RuntimeError("sox_effects unavailable; input must be 16 kHz mono")

    _sox.apply_effects_tensor = _missing
    sys.modules["torchaudio.sox_effects"] = _sox

from data.dataset import getFeaturesOrWaveform  # noqa: E402
from model import SpeechToUnitTransformer  # noqa: E402
from params import ModelParams  # noqa: E402
from utils import Dictionary  # noqa: E402

_generate = types.ModuleType("generate")
_generate.Dictionary = Dictionary
sys.modules["generate"] = _generate

from sequence_generator import SequenceGenerator  # noqa: E402
from utils import (  # noqa: E402
    getModelStateDictFromPath,
    getSymbolsToStripFromOutput,
    postProcessPrediction,
)

app = FastAPI(title="secondvoice-inference-s2u")
_state: dict = {"model": None, "generator": None, "tgt_dict": None,
                "checkpoint": None, "load_s": None}


def _load():
    t0 = time.perf_counter()
    tgt_dict = Dictionary()
    for i in range(1000):
        tgt_dict.addSymbol(str(i))
    model = SpeechToUnitTransformer.buildModel(params=ModelParams(), tgtDict=tgt_dict)
    ckpt_path = f"/models/claris/{CHECKPOINT}"
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"checkpoint missing: {ckpt_path}")
    model.load_state_dict(getModelStateDictFromPath(ckpt_path, model.state_dict()))
    model.eval()
    generator = SequenceGenerator(model=model, tgtDict=tgt_dict,
                                  beamSize=BEAM_DEFAULT, maxLenA=1, maxLen=50_000)
    _state.update(model=model, generator=generator, tgt_dict=tgt_dict,
                  checkpoint=CHECKPOINT, load_s=round(time.perf_counter() - t0, 1))


@app.on_event("startup")
def startup():
    _load()


@app.get("/healthz")
def healthz():
    gen = _state["generator"]
    return {"ok": gen is not None, "checkpoint": _state["checkpoint"],
            "device": DEVICE, "units_available": gen is not None,
            "vocoder_available": False,
            "note": "S2U units only; no vocoder checkpoint published"}


@app.post("/units")
async def units(request: Request, beam: int = 0):
    if _state["generator"] is None:
        raise HTTPException(status_code=503, detail="S2U model not loaded")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty audio body")
    try:
        wav, sr = sf.read(io.BytesIO(body))
    except Exception as exc:
        raise HTTPException(status_code=415, detail=f"Could not decode audio: {exc}")
    if sr != 16_000:
        raise HTTPException(status_code=415, detail=f"Expected 16 kHz WAV, got {sr} Hz")
    import tempfile

    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(body)
        tmp.flush()
        feats = getFeaturesOrWaveform(path=tmp.name)
    audio = torch.from_numpy(feats).float()
    gen = _state["generator"]
    if beam and beam != gen.beamSize:
        from copy import copy
        gen = copy(gen)
        gen.beamSize = max(1, min(beam, 20))
    hypos = gen.generate(
        srcTokens=audio.unsqueeze(0),
        srcLengths=torch.tensor([audio.size(0)], dtype=torch.long),
        ids=torch.tensor([0], dtype=torch.long),
    )
    hypo = hypos[0][0]
    _, hypo_str = postProcessPrediction(
        hypoTokens=hypo["tokens"].int().cpu(), srcStr="",
        alignment=hypo["alignment"], alignDict=None, tgtDict=_state["tgt_dict"],
        removeBpe=None, extraSymbolsToIgnore=getSymbolsToStripFromOutput(gen),
    )
    unit_list = [int(u) for u in hypo_str.split()]
    dt = time.perf_counter() - t0
    return JSONResponse({
        "units": unit_list, "n_units": len(unit_list),
        "frames": int(audio.size(0)), "duration_s": round(len(wav) / sr, 2),
        "checkpoint": _state["checkpoint"], "beam": gen.beamSize,
        "latency_s": round(dt, 1),
    })
