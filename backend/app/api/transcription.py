from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..core.ratelimit import rate_limit
from ..services import audio_service, language_service, meta_asr_service

router = APIRouter(prefix="/api/v1", tags=["transcription"])


def _session_owned(db: Session, user_id: int, audio_id: int) -> models.AudioAsset:
    audio = (
        db.query(models.AudioAsset)
        .join(models.CommSession, models.AudioAsset.session_id == models.CommSession.id)
        .filter(models.AudioAsset.id == audio_id, models.CommSession.user_id == user_id)
        .first()
    )
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    return audio


@router.post("/transcription")
async def transcribe(body: schemas.TranscribeIn, request: Request, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(request)
    return await _do_transcribe(body, user, db)


async def _do_transcribe(body: schemas.TranscribeIn, user: models.User, db: Session):
    audio = _session_owned(db, user.id, body.audio_id)
    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    data = audio_service.load_audio(audio.file_path, prefs.audio_retention_days if prefs else 30)
    vocab_terms = [v.term for v in db.query(models.VocabularyEntry).filter(models.VocabularyEntry.user_id == user.id).all()]
    result = await meta_asr_service.transcribe(data, audio.mime, body.language_hint, vocab_terms + body.keywords)
    text = (result.get("text") or "").strip()
    if result.get("fallback") and not text:
        # Labelled dev path: allow manual transcript so the workflow still works.
        raise HTTPException(status_code=409, detail={
            "code": "ASR_FALLBACK_NO_KEY",
            "message": "META_API_KEY is not configured, so live transcription is unavailable. Submit manual_transcript instead.",
            "provider": "dev-fallback",
        })
    lang = result.get("language") or language_service.detect_language(text)["language"]
    if body.language_hint not in ("auto",) and result.get("fallback"):
        lang = body.language_hint
    t = models.Transcript(audio_id=audio.id, text_original=text, language=lang,
                          provider=result["provider"], model_version=result.get("model_version", ""),
                          confidence=result.get("confidence"), timestamps=result.get("timestamps"))
    db.add(t)
    db.commit()
    db.refresh(t)
    detected = language_service.detect_language(text)
    return {"transcript_id": t.id, "text_original": text, "language": lang,
            "provider": t.provider, "model_version": t.model_version,
            "detection": detected, "fallback": result.get("fallback", False)}


@router.post("/transcription/manual")
def transcribe_manual(audio_id: int, manual_transcript: str, language: str = "en",
                      user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Honest manual path for dev-fallback / mic-less demos. Labelled provider."""
    audio = _session_owned(db, user.id, audio_id)
    _ = audio
    text = " ".join(manual_transcript.split())
    if not text:
        raise HTTPException(status_code=422, detail="manual_transcript is empty")
    t = models.Transcript(audio_id=audio_id, text_original=text, language=language,
                          provider="manual-entry", model_version="user-typed-1")
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"transcript_id": t.id, "text_original": text, "language": language,
            "provider": "manual-entry", "detection": language_service.detect_language(text)}


@router.post("/transcription/file")
async def transcribe_file(file: UploadFile, session_id: int, language_hint: str = "auto",
                          user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    data = await file.read()
    s = db.query(models.CommSession).filter(models.CommSession.id == session_id, models.CommSession.user_id == user.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    path, duration = audio_service.save_audio(user.id, session_id, data, file.content_type or "audio/wav")
    asset = models.AudioAsset(session_id=session_id, file_path=path, mime=file.content_type or "audio/wav", duration_s=duration)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return await _do_transcribe(schemas.TranscribeIn(audio_id=asset.id, language_hint=language_hint), user, db)
