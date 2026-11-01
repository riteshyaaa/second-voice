"""Visual communication cards + optional illustration seam (Phase 9).

Every card tap speaks through the SAME confirmation workflow: tapping is
an explicit user selection, so speak creates the ApprovedMessage +
ConfirmationEvent, then delegates to the standard synthesis endpoint
(the server-side gate still applies — no path speaks unconfirmed text).

Illustrations: Muse Image request/response shapes could not be verified
against official Meta API documentation (only third-party wrappers and
cookbook fragments found, 2026-11-01). The seam exists
(muse_image_service + image_url + /illustrate), but generation stays a
labelled 409 until a verified provider is wired. Cards are fully useful
without it: emoji anchors + multilingual labels carry the visual load.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from .speech import synthesize as _synthesize

router = APIRouter(prefix="/api/v1/cards", tags=["cards"])

CATEGORIES = {"needs", "requests", "feelings", "questions", "emergency", "personal"}

# Seed board: (label, label_native|None, language, emoji, category, phrase).
# Native labels only where the wording is already verified in this repo
# (phrasebook mappings, validation corpus) or standard undisputed forms.
SEEDS: list[tuple] = [
    ("I need help.", "मुझे मदद चाहिए", "hi", "🙏", "needs", "I need help."),
    ("I need water.", "मुझे पानी चाहिए", "hi", "💧", "needs", "I need water."),
    ("I need the bathroom.", None, "en", "🚻", "needs", "I need the bathroom."),
    ("Please wait.", "कृपया प्रतीक्षा करें", "hi", "⏳", "requests", "Please wait."),
    ("Please repeat that.", None, "en", "🔁", "requests", "Please repeat that."),
    ("I am in pain.", "मुझे दर्द हो रहा है", "hi", "😖", "feelings", "I am in pain."),
    ("I am tired.", None, "en", "😮‍💨", "feelings", "I am tired."),
    ("What time is it?", None, "en", "🕐", "questions", "What time is it?"),
    ("Emergency! Please call for help.", "आपातकाल! कृपया मदद बुलाएँ", "hi", "🚨", "emergency",
     "Emergency! Please call for help."),
    ("Thank you.", "धन्यवाद", "hi", "🙏", "personal", "Thank you."),
    ("Yes.", "हाँ", "hi", "👍", "personal", "Yes."),
    ("No.", "नहीं", "hi", "👎", "personal", "No."),
]


def _shape(c: models.CommCard) -> dict:
    return {"id": c.id, "label": c.label, "label_native": c.label_native, "language": c.language,
            "emoji": c.emoji, "category": c.category, "phrase": c.phrase,
            "favorite": c.favorite, "image_url": c.image_url}


def seed_defaults(db: Session, user_id: int) -> None:
    if db.query(models.CommCard).filter(models.CommCard.user_id == user_id).first():
        return
    for label, native, lang, emoji, cat, phrase in SEEDS:
        db.add(models.CommCard(user_id=user_id, label=label, label_native=native, language=lang,
                               emoji=emoji, category=cat, phrase=phrase))
    db.commit()


@router.get("")
def list_cards(user: models.User = Depends(current_user), db: Session = Depends(get_db),
               category: str | None = None, favorites: bool = False):
    seed_defaults(db, user.id)
    q = db.query(models.CommCard).filter(models.CommCard.user_id == user.id)
    if category:
        q = q.filter(models.CommCard.category == category)
    if favorites:
        q = q.filter(models.CommCard.favorite.is_(True))
    return [_shape(c) for c in q.order_by(models.CommCard.id).all()]


@router.post("")
def create_card(body: schemas.CardIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of {sorted(CATEGORIES)}")
    c = models.CommCard(user_id=user.id, label=body.label.strip(), label_native=body.label_native,
                        language=body.language, emoji=body.emoji or "", category=body.category,
                        phrase=body.phrase.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _shape(c)


@router.patch("/{card_id}")
def edit_card(card_id: int, body: schemas.CardPatch, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.query(models.CommCard).filter(models.CommCard.id == card_id, models.CommCard.user_id == user.id).first()
    if c is None:
        raise HTTPException(status_code=404, detail="Card not found")
    if body.label is not None:
        c.label = body.label.strip()
    if body.label_native is not None:
        c.label_native = body.label_native
    if body.language is not None:
        c.language = body.language
    if body.emoji is not None:
        c.emoji = body.emoji
    if body.category is not None:
        if body.category not in CATEGORIES:
            raise HTTPException(status_code=422, detail=f"category must be one of {sorted(CATEGORIES)}")
        c.category = body.category
    if body.phrase is not None:
        c.phrase = body.phrase.strip()
    if body.favorite is not None:
        c.favorite = body.favorite
    db.commit()
    return _shape(c)


@router.delete("/{card_id}")
def delete_card(card_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.query(models.CommCard).filter(models.CommCard.id == card_id, models.CommCard.user_id == user.id).first()
    if c is None:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(c)
    db.commit()
    return {"deleted": card_id}


@router.post("/{card_id}/speak")
async def speak_card(card_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Tap-to-speak: the tap IS the confirmation (explicit selection), so
    this mints the ApprovedMessage + ConfirmationEvent and reuses the
    standard synthesis path — the gate still sees a confirmed row."""
    c = db.query(models.CommCard).filter(models.CommCard.id == card_id, models.CommCard.user_id == user.id).first()
    if c is None:
        raise HTTPException(status_code=404, detail="Card not found")
    msg = models.ApprovedMessage(user_id=user.id, session_id=None, suggestion_id=None,
                                 transcript_id=None, final_text=c.phrase, language=c.language, source="card")
    db.add(msg)
    db.commit()
    db.refresh(msg)
    db.add(models.ConfirmationEvent(approved_message_id=msg.id, language=c.language))
    db.commit()
    return await _synthesize(schemas.SynthesizeIn(approved_message_id=msg.id), user, db)


@router.post("/{card_id}/illustrate")
def illustrate_card(card_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Optional AI illustration — currently unavailable (honest 409).

    Muse Image request/response shapes are unverified against official
    docs, so no call is attempted. See muse_image_service for status.
    """
    from ..services import muse_image_service

    c = db.query(models.CommCard).filter(models.CommCard.id == card_id, models.CommCard.user_id == user.id).first()
    if c is None:
        raise HTTPException(status_code=404, detail="Card not found")
    try:
        return {"image_url": muse_image_service.generate_sync(c)}
    except muse_image_service.ImageUnavailable as exc:
        raise HTTPException(status_code=409, detail={"code": "IMAGE_UNAVAILABLE", "message": str(exc)})
