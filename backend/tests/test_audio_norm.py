"""Audio normalization regression tests (offline, no network).

Meta ASR requires mono s16le at 16/24 kHz with audioEncoding WAV (verified
live); uploads are normalized to that shape server-side.
"""
import io
import wave

import pytest

from app.services.audio_service import normalize_to_wav16k, resample_linear


def _wav_bytes(rate=44100, channels=2, secs=0.5, freq=440.0):
    import array
    import math

    n = int(rate * secs)
    frames = array.array("h")
    for i in range(n):
        s = int(10000 * math.sin(2 * 3.14159 * freq * i / rate))
        frames.extend([s] * channels)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames.tobytes())
    return buf.getvalue()


def _props(data: bytes):
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()


def test_compliant_wav_passes_through_untouched():
    raw = _wav_bytes(rate=16000, channels=1)
    assert normalize_to_wav16k(raw, "audio/wav") == raw


def test_441k_stereo_becomes_16k_mono():
    out = normalize_to_wav16k(_wav_bytes(rate=44100, channels=2), "audio/wav")
    ch, sw, rate, n = _props(out)
    assert (ch, sw, rate) == (1, 2, 16000)
    assert abs(n - 8000) < 5  # 0.5 s at 16 kHz


def test_garbage_raises():
    with pytest.raises(Exception):
        normalize_to_wav16k(b"not audio at all", "audio/wav")


def test_resample_identity_and_length():
    import array

    pcm = array.array("h", [0, 1000, -1000, 500]).tobytes()
    assert resample_linear(pcm, 16000, 16000) == pcm
    assert len(resample_linear(pcm, 8000, 16000)) == 2 * len(pcm)
