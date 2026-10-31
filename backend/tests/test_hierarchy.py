"""Evidence-hierarchy regression tests (offline).

Audio is primary evidence; the transcript is the ASR system's imperfect
interpretation. These tests pin the framing in prompts, payloads, and plumbing.
"""
from app.services import muse_spark_service as spark
from app.services import prompts
from app.services import reconstruction_service as rs


def test_prompt_frames_transcript_as_imperfect():
    assert "IMPERFECT" in prompts.RECONSTRUCTION_SYSTEM
    assert "asr_interpretation" in prompts.RECONSTRUCTION_SYSTEM
    assert "primary evidence" in prompts.RECONSTRUCTION_SYSTEM.lower()


def test_payload_carries_reliability_and_low_effort():
    p = spark._payload(prompts.RECONSTRUCTION_SYSTEM, {"asr_transcript": "x"}, 2500)
    assert p["instructions"] == prompts.RECONSTRUCTION_SYSTEM
    assert p["reasoning"] == {"effort": "low"}
    assert "max_output_tokens" in p


def test_reliability_forwarded_to_model(monkeypatch):
    seen = {}

    async def fake_reconstruct(transcript, asr_note, vocab, history, language, user_request, reliability=""):
        seen.update(transcript=transcript, asr_note=asr_note, reliability=reliability)

        class S:
            proposed_text = transcript
            explanation = "fake"
            changed_words = []
            alternatives = []
            needs_clarification = False
            clarification_question = ""
            meaning_risk = "low"

        from app.core.providers import ProviderStatus

        return S(), ProviderStatus("meta-spark", "test", True, "live")

    import app.services.reconstruction_service as svc

    monkeypatch.setattr(svc, "meta_available", lambda *a: True)
    monkeypatch.setattr(svc.muse_spark_service, "reconstruct", fake_reconstruct)
    import asyncio

    asyncio.run(svc.suggest("hello.", {}, [], "en", "", reliability="custom-note"))
    assert seen["reliability"] == "custom-note"
    assert "imperfect" in seen["asr_note"]


def test_default_reliability_when_caller_passes_none(monkeypatch):
    seen = {}

    async def fake_reconstruct(transcript, asr_note, vocab, history, language, user_request, reliability=""):
        seen["reliability"] = reliability

        class S:
            proposed_text = transcript
            explanation = "fake"
            changed_words = []
            alternatives = []
            needs_clarification = False
            clarification_question = ""
            meaning_risk = "low"

        from app.core.providers import ProviderStatus

        return S(), ProviderStatus("meta-spark", "test", True, "live")

    import app.services.reconstruction_service as svc

    monkeypatch.setattr(svc, "meta_available", lambda *a: True)
    monkeypatch.setattr(svc.muse_spark_service, "reconstruct", fake_reconstruct)
    import asyncio

    asyncio.run(svc.suggest("hello.", {}, [], "en", ""))
    assert "audio is primary" in seen["reliability"]
