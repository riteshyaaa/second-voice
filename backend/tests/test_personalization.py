"""Personalization: approved vocab is reused; users are isolated."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_vocab.db")
if os.path.exists("./test_vocab.db"):
    os.remove("./test_vocab.db")

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


def test_vocab_learn_and_reuse():
    """Spec example: ASR 'Arav' corrected+approved to 'Aarav' once → next
    'Arav' is offered as 'Aarav' (still rejectable)."""
    h = _user("vocab@test.app")
    client.post("/api/v1/vocabulary", json={"term": "Aarav", "language": "en", "category": "name"}, headers=h)
    s = client.post("/api/v1/audio/sessions", json={"title": "v"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....", headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual", params={"audio_id": up["audio_id"], "manual_transcript": "Arav is here", "language": "en"}, headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    # user corrects and approves → learning event recorded
    client.post("/api/v1/feedback", json={"suggestion_id": sg["suggestion_id"], "final_text": "Aarav is here"}, headers=h)
    t2 = client.post("/api/v1/transcription/manual", params={"audio_id": up["audio_id"], "manual_transcript": "Arav is here", "language": "en"}, headers=h).json()
    sg2 = client.post("/api/v1/reconstruction", json={"transcript_id": t2["transcript_id"]}, headers=h).json()
    assert "Aarav" in sg2["proposed_text"]
    # dashboard must survive real correction data (regression: dict(pair) crash)
    stats = client.get("/api/v1/feedback/stats", headers=h).json()
    assert stats["corrections_approved"] >= 1
    assert stats["frequent_phrases"][0]["phrase"] == "Aarav is here"


def test_user_isolation():
    a = _user("alice@test.app")
    b = _user("bob@test.app")
    sa = client.post("/api/v1/audio/sessions", json={"title": "a"}, headers=a).json()
    r = client.get(f"/api/v1/sessions/{sa['id']}", headers=b)
    assert r.status_code == 404
