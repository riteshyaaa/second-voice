"""CLARIS P2: local Whisper adapter contract (engine stubbed)."""
import io
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_asr_local.db")
if os.path.exists("./test_asr_local.db"):
    os.remove("./test_asr_local.db")

import pytest

from app.core.config import settings
from app.core.database import init_db
from app.services import asr_providers
from app.services.asr_providers import LocalWhisperProvider, get_provider, second_available

init_db()

CALLS = {}


def _stub_engine(transcript="namaste duniya", lang="hi"):
    segs = [types.SimpleNamespace(text=transcript)]
    info = types.SimpleNamespace(language=lang)
    fw = types.ModuleType("faster_whisper")

    class FakeModel:
        def __init__(self, model_id, device=None, compute_type=None):
            CALLS["model"] = (model_id, device, compute_type)

        def transcribe(self, audio, language=None, initial_prompt=None, vad_filter=False):
            import numpy as _np

            CALLS["args"] = {"language": language, "initial_prompt": initial_prompt}
            assert isinstance(audio, _np.ndarray) and audio.dtype == _np.float32
            CALLS["samples"] = list(audio)
            return segs, info

    fw.WhisperModel = FakeModel
    return fw


@pytest.fixture
def stub(monkeypatch):
    sys.modules.pop("faster_whisper", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", _stub_engine())
    monkeypatch.setattr(settings, "LOCAL_ASR_DEVICE", "cpu")
    monkeypatch.setattr(settings, "LOCAL_ASR_COMPUTE", "int8")
    CALLS.clear()
    return CALLS


def _wav():
    import math
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(2 * math.pi * 440 * i / 16000)))
                               for i in range(16000)))
    return buf.getvalue()


def test_transcribe_maps_language_and_keywords(stub):
    import asyncio

    p = LocalWhisperProvider("Systran/faster-whisper-small")
    out = asyncio.run(p.transcribe(_wav(), "audio/wav", "hi", ["Aarav"]))
    assert out["text"] == "namaste duniya"
    assert out["language"] == "hi"
    assert out["provider"] == "local-whisper"
    assert out["confidence"] is None and out["timestamps"] is None  # never invented
    assert stub["args"] == {"language": "hi", "initial_prompt": "Aarav"}
    assert len(stub["samples"]) == 16000  # 1 s of normalized mono samples
    assert all(-1.0 <= s <= 1.0 for s in stub["samples"][:100])

    out2 = asyncio.run(p.transcribe(_wav(), "audio/wav", "hinglish"))
    assert stub["args"]["language"] is None  # non-Whisper hint falls back to detect


def test_local_model_path_passes_through(stub):
    """CLARIS P2: a converted local dir (e.g. Hindi-adapted CT2) reaches the
    engine unchanged — no hub-name assumptions."""
    import asyncio

    p = LocalWhisperProvider("/models/whisper-small-hindi-ct2")
    out = asyncio.run(p.transcribe(_wav(), "audio/wav", "hi"))
    assert stub["model"][0] == "/models/whisper-small-hindi-ct2"
    assert out["model_version"] == "/models/whisper-small-hindi-ct2"
    assert out["provider"] == "local-whisper"


def test_health_unavailable_without_engine(monkeypatch):
    # faster_whisper is not installed in the host env: the adapter must say so.
    monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
    p = LocalWhisperProvider("x")
    h = asyncio_run(p.health_check())
    assert h["live"] is False and "not installed" in h["detail"]
    assert p.provider_metadata()["live"] != True


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def test_registry_and_second_available(monkeypatch):
    with pytest.raises(ValueError):
        get_provider("nope")
    monkeypatch.setattr(settings, "LOCAL_ASR_MODEL", "")
    with pytest.raises(ValueError, match="LOCAL_ASR_MODEL not set"):
        get_provider("local-whisper")
    monkeypatch.setattr(settings, "SECOND_ASR_ENABLED", True)
    monkeypatch.setattr(settings, "SECOND_ASR_PROVIDER", "local-whisper")
    ok, reason = second_available()
    assert ok is False and reason  # unconfigured or uninstalled: honest reason, no silent fallback


def test_meta_contract_untouched():
    p = get_provider("meta-asr")
    assert p.supported_formats() and "auto" in p.supported_languages()
