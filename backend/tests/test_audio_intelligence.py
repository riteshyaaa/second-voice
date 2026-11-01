"""Phase 1: audio quality verdicts on synthesized fixtures (offline-safe).

Fixtures are synthesized with stdlib wave — no network, no corpus download.
Thresholds live in audio_intelligence; these tests pin the behavior.
"""
import io
import math
import struct
import wave

from app.services import audio_intelligence as ai

RATE = 16000


def _wav(samples) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return buf.getvalue()


def _sine(secs, amp, freq=220.0):
    n = int(RATE * secs)
    return [int(amp * math.sin(2 * math.pi * freq * i / RATE)) for i in range(n)]


def _clamp(samples):
    return [max(-32768, min(32767, s)) for s in samples]


def test_silence_flags_rerecord():
    q = ai.analyze_wav16k(_wav([0] * RATE))  # 1 s of silence
    assert q["analyzed"] is True
    assert q["quality"] == "poor"
    assert "mostly_silence" in q["issues"]
    assert q["rerecord_suggested"] is True
    assert q["advice"]


def test_quiet_flags_too_quiet():
    # Audible above the silence floor (frame RMS ~566) but weak overall.
    q = ai.analyze_wav16k(_wav(_sine(1.0, 800)))
    assert q["quality"] in ("usable", "poor")
    assert "too_quiet" in q["issues"]
    assert q["rerecord_suggested"] is True


def test_clipped_flags_clipping():
    q = ai.analyze_wav16k(_wav(_clamp([int(40000 * math.sin(2 * math.pi * 220 * i / RATE)) for i in range(RATE)])))
    assert "clipping" in q["issues"]
    assert q["clipping_fraction"] > 0.01
    assert q["rerecord_suggested"] is True


def test_healthy_speech_like_scores_good():
    # Bursts with natural pauses — silence present but not dominant.
    burst = _sine(0.4, 8000)
    pause = [0] * int(RATE * 0.15)
    q = ai.analyze_wav16k(_wav(burst + pause + burst + pause + burst))
    assert q["quality"] == "good", q
    assert q["issues"] == []
    assert q["rerecord_suggested"] is False
    assert q["longest_speech_s"] >= 0.35


def test_loud_continuous_is_not_bad_audio():
    # Regression: the live empty-transcript clip (9.25 s, peak ~25371,
    # continuous loud speech) is a PROVIDER failure, not bad audio.
    # Quality must stay good so we never blame the user's recording.
    q = ai.analyze_wav16k(_wav(_sine(2.0, 25000, freq=180.0)))
    assert q["peak"] > 20000
    assert q["silence_fraction"] < 0.2
    assert q["quality"] == "good", q
    assert q["rerecord_suggested"] is False


def test_noisy_flags_too_noisy():
    import random
    rng = random.Random(7)
    speech = _sine(1.0, 1200)
    noisy = [max(-32768, min(32767, s + rng.randint(-1000, 1000))) for s in speech]
    q = ai.analyze_wav16k(_wav(noisy))
    assert q["snr_db"] is not None and q["snr_db"] < 10, q
    assert "too_noisy" in q["issues"], q
    assert q["rerecord_suggested"] is True


def test_too_short():
    q = ai.analyze_wav16k(_wav(_sine(0.1, 8000)))
    assert "too_short" in q["issues"]
    assert q["rerecord_suggested"] is True


def test_analyze_upload_never_raises():
    ok = ai.analyze_upload(_wav(_sine(0.5, 8000)), "audio/wav")
    assert ok["analyzed"] is True
    bad = ai.analyze_upload(b"RIFF....not-audio", "audio/wav")
    assert bad["analyzed"] is False
    assert bad["rerecord_suggested"] is False  # skipped != poor


def _client():
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_audiointel.db")
    if os.path.exists("./test_audiointel.db"):
        os.remove("./test_audiointel.db")
    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    init_db()
    return TestClient(app)


def _auth(client, email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_upload_returns_quality_and_rerecord_nudge():
    client = _client()
    h = _auth(client, "intel@test.app")
    s = client.post("/api/v1/audio/sessions", json={"title": "q"}, headers=h).json()
    pause = [0] * int(RATE * 0.15)
    good = client.post(f"/api/v1/audio/sessions/{s['id']}/audio",
                       content=_wav(_sine(0.5, 8000) + pause + _sine(0.5, 5000) + pause + _sine(0.5, 9000)),
                       headers={**h, "Content-Type": "audio/wav"}).json()
    assert good["audio_quality"]["quality"] == "good"
    assert good["rerecord_suggested"] is False
    poor = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=_wav([0] * RATE),
                       headers={**h, "Content-Type": "audio/wav"}).json()
    assert poor["audio_quality"]["quality"] == "poor"
    assert poor["rerecord_suggested"] is True
    assert poor["audio_quality"]["advice"]
    # quality persists on the session history path (items need transcripts)
    client.post("/api/v1/transcription/manual",
                params={"audio_id": poor["audio_id"], "manual_transcript": "hello", "language": "en"}, headers=h)
    detail = client.get(f"/api/v1/sessions/{s['id']}", headers=h).json()
    assert detail["items"][0]["audio_quality"]["quality"] == "poor"
