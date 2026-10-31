"""Speech synthesis — CONFIRMED TEXT ONLY (server-side gate).

POST /speech/synthesize with an approved_message_id that has NO
confirmation_events row → 409 UNCONFIRMED. No frontend flag can bypass this.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import tts_service

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])


@router.get("/voices")
def voices(language: str = "en", user: models.User = Depends(current_user)):
    return {"language": language, "voices": tts_service.voices_for(language)}


@router.post("/synthesize")
async def synthesize(body: schemas.SynthesizeIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    msg = db.query(models.ApprovedMessage).filter(
        models.ApprovedMessage.id == body.approved_message_id,
        models.ApprovedMessage.user_id == user.id).first()
    if msg is None:
        raise HTTPException(status_code=404, detail="Approved message not found")
    conf = db.query(models.ConfirmationEvent).filter(
        models.ConfirmationEvent.approved_message_id == msg.id).first()
    if conf is None:
        # THE gate: unconfirmed text can never be spoken through this API.
        raise HTTPException(status_code=409, detail={
            "code": "UNCONFIRMED", "message": "This text was never confirmed. Confirm it first."})
    voice = body.voice or (db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first().tts_voice if db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first() else "")
    if voice and msg.language in tts_service.VOICES and voice not in tts_service.voices_for(msg.language):
        raise HTTPException(status_code=409, detail={
            "code": "VOICE_UNSUPPORTED", "message": f"Voice {voice} not available for {msg.language}.",
            "supported_voices": tts_service.voices_for(msg.language)})
    path = tts_service.tts_path(user.id, msg.id)
    try:
        info = await tts_service.synthesize(msg.final_text, msg.language, voice, body.speed, path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"code": "TTS_ERROR", "message": str(exc)[:300], "retryable": True})
    tts = models.TTSRequest(approved_message_id=msg.id, provider=info["provider"], voice=info["voice"],
                            language=msg.language, status="ready", audio_path=path, fallback=info.get("fallback", False))
    db.add(tts)
    conf.tts_status = "done"
    db.commit()
    db.refresh(tts)
    return {"tts_request_id": tts.id, "provider": tts.provider, "voice": tts.voice,
            "fallback": tts.fallback, "audio_url": f"/api/v1/speech/audio/{tts.id}",
            "note": info.get("note", "")}


@router.get("/audio/{tts_id}")
def audio(tts_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    tts = (
        db.query(models.TTSRequest)
        .join(models.ApprovedMessage, models.TTSRequest.approved_message_id == models.ApprovedMessage.id)
        .filter(models.TTSRequest.id == tts_id, models.ApprovedMessage.user_id == user.id)
        .first()
    )
    if tts is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(tts.audio_path, media_type="audio/wav", filename=f"secondvoice_{tts_id}.wav")
