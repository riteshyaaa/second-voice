"""Phase 3: uncertainty indicators are observable-only and persisted.

No phoneme/acoustic claims anywhere: every indicator kind comes from a
fixed set derived from provider outputs, comparison, quality, and length.
"""
import pytest

from app.services import uncertainty_service as u

KNOWN_KINDS = {"no_confidence", "manual_entry", "single_engine", "empty_output",
               "very_short", "disagreement", "meaning_divergence",
               "language_mismatch", "poor_audio", "audio_quality"}


def _primary(text="hello there friend", provider="meta-asr"):
    return {"text": text, "language": "en", "provider": provider, "model_version": "m"}


def _kinds(inds):
    return {i["kind"] for i in inds}


def test_no_confidence_always_present_and_kinds_closed():
    inds = u.summarize(_primary(), {"verdict": "single"}, {"issues": []})
    kinds = _kinds(inds)
    assert "no_confidence" in kinds and "single_engine" in kinds
    assert kinds <= KNOWN_KINDS, kinds - KNOWN_KINDS
    assert all(set(i) == {"kind", "severity", "message"} for i in inds)


def test_manual_entry_short_circuits():
    inds = u.summarize(_primary("typed words", "manual-entry"), {"verdict": "single"}, None)
    assert _kinds(inds) == {"manual_entry", "no_confidence"}


def test_empty_is_risk_and_stops():
    inds = u.summarize(_primary(""), {"verdict": "single"}, {"issues": []})
    by_kind = {i["kind"]: i for i in inds}
    assert by_kind["empty_output"]["severity"] == "risk"
    assert "very_short" not in by_kind  # empty returns before length checks


def test_disagreement_and_divergence_surface():
    comp = {"verdict": "disagree", "meaning_divergence": ["negation changed — intent would reverse"],
            "language_match": False}
    inds = u.summarize(_primary("I want to go"), comp, {"issues": []})
    by_kind = {i["kind"]: i for i in inds}
    assert by_kind["disagreement"]["severity"] == "watch"
    assert by_kind["meaning_divergence"]["severity"] == "risk"
    assert by_kind["language_mismatch"]["severity"] == "watch"


def test_quality_mapping():
    inds = u.summarize(_primary(), {"verdict": "agree", "meaning_divergence": []}, {"issues": ["too_noisy"]})
    assert {i["kind"]: i["severity"] for i in inds}["audio_quality"] == "watch"
    inds = u.summarize(_primary(), {"verdict": "agree", "meaning_divergence": []}, {"issues": ["mostly_silence"]})
    assert {i["kind"]: i["severity"] for i in inds}["poor_audio"] == "risk"


def test_short_transcript_flagged():
    inds = u.summarize(_primary("paani"), {"verdict": "single"}, {"issues": []})
    assert "very_short" in _kinds(inds)


def test_reliability_text():
    inds = u.summarize(_primary(), {"verdict": "single"}, {"issues": ["too_noisy"]})
    note = u.reliability_text("meta-asr", "m", "en", inds)
    assert "meta-asr/m" in note and "primary evidence" in note and "too_noisy" in note
    note2 = u.reliability_text("meta-asr", "m", "en", inds, confidence=0.9)
    assert "word-level confidence 0.9" in note2


def test_manual_transcript_persists_evidence():
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_uncert.db")
    if os.path.exists("./test_uncert.db"):
        os.remove("./test_uncert.db")
    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    init_db()
    client = TestClient(app)
    r = client.post("/api/v1/auth/register", json={"email": "uncert@test.app", "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    s = client.post("/api/v1/audio/sessions", json={"title": "u"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": up["audio_id"], "manual_transcript": "typed words here", "language": "en"},
                    headers=h).json()
    assert {i["kind"] for i in t["uncertainty"]} == {"manual_entry", "no_confidence"}
    detail = client.get(f"/api/v1/sessions/{s['id']}", headers=h).json()
    assert detail["items"][0]["uncertainty"] == t["uncertainty"]
    # reconstruction consumes stored evidence without breaking
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    assert sg["proposed_text"]
