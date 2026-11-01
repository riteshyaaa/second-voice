"""Phase 10: safety battery — every speech path attacked directly via API.

No frontend, no flow assumptions: each test forges the exact request an
abusive or buggy client would send. The gate must hold at the API layer.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_safety.db")
if os.path.exists("./test_safety.db"):
    os.remove("./test_safety.db")

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


def _setup(h):
    s = client.post("/api/v1/audio/sessions", json={"title": "s"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": up["audio_id"], "manual_transcript": "I need help", "language": "en"},
                    headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    return s, up, t, sg


def test_synth_rejects_everything_unconfirmed():
    h = _user("safe@test.app")
    _, _, _, sg = _setup(h)
    # forged approved id
    assert client.post("/api/v1/speech/synthesize", json={"approved_message_id": 999999}, headers=h).status_code == 404
    # confirm first, then speak works (control)
    c = client.post("/api/v1/confirmation",
                    json={"suggestion_id": sg["suggestion_id"], "final_text": "I need help.", "language": "en"},
                    headers=h).json()
    sp = client.post("/api/v1/speech/synthesize",
                     json={"approved_message_id": c["approved_message_id"]}, headers=h).json()
    assert "audio_url" in sp


def test_cross_user_speech_barrier():
    a, b = _user("safe-a@test.app"), _user("safe-b@test.app")
    _, _, _, sg = _setup(a)
    c = client.post("/api/v1/confirmation",
                    json={"suggestion_id": sg["suggestion_id"], "final_text": "I need help.", "language": "en"},
                    headers=a).json()
    # B cannot speak A's confirmed message, fetch its audio, confirm its suggestion,
    # read its questions, replay its audio, or touch its cards
    assert client.post("/api/v1/speech/synthesize",
                       json={"approved_message_id": c["approved_message_id"]}, headers=b).status_code == 404
    assert client.post("/api/v1/confirmation",
                       json={"suggestion_id": sg["suggestion_id"], "final_text": "x", "language": "en"},
                       headers=b).status_code == 404
    assert client.get(f"/api/v1/reconstruction/questions/{sg['suggestion_id']}", headers=b).status_code == 404
    s_a = client.get("/api/v1/sessions", headers=a).json()[0]
    assert client.get(f"/api/v1/audio/sessions/{s_a['id']}/audio/1", headers=b).status_code in (403, 404)
    cards = client.get("/api/v1/cards", headers=a).json()
    assert client.post(f"/api/v1/cards/{cards[0]['id']}/speak", headers=b).status_code == 404


def test_card_speak_is_confirmed_not_bypassed():
    h = _user("safe-card@test.app")
    cards = client.get("/api/v1/cards", headers=h).json()
    sp = client.post(f"/api/v1/cards/{cards[0]['id']}/speak", headers=h).json()
    assert "audio_url" in sp  # tap minted confirmation; gate saw a confirmed row


def test_audit_trail_complete_per_item():
    import io
    import struct
    import wave

    h = _user("safe-audit@test.app")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<16000h", *([0] * 16000)))
    s = client.post("/api/v1/audio/sessions", json={"title": "s"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=buf.getvalue(),
                     headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": up["audio_id"], "manual_transcript": "I need help", "language": "en"},
                    headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    d = client.get(f"/api/v1/sessions/{s['id']}", headers=h).json()
    item = d["items"][0]
    assert item["original"] == "I need help"  # original transcript preserved
    assert item["audio_quality"]["analyzed"] is True  # quality kept
    assert item["uncertainty"]  # uncertainty kept
    assert item["evidence"]["comparison_verdict"] == "single"  # full evidence kept
    assert item["suggestions"][0]["evidence_for"] is not None  # suggestion evidence kept
    replay = client.get(f"/api/v1/audio/sessions/{s['id']}/audio/{up['audio_id']}", headers=h)
    assert replay.status_code == 200  # original recording retrievable


def test_wipe_covers_revision_journal():
    h = _user("safe-wipe@test.app")
    v = client.post("/api/v1/vocabulary", json={"term": "Wipe", "language": "en", "category": "word"}, headers=h).json()
    client.patch(f"/api/v1/vocabulary/{v['id']}", json={"term": "Wipe2"}, headers=h)
    assert client.get(f"/api/v1/vocabulary/{v['id']}/revisions", headers=h).json() != []
    assert client.delete("/api/v1/account/data", headers=h).json() == {"deleted": True}
    assert client.get("/api/v1/vocabulary", headers=h).json() == []
