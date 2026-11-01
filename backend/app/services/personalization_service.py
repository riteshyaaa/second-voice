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


def recognition_patterns(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    """Recurring speaker-specific recognition-error patterns (Phase 5).

    Built ONLY from user-approved corrections: Correction rows (explicit
    saves) plus LearningEvent correction details (user-approved patterns).
    {from, to, count, sources[]}. A `from` with several distinct `to`
    readings is flagged ambiguous (candidate for clarification, Phase 8).
    No audio analysis, no medical inference — just counted user edits.
    """
    counts: dict[tuple[str, str], dict] = {}

    def valid(frm: str, to: str) -> bool:
        return bool(frm and to and frm != to and len(frm) > 1)

    # Counts come from Correction rows (one per explicit user save), so
    # `count` means "times the user made this correction". LearningEvents
    # only add a "pattern" source label — counting both would double every
    # save, since _learn writes a Correction row and its pattern events
    # together.
    def bucket(frm: str, to: str, source: str, count: int = 1):
        # Key case-insensitively: LearningEvents store lowercased `to`
        # while Corrections keep user casing ("aarav" vs "Aarav").
        # Display prefers the user's own casing.
        key = (frm.lower(), to.lower())
        if key not in counts and count == 0:
            return  # pattern-only leftover with no Correction row: not countable
        e = counts.setdefault(key, {"from": frm.lower(), "to": to, "count": 0, "sources": []})
        e["count"] += count
        if e["to"].islower() and not to.islower():
            e["to"] = to
        if source not in e["sources"]:
            e["sources"].append(source)

    for c in db.query(models.Correction).filter(models.Correction.user_id == user_id).all():
        o, n = (c.original_text or "").split(), (c.corrected_text or "").split()
        if len(o) == len(n):
            for a, b in zip(o, n):
                if a.lower() != b.lower() and valid(a, b):
                    bucket(a, b, "correction")
    for e in db.query(models.LearningEvent).filter(
            models.LearningEvent.user_id == user_id, models.LearningEvent.kind == "correction").all():
        d = e.detail or {}
        frm, to = str(d.get("from") or ""), str(d.get("to") or "")
        if not valid(frm, to):
            continue
        # Pattern events only label; the Correction row already counted.
        bucket(frm, to, "pattern", count=0)
    targets: dict[str, set] = {}
    for (frm, to) in counts:
        targets.setdefault(frm, set()).add(to)
    rows = sorted(counts.values(), key=lambda r: (-r["count"], r["from"]))
    for r in rows:
        r["ambiguous"] = len(targets[r["from"]]) > 1
    return rows[:limit]


VOCAB_CONTEXT_LIMIT = 20
HISTORY_CONTEXT_LIMIT = 5
PATTERN_HINT_LIMIT = 5


def _lang_match(entry_lang: str, language: str) -> bool:
    return entry_lang == language or entry_lang == "hinglish" or language == "hinglish"


def retrieve_context(db: Session, user_id: int, transcript: str, language: str,
                     use_history: bool = True) -> dict:
    """Relevance-scored personal context for one transcript (Phase 6).

    Deterministic approved swaps (vocab_map) are NOT subsetted — every
    user-saved spelling keeps applying (the "correct 10 times" guarantee).
    What IS scored and capped is the LLM context: which canonicals, past
    phrases, and pattern hints earn a slot in the prompt. Scoring:
    approved-correction patterns triggered by transcript tokens first,
    then token overlap, then language match, then recency. Provisional
    entries stay usable but are marked. Returns full provenance
    (context_used) so the user can see why each item was included.
    """
    toks = set(transcript.lower().split())
    vocab_map_full = vocab_map(db, user_id)
    entries = db.query(models.VocabularyEntry).filter(models.VocabularyEntry.user_id == user_id).all()
    patterns = recognition_patterns(db, user_id, limit=50)

    scored: dict[str, tuple[float, str, str]] = {}  # canonical -> (score, reason, kind)
    used: list[dict] = []
    for p in patterns[:PATTERN_HINT_LIMIT * 4]:
        if p["from"] in toks:
            score = 100 + 10 * min(p["count"], 5)
            reason = f"you corrected '{p['from']}' → '{p['to']}' {p['count']}×"
            if p["to"] not in scored or scored[p["to"]][0] < score:
                scored[p["to"]] = (score, reason, "pattern")
    for e in entries:
        overlap = len((set(e.normalized.split()) | set(e.term.lower().split())) & toks)
        if not overlap and e.normalized not in transcript.lower():
            continue
        score = 50 + min(e.times_used, 10) + (20 if _lang_match(e.language, language) else 0)
        reason = f"your saved {e.category} ({e.language})"
        if e.status == "provisional":
            score -= 15
            reason += ", provisional — review suggested"
        if e.term not in scored or scored[e.term][0] < score:
            scored[e.term] = (score, reason, "vocabulary")
    ranked = sorted(scored.items(), key=lambda kv: -kv[1][0])[:VOCAB_CONTEXT_LIMIT]
    spark_vocabulary = [term for term, _ in ranked]
    for term, (score, reason, kind) in ranked:
        used.append({"kind": kind, "ref": term, "score": round(score, 1), "reason": reason})

    history: list[str] = []
    if use_history:
        cands = db.query(models.ApprovedMessage).filter(
            models.ApprovedMessage.user_id == user_id).order_by(
            models.ApprovedMessage.id.desc()).limit(20).all()
        hscored = []
        for i, m in enumerate(cands):
            overlap = len(set(m.final_text.lower().split()) & toks)
            if not overlap:
                continue
            score = 10 * overlap + (20 if m.language == language else 0) + max(0, 10 - i)
            hscored.append((score, m.final_text))
        hscored.sort(key=lambda t: -t[0])
        history = [t for _, t in hscored[:HISTORY_CONTEXT_LIMIT]]
        for h in history:
            used.append({"kind": "history", "ref": h[:80], "score": None,
                         "reason": "your approved phrase resembles this transcript"})

    hints = [f"{p['from']}→{p['to']} ({p['count']}×)" for p in patterns[:PATTERN_HINT_LIMIT] if p["from"] in toks]
    return {"vocab_map": vocab_map_full, "spark_vocabulary": spark_vocabulary,
            "history": history, "pattern_hints": hints, "context_used": used}


def applied_swaps(vocab: dict[str, str], original: str, suggested: str) -> list[dict]:
    """Which vocab swaps actually fired: variant was a token in the original,
    canonical is in the suggestion, variant is no longer a token there.

    Token-based on the variant side: substring matching blinds us exactly
    when it matters most ("arav" is a substring of "Aarav", so a substring
    check would claim the variant is still present after the swap fired).
    """
    o_toks = set(re.findall(r"[A-Za-z\u0900-\u097F']+", (original or "").lower()))
    s_toks = set(re.findall(r"[A-Za-z\u0900-\u097F']+", (suggested or "").lower()))
    s_raw = suggested or ""
    out = []
    for variant, canonical in vocab.items():
        if variant.lower() in o_toks and canonical in s_raw and variant.lower() not in s_toks:
            out.append({"variant": variant, "canonical": canonical})
    return out


def reverted_swap(swap: dict, final_text: str) -> bool:
    """Did the user undo this fired swap: variant token back, canonical gone."""
    f_toks = set(re.findall(r"[A-Za-z\u0900-\u097F']+", (final_text or "").lower()))
    return swap["variant"].lower() in f_toks and swap["canonical"] not in (final_text or "")


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
    patterns = recognition_patterns(db, user_id, limit=5)
    all_patterns = recognition_patterns(db, user_id, limit=1000)
    saves = len(corrections)
    reused = sum(p["count"] for p in all_patterns if p["count"] >= 2)
    false_pers = db.query(models.LearningEvent).filter(
        models.LearningEvent.user_id == user_id,
        models.LearningEvent.kind == "false_personalization").count()
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
        # Phase 5 profile section (additive — old keys untouched)
        "vocab_by_language": dict(Counter(v.language for v in vocab)),
        "provisional_count": sum(1 for v in vocab if v.status == "provisional"),
        "top_patterns": patterns,
        "ambiguous_terms": sorted({p["from"] for p in patterns if p["ambiguous"]}),
        # Phase 6 adaptation metrics (definitions in docs/phase-6-adaptation.md)
        "correction_saves": saves,
        "reused_corrections": reused,
        "reuse_rate": round(reused / max(saves, 1), 3),
        "false_personalizations": false_pers,
        "unwanted_rate": round(false_pers / max(len(suggestions), 1), 3),
    }
