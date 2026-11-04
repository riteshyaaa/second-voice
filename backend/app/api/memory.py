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
def list_vocab(user: models.User = Depends(current_user), db: Session = Depends(get_db),
               language: str | None = None):
    q = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.user_id == user.id)
    if language:
        q = q.filter(models.VocabularyEntry.language == language)
    rows = q.order_by(models.VocabularyEntry.term).all()
    return [{"id": r.id, "term": r.term, "language": r.language, "category": r.category,
             "source": r.source, "status": r.status, "version": r.version,
             "times_used": r.times_used, "times_corrected": r.times_corrected} for r in rows]


@router.post("/vocabulary")
def add_vocab(body: schemas.VocabIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    entry = personalization_service.upsert_vocab(db, user.id, body.term, body.language, body.category)
    return {"id": entry.id, "term": entry.term}


@router.patch("/vocabulary/{entry_id}")
def edit_vocab(entry_id: int, body: schemas.VocabPatch, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 5: every learned entry is editable (edits bump version)."""
    r = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.id == entry_id, models.VocabularyEntry.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.add(models.ProfileRevision(user_id=user.id, entity="vocab", entity_id=r.id,
                                  snapshot={"term": r.term, "language": r.language,
                                            "category": r.category, "status": r.status,
                                            "version": r.version}))
    if body.term is not None:
        r.term = body.term.strip()
        r.normalized = normalize_term(body.term)
    if body.language is not None:
        r.language = body.language
    if body.category is not None:
        r.category = body.category
    if body.status is not None:
        if body.status not in ("approved", "provisional"):
            raise HTTPException(status_code=422, detail="status must be approved|provisional")
        r.status = body.status
    r.version += 1
    db.commit()
    return {"id": r.id, "term": r.term, "version": r.version, "status": r.status}


@router.get("/vocabulary/{entry_id}/revisions")
def vocab_revisions(entry_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 6: pre-edit snapshots for rollback review."""
    rows = db.query(models.ProfileRevision).filter(
        models.ProfileRevision.user_id == user.id, models.ProfileRevision.entity == "vocab",
        models.ProfileRevision.entity_id == entry_id).order_by(models.ProfileRevision.id.desc()).all()
    return [{"id": x.id, "snapshot": x.snapshot, "created_at": x.created_at} for x in rows]


@router.post("/vocabulary/{entry_id}/rollback/{rev_id}")
def vocab_rollback(entry_id: int, rev_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 6: restore a snapshot (journals pre-restore state, bumps version)."""
    r = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.id == entry_id, models.VocabularyEntry.user_id == user.id).first()
    rev = db.query(models.ProfileRevision).filter(
        models.ProfileRevision.id == rev_id, models.ProfileRevision.user_id == user.id,
        models.ProfileRevision.entity == "vocab", models.ProfileRevision.entity_id == entry_id).first()
    if r is None or rev is None:
        raise HTTPException(status_code=404, detail="Entry or revision not found")
    db.add(models.ProfileRevision(user_id=user.id, entity="vocab", entity_id=r.id,
                                  snapshot={"term": r.term, "language": r.language,
                                            "category": r.category, "status": r.status,
                                            "version": r.version}))
    snap = rev.snapshot or {}
    r.term = snap.get("term", r.term)
    r.normalized = normalize_term(r.term)
    r.language = snap.get("language", r.language)
    r.category = snap.get("category", r.category)
    r.status = snap.get("status", r.status)
    r.version += 1
    db.commit()
    return {"id": r.id, "term": r.term, "version": r.version}


@router.delete("/vocabulary/{entry_id}")
def delete_vocab(entry_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.id == entry_id, models.VocabularyEntry.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(r)
    db.commit()
    return {"deleted": entry_id}


# --- Memory ---
@router.get("/personalization/review")
def personalization_review(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 7: everything the system learned about this user, with the
    actions each item supports. Correction patterns are a ranked derived
    view (nothing stored separately); calibration is storage-only."""
    return personalization_service.review(db, user.id)


@router.get("/memory")
def list_memory(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.CommMemory).filter(models.CommMemory.user_id == user.id).order_by(models.CommMemory.id.desc()).limit(100).all()
    return [{"id": r.id, "kind": r.kind, "content": r.content, "language": r.language,
             "source": r.source, "provenance": r.provenance, "version": r.version} for r in rows]


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


@router.patch("/memory/{entry_id}")
def edit_memory(entry_id: int, body: schemas.MemoryPatch, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Phase 5: every saved entry is editable (edits bump version)."""
    r = db.query(models.CommMemory).filter(models.CommMemory.id == entry_id, models.CommMemory.user_id == user.id).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.add(models.ProfileRevision(user_id=user.id, entity="memory", entity_id=r.id,
                                  snapshot={"kind": r.kind, "content": r.content,
                                            "language": r.language, "version": r.version}))
    if body.kind is not None:
        r.kind = body.kind
    if body.content is not None:
        r.content = body.content
    if body.language is not None:
        r.language = body.language
    r.version += 1
    db.commit()
    return {"id": r.id, "version": r.version}


@router.get("/memory/{entry_id}/revisions")
def memory_revisions(entry_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(models.ProfileRevision).filter(
        models.ProfileRevision.user_id == user.id, models.ProfileRevision.entity == "memory",
        models.ProfileRevision.entity_id == entry_id).order_by(models.ProfileRevision.id.desc()).all()
    return [{"id": x.id, "snapshot": x.snapshot, "created_at": x.created_at} for x in rows]


@router.post("/memory/{entry_id}/rollback/{rev_id}")
def memory_rollback(entry_id: int, rev_id: int, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.query(models.CommMemory).filter(models.CommMemory.id == entry_id, models.CommMemory.user_id == user.id).first()
    rev = db.query(models.ProfileRevision).filter(
        models.ProfileRevision.id == rev_id, models.ProfileRevision.user_id == user.id,
        models.ProfileRevision.entity == "memory", models.ProfileRevision.entity_id == entry_id).first()
    if r is None or rev is None:
        raise HTTPException(status_code=404, detail="Entry or revision not found")
    db.add(models.ProfileRevision(user_id=user.id, entity="memory", entity_id=r.id,
                                  snapshot={"kind": r.kind, "content": r.content,
                                            "language": r.language, "version": r.version}))
    snap = rev.snapshot or {}
    r.kind = snap.get("kind", r.kind)
    r.content = snap.get("content", r.content)
    r.language = snap.get("language", r.language)
    r.version += 1
    db.commit()
    return {"id": r.id, "version": r.version}


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
    cards = db.query(models.CommCard).filter(models.CommCard.user_id == user.id).all()
    return {"vocabulary": vocab, "memory": memory,
            "approved": [{"text": a.final_text, "language": a.language} for a in approved],
            "cards": [{"label": c.label, "label_native": c.label_native, "language": c.language,
                       "emoji": c.emoji, "category": c.category, "phrase": c.phrase,
                       "favorite": c.favorite} for c in cards]}
