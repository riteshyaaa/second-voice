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
                "suggestions": [{"id": x.id, "proposed": x.proposed_text, "status": x.status, "abstained": x.abstained} for x in t.suggestions],
            })
    approved = db.query(models.ApprovedMessage).filter(models.ApprovedMessage.session_id == session_id).all()
    return {"id": s.id, "title": s.title, "language": s.language, "items": items,
            "approved": [{"id": a.id, "text": a.final_text, "language": a.language} for a in approved]}
