"""Phase 2: provider interface, orchestration routing, comparison.

All routing/comparison tests run offline. Live Meta behavior is unchanged
by construction (moved verbatim) and covered by the pre-existing suite +
validation scripts — not re-proven here. A test-only stub engine exercises
the secondary path; it is labelled stub and never ships.
"""
import pytest

from app.core.config import settings
from app.services import asr_orchestration as orch
from app.services.asr_providers import ASRProvider, MetaASRProvider, get_provider, primary_provider
from app.services.meta_asr_service import transcribe


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.setattr(settings, "META_API_KEY", "")
    monkeypatch.setattr(settings, "SECOND_ASR_ENABLED", False)
    monkeypatch.setattr(settings, "SECOND_ASR_PROVIDER", "")
    return True


def test_meta_conforms_to_interface():
    p = MetaASRProvider()
    assert isinstance(p, ASRProvider)
    assert p.name == "meta-asr"
    assert "auto" in p.supported_languages() and "hi" in p.supported_languages()
    assert "audio/wav" in p.supported_formats()
    md = p.provider_metadata()
    assert set(md) == {"name", "model_version", "live"}


@pytest.mark.asyncio
async def test_meta_health_and_fallback_shape(no_key):
    p = MetaASRProvider()
    h = await p.health_check()
    assert h == {"ok": True, "live": False, "detail": "META_API_KEY not set (dev-fallback)"}
    out = await transcribe(b"RIFF....", "audio/wav", "hi")
    # Exact pre-Phase-2 fallback shape — the default path is behavior-identical.
    assert out["provider"] == "dev-fallback" and out["fallback"] is True
    assert out["language"] == "hi" and out["confidence"] is None and out["timestamps"] is None


@pytest.mark.asyncio
async def test_orchestrate_single_engine_default(no_key):
    out = await orch.orchestrate(b"RIFF....", "audio/wav", "en", quality={"issues": []})
    assert out["secondary"] is None
    assert out["comparison"]["verdict"] == "single"
    assert out["primary"]["provider"] == "dev-fallback"
    ev = out["evidence_package"]
    assert ev["model_confidence"] is None  # never invented
    assert "primary evidence" in ev["reliability_note"]
    assert ev["secondary_trigger"].startswith("single-engine")


def test_compare_pure_cases():
    a = {"text": "I need help", "language": "en", "provider": "x", "model_version": "1"}
    assert orch.compare_transcripts(a, None)["verdict"] == "single"
    b = dict(a)
    assert orch.compare_transcripts(a, b)["verdict"] == "agree"
    c = dict(a, text="I need help please")
    d = orch.compare_transcripts(a, c)
    assert d["verdict"] == "disagree" and d["word_diffs"] and d["language_match"] is True
    neg = dict(a, text="I don't need help")
    d2 = orch.compare_transcripts(a, neg)
    assert d2["verdict"] == "disagree" and d2["meaning_divergence"], "negation flip must surface"
    e = {"text": "", "language": "en", "provider": "x", "model_version": "1"}
    assert orch.compare_transcripts(e, dict(e))["verdict"] == "both_empty"


def test_should_run_secondary_matrix(no_key):
    run, reason = orch.should_run_secondary("hello", {"issues": []})
    assert (run, reason) == (False, "single-engine: SECOND_ASR_ENABLED is false")
    # Force cannot conjure an engine that isn't configured.
    run, _ = orch.should_run_secondary("", {"issues": []}, force=True)
    assert run is False
    run, reason = orch.should_run_secondary("", {"issues": ["mostly_silence"]}, force=True)
    assert run is False and "single-engine" in reason


class _StubProvider(ASRProvider):
    name = "stub-secondary"

    async def transcribe(self, data, mime, language_hint="auto", keywords=None):
        return {"text": "I need help please", "language": "en", "provider": "stub-secondary",
                "model_version": "stub-1", "confidence": None, "timestamps": None, "fallback": False}

    def supported_languages(self):
        return ["auto", "en"]

    def supported_formats(self):
        return ["audio/wav"]

    async def health_check(self):
        return {"ok": True, "live": False, "detail": "test stub"}

    def provider_metadata(self):
        return {"name": self.name, "model_version": "stub-1", "live": False}


@pytest.mark.asyncio
async def test_secondary_path_with_stub(monkeypatch, no_key):
    from app.services import asr_providers

    monkeypatch.setitem(asr_providers._REGISTRY, "stub-secondary", _StubProvider())
    monkeypatch.setattr(settings, "SECOND_ASR_ENABLED", True)
    monkeypatch.setattr(settings, "SECOND_ASR_PROVIDER", "stub-secondary")
    run, reason = orch.should_run_secondary("hello", {"issues": ["too_noisy"]})
    assert run is True and reason == "quality-too_noisy"
    run, reason = orch.should_run_secondary("hello", {"issues": []})
    assert run is False and reason == "no-trigger"
    out = await orch.orchestrate(b"RIFF....", "audio/wav", "en", quality={"issues": ["too_noisy"]})
    assert out["secondary"]["provider"] == "stub-secondary"
    assert out["comparison"]["verdict"] == "disagree"
    assert len(out["evidence_package"]["providers"]) == 2
    with pytest.raises(ValueError):
        get_provider("no-such-engine")
    assert primary_provider().name == "meta-asr"


def test_compare_endpoint_single_engine(no_key):
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_asr2.db")
    if os.path.exists("./test_asr2.db"):
        os.remove("./test_asr2.db")
    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    init_db()
    client = TestClient(app)
    r = client.post("/api/v1/auth/register", json={"email": "asr2@test.app", "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    s = client.post("/api/v1/audio/sessions", json={"title": "c"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    out = client.post("/api/v1/transcription/compare", json={"audio_id": up["audio_id"]}, headers=h).json()
    assert out["primary"]["provider"] == "dev-fallback"
    assert out["secondary"] is None
    assert out["comparison"]["verdict"] == "single"
    assert out["evidence_package"]["model_confidence"] is None
