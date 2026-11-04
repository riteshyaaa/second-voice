"""Restoration pipeline: stage planning (pure) + execution.

plan_stages() is offline-testable: given config, it says exactly which
stages will run and why the others will not. run_job() executes the ready
stages against real services and stores the units evidence as a
`restored` AudioDerivative (operation `s2u-units`, JSON — never audio).
"""
import json
import os

from .. import audio_service
from .s2u_client import S2UUnavailable, fetch_units

ENHANCE_UNAVAILABLE = "no enhancer configured: Phase 4 ships no enhancement implementation"
VOCODE_UNAVAILABLE = "no vocoder checkpoint published (Phase 3 report); waveform synthesis disabled"


def plan_stages(*, restoration_enabled: bool) -> list[dict]:
    """Decide + explain. Pure function (offline-testable)."""
    stages = [
        {"stage": "normalize", "status": "ready", "reason": "audio_service.derive_normalized"},
        {"stage": "enhance", "status": "skipped", "reason": ENHANCE_UNAVAILABLE},
    ]
    if restoration_enabled:
        stages.append({"stage": "s2u_units", "status": "ready",
                       "reason": "inference sidecar (weights-gated at call time)"})
    else:
        stages.append({"stage": "s2u_units", "status": "skipped",
                       "reason": "RESTORATION_ENABLED is false"})
    stages.append({"stage": "vocode", "status": "skipped", "reason": VOCODE_UNAVAILABLE})
    return stages


async def run_job(db, audio, *, base_url: str, beam: int, timeout_s: float,
                  checkpoint: str) -> dict:
    """Execute normalize + S2U; persist units evidence. Raises on failure.

    Returns {"derivative", "units", "stages"} — the API layer owns the
    RestorationJob row. S2UUnavailable / FileNotFoundError / ValueError
    propagate with their reasons; nothing is synthesized on failure.
    """
    norm = audio_service.derive_normalized(db, audio)
    with open(norm.file_path, "rb") as f:
        wav = f.read()
    payload = await fetch_units(wav, base_url=base_url, beam=beam, timeout_s=timeout_s)
    units = payload["units"]
    doc = {"operation": "s2u-units", "checkpoint": payload.get("checkpoint", checkpoint),
           "beam": payload.get("beam", beam), "n_units": len(units),
           "frames": payload.get("frames"), "latency_s": payload.get("latency_s"),
           "vocoder": None, "units": units}
    blob = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    path = os.path.join(os.path.dirname(norm.file_path), f"restored_{audio.id}_units.json")
    with open(path, "wb") as f:
        f.write(blob)
    from ... import models as _models

    deriv = _models.AudioDerivative(
        parent_asset_id=audio.id, kind="restored", operation="s2u-units",
        model_version=payload.get("checkpoint", checkpoint),
        config={"beam": payload.get("beam", beam), "frames": payload.get("frames"),
                "latency_s": payload.get("latency_s"), "vocoder": None,
                "note": "S2U units as evidence; no waveform (no vocoder published)."},
        file_path=path, mime="application/json", duration_s=audio.duration_s or 0.0,
        quality=None, status="ready", error=None)
    db.add(deriv)
    db.commit()
    db.refresh(deriv)
    stages = plan_stages(restoration_enabled=True)
    return {"derivative": deriv, "units": units, "stages": stages,
            "latency_s": payload.get("latency_s"),
            "checkpoint": payload.get("checkpoint", checkpoint)}
