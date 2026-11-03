from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import audio_intelligence

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/audio/sessions")
def create_session(body: schemas.SessionIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    s = models.CommSession(user_id=user.id, title=body.title, language=body.language)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title, "language": s.language, "status": s.status, "created_at": s.created_at}


@router.get("/audio/sessions/{session_id}/audio/{audio_id}")
def download_audio(session_id: int, audio_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 8: replay the original recording (ownership + retention checked).

    Full clip only — per-segment replay needs word timings no provider
    exposes. Expired audio 410s via load_audio; never the AI text.
    """
    from fastapi.responses import FileResponse

    from ..services import audio_service

    s = db.query(models.CommSession).filter(models.CommSession.id == session_id, models.CommSession.user_id == user.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    audio = db.query(models.AudioAsset).filter(models.AudioAsset.id == audio_id, models.AudioAsset.session_id == session_id).first()
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    audio_service.load_audio(audio.file_path, prefs.audio_retention_days if prefs else 30)
    return FileResponse(audio.file_path, media_type=audio.mime or "audio/wav", filename=f"secondvoice_orig_{audio_id}.wav")


@router.post("/audio/sessions/{session_id}/audio")
async def upload_audio(session_id: int, request: Request, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    from ..services import audio_service

    s = db.query(models.CommSession).filter(models.CommSession.id == session_id, models.CommSession.user_id == user.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    body = await request.body()
    mime = (request.headers.get("content-type") or "audio/wav").split(";")[0].strip()
    path, duration = audio_service.save_audio(user.id, session_id, body, mime)
    quality = audio_intelligence.analyze_upload(body, mime)
    asset = models.AudioAsset(session_id=session_id, file_path=path, mime=mime, duration_s=duration,
                              quality=quality, consent_stored=False)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"audio_id": asset.id, "duration_s": duration, "mime": mime,
            "audio_quality": quality, "rerecord_suggested": quality.get("rerecord_suggested", False)}


@router.post("/audio/sessions/{session_id}/audio/{audio_id}/normalize")
def normalize_audio(session_id: int, audio_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """CLARIS P1: build (idempotent) the normalized derivative of an original.

    The original is only read. Only `normalized` is produced in P1;
    enhanced/restored/generated arrive with the restoration pipeline.
    """
    from ..services import audio_service

    s = db.query(models.CommSession).filter(models.CommSession.id == session_id, models.CommSession.user_id == user.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    audio = db.query(models.AudioAsset).filter(models.AudioAsset.id == audio_id, models.AudioAsset.session_id == session_id).first()
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    try:
        d = audio_service.derive_normalized(db, audio)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Audio expired or deleted per retention policy.")
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=f"Could not decode audio: {exc}")
    return {"derivative_id": d.id, "kind": d.kind, "operation": d.operation, "model_version": d.model_version,
            "duration_s": d.duration_s, "quality": d.quality, "status": d.status}


@router.get("/audio/sessions/{session_id}/audio/{audio_id}/derivatives/{derivative_id}")
def download_derivative(session_id: int, audio_id: int, derivative_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """CLARIS P1: replay a processing derivative (ownership + retention checked)."""
    from fastapi.responses import FileResponse

    from ..services import audio_service

    s = db.query(models.CommSession).filter(models.CommSession.id == session_id, models.CommSession.user_id == user.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    d = db.query(models.AudioDerivative).join(models.AudioAsset).filter(
        models.AudioDerivative.id == derivative_id, models.AudioDerivative.parent_asset_id == audio_id,
        models.AudioAsset.session_id == session_id).first()
    if d is None:
        raise HTTPException(status_code=404, detail="Derivative not found")
    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    audio_service.load_audio(d.file_path, prefs.audio_retention_days if prefs else 30)
    return FileResponse(d.file_path, media_type=d.mime or "audio/wav", filename=f"secondvoice_{d.kind}_{derivative_id}.wav")


@router.get("/sessions")
def list_sessions(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.CommSession).filter(models.CommSession.user_id == user.id).order_by(models.CommSession.id.desc()).limit(50).all()
    return [{"id": r.id, "title": r.title, "language": r.language, "status": r.status, "created_at": r.created_at} for r in rows]


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.query(models.CommSession).filter(models.CommSession.id == session_id, models.CommSession.user_id == user.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    items = []
    for audio in s.audios:
        for t in audio.transcripts:
            items.append({
                "audio_id": audio.id, "transcript_id": t.id, "original": t.text_original,
                "language": t.language, "provider": t.provider, "audio_quality": audio.quality,
                "uncertainty": (t.evidence or {}).get("uncertainty", []),
                "evidence": t.evidence,  # Phase 10: full audit trail per transcript
                "suggestions": [{"id": x.id, "proposed": x.proposed_text, "status": x.status, "abstained": x.abstained,
                                 "evidence_for": x.evidence_for or [],
                                 "evidence_missing": x.evidence_missing or []} for x in t.suggestions],
                "derivatives": [{"id": d.id, "kind": d.kind, "operation": d.operation,
                                 "model_version": d.model_version, "status": d.status,
                                 "duration_s": d.duration_s} for d in audio.derivatives],
            })
    approved = db.query(models.ApprovedMessage).filter(models.ApprovedMessage.session_id == session_id).all()
    return {"id": s.id, "title": s.title, "language": s.language, "items": items,
            "approved": [{"id": a.id, "text": a.final_text, "language": a.language} for a in approved]}
