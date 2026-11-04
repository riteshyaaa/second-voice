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


def test_compare_texts_pure_cases():
    from app.services.speech_restoration import comparison

    a = comparison.compare_texts("I need help", "I need help", "original", "normalized")
    assert a["verdict"] == "agree" and a["meaning_divergence"] == []
    d = comparison.compare_texts("I need help", "I need help please", "original", "normalized")
    assert d["verdict"] == "disagree" and d["word_diffs"]
    n = comparison.compare_texts("I need help", "I don't need help", "original", "normalized")
    assert n["verdict"] == "disagree" and n["meaning_divergence"], "negation flip must surface"
    e = comparison.compare_texts("", "", "original", "normalized")
    assert e["verdict"] == "both_empty"
    o = comparison.compare_texts("hello", "", "original", "normalized")
    assert o["verdict"] == "either_empty"
    r = comparison.build_report(original=None, normalized=None, units=None, stages=[])
    by = {x["artifact"]: x for x in r["artifacts"]}
    assert by["original"]["status"] == "unavailable"
    assert by["enhanced_audio"]["status"] == "unavailable" and by["enhanced_audio"]["reason"]
    assert by["restored_waveform"]["status"] == "unavailable" and by["restored_waveform"]["reason"]
    assert r["comparisons"] == []
    assert "vocoder" in r["note"].lower() or "waveform" in r["note"].lower()


def _ready_job(h, monkeypatch, beam=5):
    import json as _json
    import os as _os

    from app import models as _models
    from app.services.speech_restoration import pipeline as _pipe

    async def fake_run(db, audio, **kw):
        path = _os.path.join(settings.STORAGE_DIR, f"restored_{audio.id}_units.json")
        with open(path, "wb") as f:
            f.write(_json.dumps({"units": [780, 289, 26], "latency_s": 2.4}).encode())
        d = _models.AudioDerivative(parent_asset_id=audio.id, kind="restored", operation="s2u-units",
                                    model_version="wtimit_44spkrs_trained.pt", config={},
                                    file_path=path, mime="application/json",
                                    duration_s=1.0, status="ready")
        db.add(d)
        db.commit()
        db.refresh(d)
        return {"derivative": d, "units": [780, 289, 26],
                "stages": _pipe.plan_stages(restoration_enabled=True),
                "latency_s": 2.4, "checkpoint": "wtimit_44spkrs_trained.pt"}

    monkeypatch.setattr(_pipe, "run_job", fake_run)
    monkeypatch.setattr(settings, "RESTORATION_ENABLED", True)
    s = client.post("/api/v1/audio/sessions", headers=h, json={"title": "c"}).json()["id"]
    aid = _upload(h, s).json()["audio_id"]
    job = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs",
                      headers=h, json={"beam": beam}).json()
    assert job["status"] == "units_ready", job
    return s, aid, job


def test_comparison_needs_ready_job(user, monkeypatch):
    from app.services.speech_restoration import pipeline as _pipe
    from app.services.speech_restoration.s2u_client import S2UUnavailable

    monkeypatch.setattr(settings, "RESTORATION_ENABLED", True)
    s = client.post("/api/v1/audio/sessions", headers=user, json={"title": "c"}).json()["id"]
    aid = _upload(user, s).json()["audio_id"]
    assert client.get(
        f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs/999/comparison",
        headers=user).status_code == 404

    async def boom(db, audio, **kw):
        raise S2UUnavailable("sidecar down")

    monkeypatch.setattr(_pipe, "run_job", boom)
    failed = client.post(f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs",
                         headers=user, json={}).json()
    assert failed["status"] == "failed"
    r = client.get(
        f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs/{failed['job_id']}/comparison",
        headers=user)
    assert r.status_code == 409 and "units_ready" in r.json()["detail"]


def test_comparison_report_live_shapes(user, monkeypatch):
    from app.services import meta_asr_service as _meta

    async def fake_transcribe(data, mime, lang="auto", keywords=None):
        text = "hello world" if mime == "audio/wav" and len(data) > 100 else "hello world"
        return {"text": text, "language": "en", "provider": "stub-asr",
                "model_version": "stub-1", "confidence": None, "timestamps": None, "fallback": True}

    monkeypatch.setattr(_meta, "transcribe", fake_transcribe)
    s, aid, job = _ready_job(user, monkeypatch)
    r = client.get(
        f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs/{job['job_id']}/comparison",
        headers=user)
    assert r.status_code == 200, r.text
    body = r.json()
    by = {x["artifact"]: x for x in body["artifacts"]}
    assert by["original"]["status"] == "ready" and by["normalized"]["status"] == "ready"
    assert by["s2u_units"]["status"] == "ready" and by["s2u_units"]["n_units"] == 3
    assert by["s2u_units"]["first_units"] == [780, 289, 26]
    assert by["enhanced_audio"]["status"] == "unavailable"
    assert by["restored_waveform"]["status"] == "unavailable"
    assert body["comparisons"] and body["comparisons"][0]["verdict"] == "agree"
    assert body["job_id"] == job["job_id"]


def test_comparison_records_asr_failure(user, monkeypatch):
    from app.services import meta_asr_service as _meta

    async def boom(data, mime, lang="auto", keywords=None):
        raise RuntimeError("asr down")

    monkeypatch.setattr(_meta, "transcribe", boom)
    s, aid, job = _ready_job(user, monkeypatch)
    body = client.get(
        f"/api/v1/audio/sessions/{s}/audio/{aid}/restoration/jobs/{job['job_id']}/comparison",
        headers=user).json()
    by = {x["artifact"]: x for x in body["artifacts"]}
    assert by["original"]["status"] == "failed" and "asr down" in by["original"]["reason"]
    assert body["comparisons"] == []  # no pair to compare: honestly empty
    assert by["s2u_units"]["status"] == "ready"  # stored evidence unaffected


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
