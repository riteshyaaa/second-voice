"""Phase 5: provenance/versioning, edit support, recognition patterns."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_profile.db")
if os.path.exists("./test_profile.db"):
    os.remove("./test_profile.db")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app

init_db()
client = TestClient(app)


def _user(email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _correct(h, original, corrected):
    s = client.post("/api/v1/audio/sessions", json={"title": "p"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": up["audio_id"], "manual_transcript": original, "language": "en"},
                    headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    client.post("/api/v1/feedback", json={"suggestion_id": sg["suggestion_id"], "final_text": corrected}, headers=h)


def test_vocab_provenance_defaults_and_edit():
    h = _user("prof@test.app")
    v = client.post("/api/v1/vocabulary", json={"term": "Aarav", "language": "en", "category": "name"}, headers=h).json()
    rows = client.get("/api/v1/vocabulary", headers=h).json()
    row = [r for r in rows if r["id"] == v["id"]][0]
    assert row["source"] == "user-approved" and row["status"] == "approved" and row["version"] == 1
    e = client.patch(f"/api/v1/vocabulary/{v['id']}", json={"status": "provisional"}, headers=h).json()
    assert e["version"] == 2 and e["status"] == "provisional"
    bad = client.patch(f"/api/v1/vocabulary/{v['id']}", json={"status": "auto"}, headers=h)
    assert bad.status_code == 422
    other = _user("prof-other@test.app")
    assert client.patch(f"/api/v1/vocabulary/{v['id']}", json={"status": "approved"}, headers=other).status_code == 404


def test_memory_edit_bumps_version():
    h = _user("profmem@test.app")
    m = client.post("/api/v1/memory", json={"kind": "phrase", "content": "hello", "language": "en"}, headers=h).json()
    e = client.patch(f"/api/v1/memory/{m['id']}", json={"content": "hello there"}, headers=h).json()
    assert e["version"] == 2
    rows = client.get("/api/v1/memory", headers=h).json()
    row = [r for r in rows if r["id"] == m["id"]][0]
    assert row["content"] == "hello there" and row["provenance"] == "user-approved"


def test_recognition_patterns_and_ambiguity():
    h = _user("profpat@test.app")
    _correct(h, "Arav is here", "Aarav is here")
    _correct(h, "Arav is here", "Aarav is here")
    _correct(h, "Arav is here", "Aarav is there")
    _correct(h, "Arav is here", "Aarav is home")
    pats = client.get("/api/v1/learning/patterns", headers=h).json()
    aarav = [p for p in pats if p["from"] == "arav" and p["to"] == "Aarav"][0]
    assert aarav["count"] == 4, aarav  # one count per explicit save, not doubled by pattern events
    assert set(aarav["sources"]) == {"correction", "pattern"}
    assert aarav["ambiguous"] is False  # one stable reading
    here = [p for p in pats if p["from"] == "here"][0]
    assert here["ambiguous"] is True, here  # here→there and here→home compete
    stats = client.get("/api/v1/feedback/stats", headers=h).json()
    assert stats["provisional_count"] == 0
    assert "vocab_by_language" in stats and stats["top_patterns"]
    assert "here" in stats["ambiguous_terms"]
