from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import muse_wonder_service, personalization_service, reconstruction_service

router = APIRouter(prefix="/api/v1", tags=["reconstruction"])


def _owned_transcript(db: Session, user_id: int, transcript_id: int) -> models.Transcript:
    t = (
        db.query(models.Transcript)
        .join(models.AudioAsset, models.Transcript.audio_id == models.AudioAsset.id)
        .join(models.CommSession, models.AudioAsset.session_id == models.CommSession.id)
        .filter(models.Transcript.id == transcript_id, models.CommSession.user_id == user_id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return t


@router.post("/reconstruction")
async def reconstruct(body: schemas.ReconstructIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    t = _owned_transcript(db, user.id, body.transcript_id)
    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    vocab = personalization_service.vocab_map(db, user.id)
    history = personalization_service.recent_approved(db, user.id) if (prefs is None or prefs.use_history) else []
    # Evidence hierarchy: the AUDIO is primary; this transcript is the ASR
    # system's interpretation of it. Say so explicitly, with provenance.
    conf = f"word-level confidence {t.confidence}" if t.confidence is not None else "no word-level confidence scores"
    reliability = (f"Source: {t.provider}/{t.model_version or 'unknown version'}; {conf}; "
                   f"detected language {t.language}. The original audio is the primary evidence — "
                   f"this transcript is an imperfect interpretation of it.")
    out, status = await reconstruction_service.suggest(
        t.text_original, vocab, history, t.language, body.user_request, reliability)
    row = models.Suggestion(
        transcript_id=t.id, proposed_text=out["proposed_text"], explanation=out["explanation"],
        changed_words=out["changed_words"], alternatives=out["alternatives"],
        needs_clarification=out["needs_clarification"], clarification_question=out["clarification_question"],
        abstained=out["abstained"], provider=out.get("provider", status.name),
        model_version=out.get("model_version", status.model_version),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"suggestion_id": row.id, **out, "provider": row.provider, "model_version": row.model_version,
            "routed_to_wonder": False}


@router.post("/reconstruction/alternatives")
def alternatives(body: schemas.AlternativesIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    t = _owned_transcript(db, user.id, body.transcript_id)
    vocab = personalization_service.vocab_map(db, user.id)
    return {"alternatives": reconstruction_service.alternatives(t.text_original, vocab, body.count)}


@router.post("/reconstruction/clarify/{suggestion_id}")
async def clarify(suggestion_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    s = (
        db.query(models.Suggestion)
        .join(models.Transcript, models.Suggestion.transcript_id == models.Transcript.id)
        .join(models.AudioAsset, models.Transcript.audio_id == models.AudioAsset.id)
        .join(models.CommSession, models.AudioAsset.session_id == models.CommSession.id)
        .filter(models.Suggestion.id == suggestion_id, models.CommSession.user_id == user.id)
        .first()
    )
    if s is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    history = personalization_service.recent_approved(db, user.id)
    try:
        raw, status = await muse_wonder_service.resolve(
            s.transcript.text_original, [s.proposed_text] + (s.alternatives or []), history)
    except RuntimeError as exc:
        # Labelled: Wonder unavailable → return the stored clarification question.
        return {"provider": "dev-fallback", "ranked": [], "contradiction": "",
                "clarification_question": s.clarification_question or "Could you say the key word once more?",
                "note": f"Muse Wonder unavailable: {exc}"}
    return {"provider": status.name, **raw}
