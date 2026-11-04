"""Phase 7: personalization review surface + calibration storage."""
from fastapi.testclient import TestClient

from app import models
from app.core.database import SessionLocal, init_db
from app.main import app
from app.services import personalization_service as ps

init_db()
client = TestClient(app)


def _user(email):
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login",
                        json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def _uid(email):
    db = SessionLocal()
    try:
        return db.query(models.User).filter(models.User.email == email).first().id
    finally:
        db.close()


def test_review_empty_for_new_user():
    h, _ = _user("rev-empty@test.app")
    body = client.get("/api/v1/personalization/review", headers=h).json()
    assert body["vocabulary"] == [] and body["correction_patterns"] == []
    assert body["suggestion_stats"]["suggestions_total"] == 0
    assert body["calibration_clips"] == [] and body["calibration_note"]


def test_review_ranks_patterns_and_lists_actions():
    h, email = _user("rev-full@test.app")
    uid = _uid(email)
    db = SessionLocal()
    try:
        db.add(models.VocabularyEntry(user_id=uid, term="Aarav", normalized="aarav",
                                      language="en", category="name"))
        for _ in range(3):
            db.add(models.Correction(user_id=uid, original_text="Call Arav tomorrow",
                                     suggested_text="Call Arav tomorrow.",
                                     corrected_text="Call Aarav tomorrow"))
        db.add(models.Correction(user_id=uid, original_text="I want meet doctor",
                                 suggested_text="I want meet doctor.",
                                 corrected_text="I want to meet doctor"))
        # one `from` with two targets -> ambiguous
        db.add(models.Correction(user_id=uid, original_text="Call Arav tomorrow",
                                 suggested_text="Call Aarav tomorrow",
                                 corrected_text="Call Arjun tomorrow"))
        db.add(models.CommMemory(user_id=uid, kind="phrase", content="I need water",
                                 language="en"))
        db.commit()
    finally:
        db.close()
    body = client.get("/api/v1/personalization/review", headers=h).json()
    assert body["vocabulary"][0]["term"] == "Aarav"
    assert body["vocabulary"][0]["actions"] == ["edit", "delete", "rollback"]
    pats = body["correction_patterns"]
    assert [p["rank"] for p in pats] == sorted(p["rank"] for p in pats)
    assert pats[0]["from"] == "arav" and pats[0]["count"] == 3
    assert any(p["ambiguous"] for p in pats if p["from"] == "arav")
    assert all(p["actions"] == [] and p["note"] for p in pats)
    assert body["memory"][0]["content"] == "I need water"
    assert body["suggestion_stats"]["suggestions_total"] == 0

    # isolation: another user sees none of this
    h2, _ = _user("rev-other@test.app")
    other = client.get("/api/v1/personalization/review", headers=h2).json()
    assert other["vocabulary"] == [] and other["correction_patterns"] == []


def test_review_reflects_rejection_stats():
    h, email = _user("rev-rej@test.app")
    uid = _uid(email)
    db = SessionLocal()
    try:
        db.add(models.LearningEvent(user_id=uid, kind="false_personalization",
                                    detail={"note": "t"}))
        db.commit()
    finally:
        db.close()
    stats = client.get("/api/v1/personalization/review", headers=h).json()["suggestion_stats"]
    assert stats["false_personalizations"] == 1


def test_calibration_clip_defaults_to_no_consent():
    _, email = _user("rev-cal@test.app")
    uid = _uid(email)
    db = SessionLocal()
    try:
        c = models.CalibrationClip(user_id=uid, prompt_text="The rainbow passage")
        db.add(c)
        db.commit()
        db.refresh(c)
        assert c.consent_granted is False and c.status == "pending"
        c.consent_granted = True
        c.status = "consented"
        db.commit()
    finally:
        db.close()
    clips = client.get("/api/v1/personalization/review",
                       headers=_user("rev-cal@test.app")[0]).json()["calibration_clips"]
    assert clips[0]["consent_granted"] is True and clips[0]["status"] == "consented"
    assert ps.review(SessionLocal(), uid)["calibration_note"]
