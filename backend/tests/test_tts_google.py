"""Phase 9: Google Cloud TTS provider, voice gating, fixed-text preview."""
import asyncio
import base64
import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import init_db
from app.main import app
from app.services import tts_service

init_db()
client = TestClient(app)


def _auth(email="tts9@test.app"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_voices_follow_active_provider(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "google")
    assert tts_service.voices_for("hi")[0].startswith("hi-IN-")
    assert "mr" not in tts_service.GOOGLE_VOICES and "mr" not in tts_service.VOICES
    monkeypatch.setattr(settings, "TTS_PROVIDER", "webspeech-fallback")
    assert tts_service.voices_for("hi")[0].startswith("hi-IN-")
    assert "SwaraNeural" in tts_service.voices_for("hi")[0]


def test_check_voice_gates_per_language(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "google")
    ok, supported = tts_service.check_voice("hi", "hi-IN-Wavenet-A")
    assert ok and supported
    ok, _ = tts_service.check_voice("hi", "en-IN-Wavenet-A")
    assert not ok
    ok, _ = tts_service.check_voice("hi", "")
    assert ok  # empty = provider default, resolved later
    ok, _ = tts_service.check_voice("hinglish", "en-IN-Wavenet-A")
    assert ok  # Hinglish honestly spans both locales


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _fake_client_factory(seen, resp):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, params=None, json=None, **k):
            seen.update(url=url, params=params, json=json)
            return resp

    return FakeClient


def _pcm(seconds=0.5, rate=16000):
    import math
    import struct

    return b"".join(struct.pack("<h", int(9000 * math.sin(2 * i))) for i in range(int(rate * seconds)))


def test_google_synthesize_writes_16k_wav(monkeypatch, tmp_path):
    import httpx

    seen = {}
    pcm = _pcm()
    monkeypatch.setattr(httpx, "AsyncClient",
                        _fake_client_factory(seen, _FakeResp(200, {"audioContent": base64.b64encode(pcm).decode()})))
    monkeypatch.setattr(settings, "TTS_PROVIDER", "google")
    monkeypatch.setattr(settings, "GOOGLE_TTS_API_KEY", "test-key")
    out = str(tmp_path / "g.wav")
    info = asyncio.run(tts_service.synthesize("नमस्ते", "hi", "hi-IN-Wavenet-D", 1.5, out))
    assert info == {"provider": "google", "voice": "hi-IN-Wavenet-D", "fallback": False}
    assert seen["url"] == "https://texttospeech.googleapis.com/v1/text:synthesize"
    assert seen["params"] == {"key": "test-key"}
    assert seen["json"]["voice"] == {"languageCode": "hi-IN", "name": "hi-IN-Wavenet-D"}
    assert seen["json"]["audioConfig"]["sampleRateHertz"] == 16000
    assert seen["json"]["audioConfig"]["speakingRate"] == 1.5
    with wave.open(out, "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() == len(pcm) // 2


def test_google_errors_are_transparent(monkeypatch, tmp_path):
    import httpx

    out = str(tmp_path / "e.wav")
    monkeypatch.setattr(settings, "TTS_PROVIDER", "google")
    monkeypatch.setattr(settings, "GOOGLE_TTS_API_KEY", "k")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_client_factory({}, _FakeResp(401, {})))
    with pytest.raises(RuntimeError, match="Google TTS error 401"):
        asyncio.run(tts_service.synthesize("hi", "en", "", 1.0, out))
    monkeypatch.setattr(httpx, "AsyncClient", _fake_client_factory({}, _FakeResp(200, {"nope": 1})))
    with pytest.raises(RuntimeError, match="malformed"):
        asyncio.run(tts_service.synthesize("hi", "en", "", 1.0, out))
    monkeypatch.setattr(settings, "GOOGLE_TTS_API_KEY", "")
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(tts_service.synthesize("hi", "en", "", 1.0, out))
    monkeypatch.setattr(settings, "GOOGLE_TTS_API_KEY", "k")
    with pytest.raises(ValueError, match="not available"):
        asyncio.run(tts_service.synthesize("hi", "hi", "en-IN-Wavenet-A", 1.0, out))


def test_preview_fixed_text_only(monkeypatch):
    h = _auth()
    # No key configured -> honest fallback tone; still 200 audio/wav.
    r = client.post("/api/v1/speech/preview", headers=h,
                    json={"language": "hi", "voice": "", "text": "MALICIOUS IGNORED"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/wav"
    assert r.headers["X-TTS-Fallback"] == "True"
    with wave.open(io.BytesIO(r.content), "rb") as w:
        assert w.getframerate() == 16000
    # Unknown voice -> clean 409, never a provider call.
    r2 = client.post("/api/v1/speech/preview", headers=h,
                     json={"language": "hi", "voice": "xx-FAKE-1"})
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "VOICE_UNSUPPORTED"

    # Google voice list is served without a key (list is static).
    # Marathi removed: unknown languages fall back to the English table.
    monkeypatch.setattr(settings, "TTS_PROVIDER", "google")
    v = client.get("/api/v1/speech/voices?language=mr", headers=h).json()
    assert v["language"] == "mr"
    assert all(x.startswith("en-IN-") or x.startswith("en-US-") for x in v["voices"])
