"""Phase 6: scored retrieval, false-personalization tracking, rollback."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_adapt.db")
if os.path.exists("./test_adapt.db"):
    os.remove("./test_adapt.db")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app
from app.services import personalization_service as ps

init_db()
client = TestClient(app)


def _user(email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _correct(h, original, corrected):
    s = client.post("/api/v1/audio/sessions", json={"title": "a"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": up["audio_id"], "manual_transcript": original, "language": "en"},
                    headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    client.post("/api/v1/feedback", json={"suggestion_id": sg["suggestion_id"], "final_text": corrected}, headers=h)
    return sg


def test_retrieval_prioritizes_patterns_and_caps():
    from app.core.database import SessionLocal
    from app import models

    h = _user("adapt@test.app")
    client.post("/api/v1/vocabulary", json={"term": "Aarav", "language": "en", "category": "name"}, headers=h)
    from app.services.personalization_service import normalize_term
    db = SessionLocal()
    me = db.query(models.User).filter(models.User.email == "adapt@test.app").first()
    uid = me.id
    for i in range(25):  # flood with overlapping terms to test the cap
        db.add(models.VocabularyEntry(user_id=uid, term=f"help word{i}", normalized=normalize_term(f"help word{i}"),
                                      language="en", category="word", times_used=i))
    db.commit()
    db.close()
    _correct(h, "Arav needs help", "Aarav needs help")
    db = SessionLocal()
    ctx = ps.retrieve_context(db, uid, "Arav needs help urgently", "en")
    db.close()
    assert ctx["spark_vocabulary"][0] == "Aarav", ctx["spark_vocabulary"][:3]  # pattern trigger wins
    assert len(ctx["spark_vocabulary"]) <= 20  # cap enforced
    assert any("corrected" in u["reason"] for u in ctx["context_used"])
    assert ctx["vocab_map"].get("arav") == "Aarav"  # deterministic map intact


def test_history_language_and_opt_out():
    h = _user("adapth@test.app")
    s = client.post("/api/v1/audio/sessions", json={"title": "h"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    for text, lang in (("I need water please", "en"), ("मुझे पानी चाहिए", "hi")):
        t = client.post("/api/v1/transcription/manual",
                        params={"audio_id": up["audio_id"], "manual_transcript": text, "language": lang},
                        headers=h).json()
        sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
        client.post("/api/v1/confirmation",
                    json={"suggestion_id": sg["suggestion_id"], "final_text": text, "language": lang}, headers=h)
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    me = db.query(models.User).filter(models.User.email == "adapth@test.app").first()
    ctx = ps.retrieve_context(db, me.id, "मुझे दवाई चाहिए", "hi")
    assert ctx["history"] and ctx["history"][0] == "मुझे पानी चाहिए", ctx["history"]
    ctx_off = ps.retrieve_context(db, me.id, "मुझे दवाई चाहिए", "hi", use_history=False)
    assert ctx_off["history"] == []
    db.close()


def _manual_reconstruct(h, audio_id, text):
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": audio_id, "manual_transcript": text, "language": "en"},
                    headers=h).json()
    return client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()


def test_false_personalization_tracked():
    h = _user("adaptfp@test.app")
    client.post("/api/v1/vocabulary", json={"term": "Aarav", "language": "en", "category": "name"}, headers=h)
    s = client.post("/api/v1/audio/sessions", json={"title": "f"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    # first the user teaches the alias (no swap fires yet — nothing to revert)
    sg0 = _manual_reconstruct(h, up["audio_id"], "Arav is here")
    assert "Aarav" not in sg0["proposed_text"]
    client.post("/api/v1/feedback", json={"suggestion_id": sg0["suggestion_id"], "final_text": "Aarav is here"}, headers=h)
    # now our swap fires (rules, offline)
    sg = _manual_reconstruct(h, up["audio_id"], "Arav is here")
    assert "Aarav" in sg["proposed_text"]
    # user reverts OUR swap -> false personalization recorded
    client.post("/api/v1/feedback", json={"suggestion_id": sg["suggestion_id"], "final_text": "Arav is here"}, headers=h)
    stats = client.get("/api/v1/feedback/stats", headers=h).json()
    assert stats["false_personalizations"] == 1, stats
    assert stats["unwanted_rate"] > 0
    # keeping our swap while editing elsewhere -> no event
    t2 = client.post("/api/v1/transcription/manual",
                     params={"audio_id": up["audio_id"], "manual_transcript": "Arav is here", "language": "en"},
                     headers=h).json()
    sg2 = client.post("/api/v1/reconstruction", json={"transcript_id": t2["transcript_id"]}, headers=h).json()
    client.post("/api/v1/feedback", json={"suggestion_id": sg2["suggestion_id"], "final_text": "Aarav is here today"}, headers=h)
    stats2 = client.get("/api/v1/feedback/stats", headers=h).json()
    assert stats2["false_personalizations"] == 1, stats2


def test_rollback_round_trip():
    h = _user("adaptrb@test.app")
    v = client.post("/api/v1/vocabulary", json={"term": "Aarav", "language": "en", "category": "name"}, headers=h).json()
    client.patch(f"/api/v1/vocabulary/{v['id']}", json={"term": "Aarav Kumar"}, headers=h)
    revs = client.get(f"/api/v1/vocabulary/{v['id']}/revisions", headers=h).json()
    assert len(revs) == 1 and revs[0]["snapshot"]["term"] == "Aarav"
    rb = client.post(f"/api/v1/vocabulary/{v['id']}/rollback/{revs[0]['id']}", headers=h).json()
    assert rb["term"] == "Aarav" and rb["version"] == 3, rb
    revs2 = client.get(f"/api/v1/vocabulary/{v['id']}/revisions", headers=h).json()
    assert len(revs2) == 2  # pre-restore state journaled too
    assert client.post(f"/api/v1/vocabulary/{v['id']}/rollback/999999", headers=h).status_code == 404
