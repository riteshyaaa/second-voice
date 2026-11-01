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
    # Phase 8: high-impact blockers must be answered or explicitly skipped
    # before confirmation — unless the user explicitly forces (audited in
    # the response; user authority always wins).
    from .reconstruction import _questions_for
    from ..services import clarification_service as _cs
    if suggestion_id is not None:
        qs = _questions_for(db, user.id, s)
        blockers = _cs.unresolved_blockers(qs, s.clarification_answers)
    else:
        t0 = db.query(models.Transcript).filter(models.Transcript.id == transcript_id).first()
        ev0 = (t0.evidence or {}) if t0 else {}
        qs = _cs.build_questions(t0.text_original if t0 else "", ev0, None,
                                 personalization_service.recognition_patterns(db, user.id, limit=50),
                                 t0.provider if t0 else "", None)
        blockers = _cs.unresolved_blockers(qs, {})
    if blockers and not body.force:
        raise HTTPException(status_code=409, detail={
            "code": "CLARIFICATION_PENDING",
            "message": "High-impact ambiguity is unresolved. Answer or skip each blocker, or confirm with force=true.",
            "blockers": blockers,
        })
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
    out = {"approved_message_id": msg.id, "confirmation": "recorded"}
    if blockers and body.force:
        out["forced"] = True
        out["forced_over"] = [b["id"] for b in blockers]
    return out


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
    # Phase 6: did the user revert a personalization swap? If our applied
    # canonical is gone and the original variant is back, the suggestion —
    # not the user — was wrong. Record it so the dashboard can show
    # unwanted-personalization rates.
    if suggested:
        vmap = personalization_service.vocab_map(db, user_id)
        final = final_text.strip()
        for swap in personalization_service.applied_swaps(vmap, original, suggested):
            if personalization_service.reverted_swap(swap, final):
                db.add(models.LearningEvent(user_id=user_id, kind="false_personalization",
                                            detail={"variant": swap["variant"], "canonical": swap["canonical"],
                                                    "suggestion_id": suggestion_id},
                                            provenance="user-correction"))
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


@router.get("/learning/patterns")
def learning_patterns(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 5: recurring speaker-specific recognition-error patterns.

    Counted only from user-approved corrections — never inferred from raw
    audio, never a medical claim. `ambiguous` marks terms with competing
    readings (clarification candidates)."""
    return personalization_service.recognition_patterns(db, user.id)


@router.delete("/learning/{event_id}")
def delete_event(event_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(models.LearningEvent).filter(models.LearningEvent.id == event_id, models.LearningEvent.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(r)
    db.commit()
    return {"deleted": event_id}
