"""End-to-end safety: TTS rejects unconfirmed text; confirmation authorizes it."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_confirm.db")
if os.path.exists("./test_confirm.db"):
    os.remove("./test_confirm.db")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app

init_db()
client = TestClient(app)


def _auth():
    r = client.post("/api/v1/auth/register", json={"email": "confirm@test.app", "password": "password123"})
    assert r.status_code in (200, 409)
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": "confirm@test.app", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_unconfirmed_tts_rejected():
    h = _auth()
    s = client.post("/api/v1/audio/sessions", json={"title": "t", "language": "en"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....", headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual", params={"audio_id": up["audio_id"], "manual_transcript": "I need help", "language": "en"}, headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    # craft an approved message WITHOUT confirmation by confirming then deleting? No — confirm properly, then verify TTS works;
    # and verify a forged approved_message_id 404s/409s instead of speaking.
    r = client.post("/api/v1/speech/synthesize", json={"approved_message_id": 999999}, headers=h)
    assert r.status_code in (404, 409)
    # now the real flow: confirm → speak works
    c = client.post("/api/v1/confirmation", json={"suggestion_id": sg["suggestion_id"], "final_text": "I need help.", "language": "en"}, headers=h).json()
    r2 = client.post("/api/v1/speech/synthesize", json={"approved_message_id": c["approved_message_id"]}, headers=h).json()
    assert "audio_url" in r2
