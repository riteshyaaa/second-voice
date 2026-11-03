"""CLARIS P1: immutable originals + versioned derivatives (maintained)."""
import glob
import hashlib
import io
import os
import wave

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import init_db
from app.main import app

init_db()
client = TestClient(app)


def _wav(seconds=1, rate=16000):
    import math
    import struct

    frames = b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / rate)))
                      for i in range(rate * seconds))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


@pytest.fixture
def user(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    r = client.post("/api/v1/auth/register",
                    json={"email": "deriv@test.app", "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login",
                        json={"email": "deriv@test.app", "password": "password123"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, str(tmp_path)


def _upload(user, session_id, data=None):
    h = dict(user)
    h["Content-Type"] = "audio/wav"
    return client.post(f"/api/v1/audio/sessions/{session_id}/audio", headers=h, content=data or _wav())


def test_normalize_preserves_original_and_is_idempotent(user):
    h, _ = user
    s = client.post("/api/v1/audio/sessions", headers=h, json={"title": "d"}).json()["id"]
    up = _upload(h, s)
    aid = up.json()["audio_id"]
    orig_path = glob.glob(os.path.join(user[1], "*.wav"))[0]
    before = hashlib.sha256(open(orig_path, "rb").read()).hexdigest()

    r1 = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/normalize", headers=h)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["kind"] == "normalized" and d1["operation"] == "normalize_to_wav16k"
    assert d1["model_version"] and d1["status"] == "ready"
    assert d1["quality"] and d1["quality"].get("analyzed") is True

    r2 = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/normalize", headers=h)
    assert r2.json()["derivative_id"] == d1["derivative_id"]  # no duplicate work
    assert len(glob.glob(os.path.join(user[1], "*.wav"))) == 2  # original + one sibling

    after = hashlib.sha256(open(orig_path, "rb").read()).hexdigest()
    assert before == after  # original never touched


def test_derivative_playback_and_history_and_isolation(user):
    h, _ = user
    s = client.post("/api/v1/audio/sessions", headers=h, json={"title": "d"}).json()["id"]
    aid = _upload(h, s).json()["audio_id"]
    did = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/normalize", headers=h).json()["derivative_id"]

    dl = client.get(f"/api/v1/audio/sessions/{s}/audio/{aid}/derivatives/{did}", headers=h)
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "audio/wav"

    det = client.get(f"/api/v1/sessions/{s}", headers=h).json()
    assert det["items"] == []  # no transcript yet: nothing to attach to
    # derivative itself is reachable metadata regardless
    r = client.post("/api/v1/auth/register",
                    json={"email": "deriv2@test.app", "password": "password123"})
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"/api/v1/audio/sessions/{s}/audio/{aid}/derivatives/{did}", headers=h2).status_code == 404
    assert client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/normalize", headers=h2).status_code == 404


def test_missing_file_maps_to_410_and_wipe_removes_derivatives(user):
    h, store = user
    s = client.post("/api/v1/audio/sessions", headers=h, json={"title": "d"}).json()["id"]
    aid = _upload(h, s).json()["audio_id"]
    for p in glob.glob(os.path.join(store, "*.wav")):
        os.remove(p)
    r = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/normalize", headers=h)
    assert r.status_code == 410

    aid2 = _upload(h, s).json()["audio_id"]
    client.post(f"/api/v1/audio/sessions/{s}/audio/{aid2}/normalize", headers=h)
    files = set(glob.glob(os.path.join(store, "*.wav")))
    assert len(files) == 2
    assert client.delete("/api/v1/account/data", headers=h).status_code == 200
    assert [p for p in files if os.path.exists(p)] == []
