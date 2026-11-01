"""Evaluation endpoints: WER/CER + guard checks + pipeline comparison demo."""
from fastapi import APIRouter, Depends

from .. import models
from ..core.deps import current_user
from ..services import evaluation_service, reconstruction_service
from ..services.personalization_service import vocab_map
from sqlalchemy.orm import Session
from ..core.database import get_db

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.get("/compare")
def compare(reference: str, hypothesis: str, user: models.User = Depends(current_user)):
    return {"wer": evaluation_service.wer(reference, hypothesis),
            "cer": evaluation_service.cer(reference, hypothesis),
            "guards": evaluation_service.guard_report(reference, hypothesis)}


@router.post("/study")
def study(body: dict, user: models.User = Depends(current_user)):
    """Phase 11: speaker-separated personalization study (offline harness)."""
    from ..services import evaluation_harness

    return evaluation_harness.run_study(body)


@router.get("/interaction")
def interaction(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 11: UX interaction metrics from the user's own audit trail."""
    approved = db.query(models.ApprovedMessage).filter_by(user_id=user.id).all()
    corrections = db.query(models.Correction).filter_by(user_id=user.id).count()
    sessions = {s.id: s for s in db.query(models.CommSession).filter_by(user_id=user.id).all()}
    confirms = {c.approved_message_id: c for c in
                db.query(models.ConfirmationEvent).join(
                    models.ApprovedMessage,
                    models.ApprovedMessage.id == models.ConfirmationEvent.approved_message_id)
                .filter(models.ApprovedMessage.user_id == user.id).all()}
    sugg = db.query(models.Suggestion).join(
        models.Transcript, models.Transcript.id == models.Suggestion.transcript_id).join(
        models.AudioAsset, models.AudioAsset.id == models.Transcript.audio_id).join(
        models.CommSession,
        models.CommSession.id == models.AudioAsset.session_id).filter(
        models.CommSession.user_id == user.id).all()
    needs_clar = sum(1 for s in sugg if s.needs_clarification)
    gaps = []
    for a in approved:
        c = confirms.get(a.id)
        s = sessions.get(a.session_id) if a.session_id else None
        if c and s and c.confirmed_at and s.created_at:
            try:
                gaps.append((c.confirmed_at - s.created_at).total_seconds())
            except TypeError:
                pass
    gaps.sort()
    median_gap = gaps[len(gaps) // 2] if gaps else None
    tts = db.query(models.TTSRequest).join(
        models.ApprovedMessage,
        models.ApprovedMessage.id == models.TTSRequest.approved_message_id).filter(
        models.ApprovedMessage.user_id == user.id).all()
    spoken = sum(1 for t in tts if t.status in ("ready", "spoken", "done"))
    return {
        "confirmed_messages": len(approved),
        "edits_per_sentence": round(corrections / max(len(approved), 1), 3),
        "suggestions_total": len(sugg),
        "clarification_rate": round(needs_clar / max(len(sugg), 1), 3),
        "median_confirm_seconds": median_gap,
        "confirm_timed_n": len(gaps),
        "tts_requests": len(tts),
        "tts_success_rate": round(spoken / max(len(tts), 1), 3) if tts else None,
        "note": ("confirm timing uses session start as the earliest "
                 "available anchor (utterance start is not recorded); "
                 "card taps have no session and are excluded from timing."),
    }


@router.post("/pipeline-demo")
async def pipeline_demo(transcript: str, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """The hackathon demo: same sample through 4 pipelines side by side."""
    vocab = vocab_map(db, user.id)
    rules = reconstruction_service.rules_only_suggestion(transcript, {})
    personal = reconstruction_service.rules_only_suggestion(transcript, vocab)
    spark_out, status = await reconstruction_service.suggest(transcript, vocab, [], "en", "")
    context_heavy = dict(personal)
    return {
        "original": transcript,
        "baseline_asr": {"text": transcript, "note": "raw transcript, untouched"},
        "context_heavy": {"text": context_heavy["proposed_text"], "note": "grammar cleanup without personal vocab"},
        "evidence_first": {"text": rules["proposed_text"], "explanation": rules["explanation"],
                           "abstained": rules["abstained"], "meaning_risk": rules["meaning_risk"]},
        "personalized": {"text": spark_out["proposed_text"], "provider": spark_out.get("provider"),
                         "explanation": spark_out["explanation"], "abstained": spark_out.get("abstained", False)},
        "user_in_control": "Nothing above is spoken until you confirm it.",
    }
