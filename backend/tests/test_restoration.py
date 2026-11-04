"""CLARIS P4: restoration pipeline stages, S2U client contract, job API."""
import asyncio
import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import init_db
from app.main import app
from app.services.speech_restoration import pipeline
from app.services.speech_restoration.s2u_client import S2UUnavailable, fetch_units

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
    monkeypatch.setattr(settings, "RESTORATION_ENABLED", False)
    r = client.post("/api/v1/auth/register",
                    json={"email": "resto@test.app", "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login",
                        json={"email": "resto@test.app", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(h, session_id):
    hh = dict(h)
    hh["Content-Type"] = "audio/wav"
    return client.post(f"/api/v1/audio/sessions/{session_id}/audio", headers=hh, content=_wav())


def test_plan_stages_explains_every_stage():
    off = pipeline.plan_stages(restoration_enabled=False)
    by = {s["stage"]: s for s in off}
    assert by["normalize"]["status"] == "ready"
    assert by["enhance"]["status"] == "skipped" and by["enhance"]["reason"]
    assert by["s2u_units"]["status"] == "skipped" and "RESTORATION_ENABLED" in by["s2u_units"]["reason"]
    assert by["vocode"]["status"] == "skipped" and by["vocode"]["reason"]

    on = pipeline.plan_stages(restoration_enabled=True)
    by = {s["stage"]: s for s in on}
    assert by["s2u_units"]["status"] == "ready"
    assert by["vocode"]["status"] == "skipped"  # no vocoder published: never ready


def test_fetch_units_refuses_unreachable_sidecar():
    with pytest.raises(S2UUnavailable, match="unreachable"):
        asyncio.run(fetch_units(_wav(), base_url="http://127.0.0.1:9",
                               beam=5, timeout_s=5))


def test_fetch_units_rejects_malformed_payload(monkeypatch):
    import httpx

    class FakeResp:
        status_code = 200
        text = "not json{"

        def json(self):
            raise ValueError("no json")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    with pytest.raises(S2UUnavailable, match="malformed"):
        asyncio.run(fetch_units(_wav(), base_url="http://x", beam=5, timeout_s=5))


def test_job_unavailable_when_disabled(user):
    s = client.post("/api/v1/audio/sessions", headers=user, json={"title": "r"}).json()["id"]
    aid = _upload(user, s).json()["audio_id"]
    r = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs",
                    headers=user, json={"beam": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unavailable" and body["reason"]
    assert any(st["stage"] == "vocode" and st["status"] == "skipped" for st in body["stages"])


def test_job_runs_and_stores_units_evidence(user, monkeypatch):
    async def fake_run(db, audio, **kw):
        import json as _json
        import os as _os

        from app import models as _models

        path = _os.path.join(settings.STORAGE_DIR, f"restored_{audio.id}_units.json")
        with open(path, "wb") as f:
            f.write(_json.dumps({"units": [63, 991, 780]}).encode())
        d = _models.AudioDerivative(parent_asset_id=audio.id, kind="restored", operation="s2u-units",
                                    model_version="wtimit_44spkrs_trained.pt", config={"beam": 5},
                                    file_path=path, mime="application/json",
                                    duration_s=1.0, status="ready")
        db.add(d)
        db.commit()
        db.refresh(d)
        return {"derivative": d, "units": [63, 991, 780],
                "stages": pipeline.plan_stages(restoration_enabled=True),
                "latency_s": 1.2, "checkpoint": "wtimit_44spkrs_trained.pt"}

    monkeypatch.setattr(pipeline, "run_job", fake_run)
    monkeypatch.setattr(settings, "RESTORATION_ENABLED", True)
    s = client.post("/api/v1/audio/sessions", headers=user, json={"title": "r"}).json()["id"]
    aid = _upload(user, s).json()["audio_id"]
    r = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs",
                    headers=user, json={"beam": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "units_ready" and body["n_units"] == 3
    assert body["derivative_id"] and body["checkpoint"] == "wtimit_44spkrs_trained.pt"

    got = client.get(f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs/{body['job_id']}",
                     headers=user).json()
    assert got["status"] == "units_ready"

    # cross-user isolation
    r2 = client.post("/api/v1/auth/register",
                     json={"email": "resto2@test.app", "password": "password123"})
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get(
        f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs/{body['job_id']}",
        headers=h2).status_code == 404


def test_job_failure_is_recorded_not_hidden(user, monkeypatch):
    async def boom(db, audio, **kw):
        raise S2UUnavailable("inference sidecar unreachable at http://x: boom")

    monkeypatch.setattr(pipeline, "run_job", boom)
    monkeypatch.setattr(settings, "RESTORATION_ENABLED", True)
    s = client.post("/api/v1/audio/sessions", headers=user, json={"title": "r"}).json()["id"]
    aid = _upload(user, s).json()["audio_id"]
    body = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs",
                       headers=user, json={}).json()
    assert body["status"] == "failed" and "unreachable" in body["error"]
