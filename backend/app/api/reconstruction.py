from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified as attributes_flag_modified

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import clarification_service, language_service, muse_wonder_service, personalization_service, reconstruction_service, uncertainty_service

router = APIRouter(prefix="/api/v1", tags=["reconstruction"])


def _questions_for(db: Session, user_id: int, s: models.Suggestion) -> list[dict]:
    t = s.transcript
    ev = t.evidence or {}
    providers = ev.get("providers", []) or []
    return clarification_service.build_questions(
        t.text_original, ev,
        {"alternatives": s.alternatives, "needs_clarification": s.needs_clarification,
         "clarification_question": s.clarification_question},
        personalization_service.recognition_patterns(db, user_id, limit=50),
        t.provider, providers[1].get("name") if len(providers) > 1 else None)


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
    ctx = personalization_service.retrieve_context(
        db, user.id, t.text_original, t.language,
        use_history=(prefs is None or prefs.use_history))
    ctx["uncertainty"] = (t.evidence or {}).get("uncertainty", [])
    ctx["secondary_text"] = (t.evidence or {}).get("secondary_text")
    ctx["language_spans"] = language_service.detect_language(t.text_original).get("spans", [])
    vocab, history = ctx["vocab_map"], ctx["history"]
    # Evidence hierarchy: the AUDIO is primary; this transcript is the ASR
    # system's interpretation of it. Phase 3: the reliability note is built
    # from the stored evidence package (observables only), not hand-written.
    ev = t.evidence or {}
    indicators = ev.get("uncertainty")
    if indicators is None:  # pre-Phase-3 rows: derive from what's stored
        indicators = uncertainty_service.summarize(
            {"text": t.text_original, "language": t.language, "provider": t.provider},
            {"verdict": "single"}, None)
    reliability = uncertainty_service.reliability_text(t.provider, t.model_version, t.language, indicators, t.confidence)
    out, status = await reconstruction_service.suggest(
        t.text_original, vocab, history, t.language, body.user_request, reliability, context=ctx)
    row = models.Suggestion(
        transcript_id=t.id, proposed_text=out["proposed_text"], explanation=out["explanation"],
        changed_words=out["changed_words"], alternatives=out["alternatives"],
        needs_clarification=out["needs_clarification"], clarification_question=out["clarification_question"],
        abstained=out["abstained"], evidence_for=out.get("evidence_for", []),
        evidence_missing=out.get("evidence_missing", []),
        candidates=out.get("candidates", []),
        provider=out.get("provider", status.name),
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


@router.get("/reconstruction/questions/{suggestion_id}")
def clarify_questions(suggestion_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 8: targeted clarification questions for one suggestion.

    Built deterministically from stored evidence — engine disagreements,
    ambiguous personal patterns, language mismatch. Includes the audio
    replay URL (full clip; segment timings don't exist) and the current
    answers so clients can render state.
    """
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
    t = s.transcript
    questions = _questions_for(db, user.id, s)
    answers = s.clarification_answers or {}
    return {"suggestion_id": s.id,
            "audio_url": f"/api/v1/audio/sessions/{t.audio.session_id}/audio/{t.audio_id}",
            "questions": questions,
            "answers": answers,
            "unresolved_blockers": [q["id"] for q in clarification_service.unresolved_blockers(questions, answers)]}


@router.post("/reconstruction/questions/{suggestion_id}/answer")
def answer_question(suggestion_id: int, body: schemas.ClarifyAnswerIn,
                    user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 8: answer or explicitly skip one question."""
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
    questions = _questions_for(db, user.id, s)
    q = next((x for x in questions if x["id"] == body.question_id), None)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found (it may have resolved)")
    try:
        record = clarification_service.apply_answer(q, body.kind, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    answers = dict(s.clarification_answers or {})
    answers[q["id"]] = record
    s.clarification_answers = answers
    attributes_flag_modified(s, "clarification_answers")
    db.commit()
    remaining = clarification_service.unresolved_blockers(questions, answers)
    return {"question_id": q["id"], "recorded": record,
            "unresolved_blockers": [x["id"] for x in remaining]}


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
