from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.database import get_db
from ..core.deps import current_user
from ..services import personalization_service
from ..services.personalization_service import normalize_term

router = APIRouter(prefix="/api/v1", tags=["vocabulary-memory"])


# --- Vocabulary ---
@router.get("/vocabulary")
def list_vocab(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.user_id == user.id).order_by(models.VocabularyEntry.term).all()
    return [{"id": r.id, "term": r.term, "language": r.language, "category": r.category,
             "times_used": r.times_used, "times_corrected": r.times_corrected} for r in rows]


@router.post("/vocabulary")
def add_vocab(body: schemas.VocabIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    entry = personalization_service.upsert_vocab(db, user.id, body.term, body.language, body.category)
    return {"id": entry.id, "term": entry.term}


@router.delete("/vocabulary/{entry_id}")
def delete_vocab(entry_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.id == entry_id, models.VocabularyEntry.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(r)
    db.commit()
    return {"deleted": entry_id}


# --- Memory ---
@router.get("/memory")
def list_memory(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.CommMemory).filter(models.CommMemory.user_id == user.id).order_by(models.CommMemory.id.desc()).limit(100).all()
    return [{"id": r.id, "kind": r.kind, "content": r.content, "language": r.language, "version": r.version} for r in rows]


@router.post("/memory")
def add_memory(body: schemas.MemoryIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    prefs = db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).first()
    if prefs and not prefs.learning_enabled and body.kind != "phrase":
        raise HTTPException(status_code=403, detail="Learning is disabled in preferences")
    m = models.CommMemory(user_id=user.id, kind=body.kind, content=body.content, language=body.language)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id}


@router.delete("/memory/{entry_id}")
def delete_memory(entry_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(models.CommMemory).filter(models.CommMemory.id == entry_id, models.CommMemory.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(r)
    db.commit()
    return {"deleted": entry_id}


@router.post("/memory/export")
def export_memory(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    vocab = list_vocab(user, db)
    memory = list_memory(user, db)
    approved = db.query(models.ApprovedMessage).filter(models.ApprovedMessage.user_id == user.id).all()
    return {"vocabulary": vocab, "memory": memory,
            "approved": [{"text": a.final_text, "language": a.language} for a in approved]}
