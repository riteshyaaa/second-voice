from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.config import settings
from ..core.database import get_db
from ..core.deps import current_user
from ..core.ratelimit import rate_limit
from ..services import audio_service, meta_asr_service
from ..services.speech_restoration import comparison, pipeline
from ..services.speech_restoration.s2u_client import S2UUnavailable

router = APIRouter(prefix="/api/v1", tags=["restoration"])


def _owned_audio(db: Session, user_id: int, session_id: int, audio_id: int) -> models.AudioAsset:
    s = db.query(models.CommSession).filter(models.CommSession.id == session_id,
                                            models.CommSession.user_id == user_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    audio = db.query(models.AudioAsset).filter(models.AudioAsset.id == audio_id,
                                               models.AudioAsset.session_id == session_id).first()
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    return audio


def _job_out(job: models.RestorationJob) -> dict:
    return {"job_id": job.id, "audio_id": job.audio_id, "checkpoint": job.checkpoint,
            "beam": job.beam, "status": job.status, "stages": job.stages,
            "derivative_id": job.derivative_id, "error": job.error,
            "created_at": job.created_at}


@router.post("/audio/sessions/{session_id}/audio/{audio_id}/restoration/jobs")
async def create_restoration_job(session_id: int, audio_id: int, body: schemas.RestorationJobIn,
                                 request: Request, user: models.User = Depends(current_user),
                                 db: Session = Depends(get_db)):
    """CLARIS P4: run normalize + S2U units over the original; store units evidence.

    Disabled without RESTORATION_ENABLED (explicit 409 with reason).
    Waveform is never produced: no vocoder checkpoint exists (Phase 3).
    """
    rate_limit(request)
    audio = _owned_audio(db, user.id, session_id, audio_id)
    if not settings.RESTORATION_ENABLED:
        return {"status": "unavailable",
                "reason": "RESTORATION_ENABLED is false",
                "stages": pipeline.plan_stages(restoration_enabled=False)}
    job = models.RestorationJob(audio_id=audio.id, checkpoint=settings.RESTORATION_CHECKPOINT,
                                beam=body.beam, status="running",
                                stages=pipeline.plan_stages(restoration_enabled=True))
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        result = await pipeline.run_job(db, audio, base_url=settings.RESTORATION_S2U_URL,
                                        beam=body.beam, timeout_s=settings.RESTORATION_TIMEOUT_S,
                                        checkpoint=settings.RESTORATION_CHECKPOINT)
    except (S2UUnavailable, FileNotFoundError, ValueError) as exc:
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        db.refresh(job)
        return _job_out(job)
    job.status = "units_ready"
    job.derivative_id = result["derivative"].id
    job.checkpoint = result["checkpoint"]
    db.commit()
    db.refresh(job)
    out = _job_out(job)
    out["n_units"] = len(result["units"])
    out["latency_s"] = result["latency_s"]
    return out


@router.get("/audio/sessions/{session_id}/audio/{audio_id}/restoration/jobs/{job_id}")
def get_restoration_job(session_id: int, audio_id: int, job_id: int,
                        user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    audio = _owned_audio(db, user.id, session_id, audio_id)
    job = db.query(models.RestorationJob).filter(models.RestorationJob.id == job_id,
                                                 models.RestorationJob.audio_id == audio.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Restoration job not found")
    return _job_out(job)


@router.get("/audio/sessions/{session_id}/audio/{audio_id}/restoration/jobs/{job_id}/comparison")
async def get_job_comparison(session_id: int, audio_id: int, job_id: int,
                             user: models.User = Depends(current_user),
                             db: Session = Depends(get_db)):
    """CLARIS P5: side-by-side evidence for one restoration job.

    Runs primary ASR over the original and the normalized derivative
    (two live ASR calls — explicit user action), attaches stored S2U
    units, and marks enhanced audio / restored waveform unavailable with
    reasons. Per-artifact failures are recorded, never hidden.
    """
    audio = _owned_audio(db, user.id, session_id, audio_id)
    job = db.query(models.RestorationJob).filter(models.RestorationJob.id == job_id,
                                                 models.RestorationJob.audio_id == audio.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Restoration job not found")
    if job.status != "units_ready":
        raise HTTPException(status_code=409,
                            detail=f"Job is {job.status}: comparison needs units_ready")
    session = db.query(models.CommSession).filter(models.CommSession.id == session_id).first()
    lang = (session.language if session and session.language else "auto")

    async def _transcribe(data: bytes, mime: str) -> dict:
        try:
            out = await meta_asr_service.transcribe(data, mime, lang)
            return {"text": out.get("text", ""), "language": out.get("language"),
                    "provider": out.get("provider"), "model_version": out.get("model_version")}
        except Exception as exc:  # noqa: BLE001 — per-artifact failure is data
            return {"error": f"{type(exc).__name__}: {exc}"[:300]}

    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    retention = prefs.audio_retention_days if prefs else 30
    try:
        orig_bytes = audio_service.load_audio(audio.file_path, retention)
        norm = audio_service.derive_normalized(db, audio)
        with open(norm.file_path, "rb") as f:
            norm_bytes = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Audio expired or deleted per retention policy.")
    original = await _transcribe(orig_bytes, audio.mime or "audio/wav")
    normalized = await _transcribe(norm_bytes, "audio/wav")

    import json as _json

    units = None
    if job.derivative_id:
        d = db.query(models.AudioDerivative).filter(
            models.AudioDerivative.id == job.derivative_id).first()
        if d is not None:
            try:
                with open(d.file_path, "rb") as f:
                    doc = _json.load(f)
                units = {"units": doc.get("units", []),
                         "checkpoint": job.checkpoint, "beam": job.beam,
                         "latency_s": (doc.get("latency_s"))}
            except (OSError, ValueError) as exc:
                units = {"units": [], "checkpoint": job.checkpoint,
                         "beam": job.beam, "error": f"units file unreadable: {exc}"[:200]}
    report = comparison.build_report(original=original, normalized=normalized,
                                     units=units, stages=job.stages or [])
    report["job_id"] = job.id
    return report
