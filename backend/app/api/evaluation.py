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
