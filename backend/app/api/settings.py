from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import audio_service

router = APIRouter(prefix="/api/v1", tags=["settings-account"])

EDITABLE = {"preferred_language", "output_language", "script", "tts_voice", "tts_speed",
            "learning_enabled", "save_rejections", "use_history", "audio_retention_days",
            "font_scale", "reduced_motion", "high_contrast"}


@router.get("/preferences")
def get_prefs(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    if p is None:
        p = models.UserPreference(user_id=user.id)
        db.add(p)
        db.commit()
        db.refresh(p)
    return {c: getattr(p, c) for c in EDITABLE}


@router.patch("/preferences")
def patch_prefs(body: schemas.PreferencesIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    for field in EDITABLE:
        val = getattr(body, field, None)
        if val is not None:
            setattr(p, field, val)
    db.commit()
    return {"updated": True}


@router.post("/account/data")
def export_all(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    from .memory import export_memory

    return export_memory(user, db)


@router.delete("/account/data")
def delete_all(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Full account wipe: preferences, sessions (audio files deleted), all rows."""
    sessions = db.query(models.CommSession).filter(models.CommSession.user_id == user.id).all()
    for s in sessions:
        for a in s.audios:
            audio_service.delete_audio(a.file_path)
    for tts in db.query(models.TTSRequest).join(models.ApprovedMessage).filter(models.ApprovedMessage.user_id == user.id).all():
        audio_service.delete_audio(tts.audio_path)
    for model in (models.LearningEvent, models.Correction, models.VocabularyEntry, models.CommMemory,
                  models.ApprovedMessage, models.CommSession, models.UserPreference):
        db.query(model).filter(
            (model.user_id == user.id) if hasattr(model, "user_id") else (model.user_id == user.id)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True}
