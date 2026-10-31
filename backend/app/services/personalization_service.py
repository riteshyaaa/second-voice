"""Personal context retrieval + transparent learning (no silent training).

Learning kinds: vocab | language | correction | pattern | rejection.
Rejections are stored ONLY when user_preferences.save_rejections is true and
never become automatic negative rules — they are shown for review.
"""
import re
from collections import Counter

from sqlalchemy.orm import Session

from .. import models

STOP = {"the", "a", "an", "to", "i", "me", "my", "please", "hai", "aur", "hai,"}


def normalize_term(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower())


def vocab_map(db: Session, user_id: int) -> dict[str, str]:
    """Approved spellings as {variant -> canonical}.

    Covers the core example: user corrects "Arav" → "Aarav" ten times; the
    correction rows yield alias {"arav": "Aarav"} so the next "Arav" is
    offered as "Aarav" — still rejectable by the user."""
    entries = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.user_id == user_id).all()
    mapping = {e.normalized: e.term for e in entries}
    for c in db.query(models.Correction).filter(models.Correction.user_id == user_id).all():
        o, n = (c.original_text or "").split(), (c.corrected_text or "").split()
        if len(o) == len(n):
            for a, b in zip(o, n):
                if a.lower() != b.lower() and len(a) > 1:
                    mapping.setdefault(a.lower(), b)
    for e in db.query(models.LearningEvent).filter(
            models.LearningEvent.user_id == user_id, models.LearningEvent.kind == "correction").all():
        d = e.detail or {}
        if d.get("from") and d.get("to"):
            mapping.setdefault(str(d["from"]).lower(), str(d["to"]))
    return mapping


def upsert_vocab(db: Session, user_id: int, term: str, language: str, category: str = "word") -> models.VocabularyEntry:
    norm = normalize_term(term)
    existing = (
        db.query(models.VocabularyEntry)
        .filter(models.VocabularyEntry.user_id == user_id, models.VocabularyEntry.normalized == norm)
        .first()
    )
    if existing:
        existing.times_used += 1
        db.commit()
        return existing
    entry = models.VocabularyEntry(user_id=user_id, term=term.strip(), normalized=norm, language=language, category=category, times_used=1)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.add(models.LearningEvent(user_id=user_id, kind="vocab", detail={"term": term, "language": language}))
    db.commit()
    return entry


def learn_correction_pattern(db: Session, user_id: int, original: str, suggested: str, corrected: str) -> None:
    """Record reusable correction patterns (word-level swaps seen repeatedly)."""
    o, c = original.lower().split(), corrected.lower().split()
    if len(o) == len(c):
        swaps = [(a, b) for a, b in zip(o, c) if a != b][:3]
        for frm, to in swaps:
            if frm in STOP or to in STOP:
                continue
            db.add(models.LearningEvent(user_id=user_id, kind="correction",
                                        detail={"from": frm, "to": to, "context": corrected[:200]}))
    # pattern: repeated user phrasing
    db.add(models.LearningEvent(user_id=user_id, kind="pattern", detail={"phrase": corrected[:200]}))
    db.commit()


def recent_approved(db: Session, user_id: int, limit: int = 10) -> list[str]:
    rows = (
        db.query(models.ApprovedMessage)
        .filter(models.ApprovedMessage.user_id == user_id)
        .order_by(models.ApprovedMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [r.final_text for r in reversed(rows)]


def dashboard(db: Session, user_id: int) -> dict:
    vocab = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.user_id == user_id).all()
    corrections = db.query(models.Correction).filter(models.Correction.user_id == user_id).all()
    suggestions = (
        db.query(models.Suggestion)
        .join(models.Transcript, models.Suggestion.transcript_id == models.Transcript.id)
        .join(models.AudioAsset, models.Transcript.audio_id == models.AudioAsset.id)
        .join(models.CommSession, models.AudioAsset.session_id == models.CommSession.id)
        .filter(models.CommSession.user_id == user_id)
        .all()
    )
    langs = Counter(a.language for a in db.query(models.ApprovedMessage).filter(models.ApprovedMessage.user_id == user_id).all())
    accepted = sum(1 for s in suggestions if s.status in ("accepted", "edited"))
    return {
        "words_learned": len(vocab),
        "corrections_approved": len(corrections),
        "suggestions_accepted": accepted,
        "suggestions_rejected": sum(1 for s in suggestions if s.status == "rejected"),
        "suggestions_total": len(suggestions),
        "acceptance_rate": round(accepted / max(len(suggestions), 1), 3),
        "languages_used": dict(langs),
        "frequent_phrases": [{"phrase": text, "count": n} for text, n in Counter(c.corrected_text for c in corrections).most_common(5)],
        "top_vocabulary": [{"term": v.term, "times_used": v.times_used, "times_corrected": v.times_corrected} for v in sorted(vocab, key=lambda v: -v.times_used)[:10]],
    }
