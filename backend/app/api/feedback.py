from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import personalization_service
from ..services.personalization_service import normalize_term

router = APIRouter(prefix="/api/v1", tags=["confirmation-feedback"])


def _owned_suggestion(db: Session, user_id: int, suggestion_id: int) -> models.Suggestion:
    s = (
        db.query(models.Suggestion)
        .join(models.Transcript, models.Suggestion.transcript_id == models.Transcript.id)
        .join(models.AudioAsset, models.Transcript.audio_id == models.AudioAsset.id)
        .join(models.CommSession, models.AudioAsset.session_id == models.CommSession.id)
        .filter(models.Suggestion.id == suggestion_id, models.CommSession.user_id == user_id)
        .first()
    )
    if s is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return s


@router.post("/confirmation")
def confirm(body: schemas.ConfirmIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """User authority: creates the approved message + confirmation event (audit)."""
    session_id, transcript_id, suggestion_id = None, body.transcript_id, body.suggestion_id
    if suggestion_id is not None:
        s = _owned_suggestion(db, user.id, suggestion_id)
        transcript_id = s.transcript_id
        session_id = s.transcript.audio.session_id
        s.status = "accepted" if body.final_text.strip() == s.proposed_text.strip() else "edited"
    elif transcript_id is not None:
        t = (
            db.query(models.Transcript)
            .join(models.AudioAsset, models.Transcript.audio_id == models.AudioAsset.id)
            .join(models.CommSession, models.AudioAsset.session_id == models.CommSession.id)
            .filter(models.Transcript.id == transcript_id, models.CommSession.user_id == user.id)
            .first()
        )
        if t is None:
            raise HTTPException(status_code=404, detail="Transcript not found")
        session_id = t.audio.session_id
    else:
        raise HTTPException(status_code=422, detail="Provide suggestion_id or transcript_id")
    msg = models.ApprovedMessage(user_id=user.id, session_id=session_id, suggestion_id=suggestion_id,
                                 transcript_id=transcript_id, final_text=body.final_text.strip(),
                                 language=body.language, source=body.source)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    db.add(models.ConfirmationEvent(approved_message_id=msg.id, language=body.language))
    db.commit()
    if body.save_as_learning:
        _learn(db, user.id, suggestion_id, transcript_id, body.final_text)
    return {"approved_message_id": msg.id, "confirmation": "recorded"}


def _learn(db: Session, user_id: int, suggestion_id: int | None, transcript_id: int | None, final_text: str) -> None:
    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user_id).first()
    if prefs and not prefs.learning_enabled:
        return
    original, suggested = "", ""
    if suggestion_id:
        s = db.query(models.Suggestion).filter(models.Suggestion.id == suggestion_id).first()
        if s:
            suggested = s.proposed_text
            original = s.transcript.text_original
    elif transcript_id:
        t = db.query(models.Transcript).filter(models.Transcript.id == transcript_id).first()
        if t:
            original = t.text_original
    db.add(models.Correction(user_id=user_id, suggestion_id=suggestion_id, original_text=original,
                             suggested_text=suggested, corrected_text=final_text.strip(),
                             kind="edit" if suggested and final_text.strip() != suggested else "accept"))
    personalization_service.learn_correction_pattern(db, user_id, original or final_text, suggested, final_text.strip())


@router.post("/feedback")
def feedback(body: schemas.FeedbackIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    if body.suggestion_id is not None:
        s = _owned_suggestion(db, user.id, body.suggestion_id)
        s.status = "rejected" if body.kind == "reject" else "edited"
        prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
        if body.kind == "reject":
            if prefs and prefs.save_rejections:
                db.add(models.LearningEvent(user_id=user.id, kind="rejection",
                                            detail={"suggestion_id": s.id, "text": s.proposed_text[:200]},
                                            provenance="user-consented"))
        elif body.save:
            _learn(db, user.id, s.id, None, body.final_text)
        db.commit()
        return {"status": s.status}
    if body.transcript_id is not None and body.save:
        _learn(db, user.id, None, body.transcript_id, body.final_text)
        return {"status": "saved"}
    raise HTTPException(status_code=422, detail="Provide suggestion_id or transcript_id")


@router.get("/feedback/stats")
def stats(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return personalization_service.dashboard(db, user.id)


@router.get("/learning")
def learning_events(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.LearningEvent).filter(models.LearningEvent.user_id == user.id).order_by(models.LearningEvent.id.desc()).limit(100).all()
    return [{"id": r.id, "kind": r.kind, "detail": r.detail, "provenance": r.provenance} for r in rows]


@router.delete("/learning/{event_id}")
def delete_event(event_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(models.LearningEvent).filter(models.LearningEvent.id == event_id, models.LearningEvent.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(r)
    db.commit()
    return {"deleted": event_id}
