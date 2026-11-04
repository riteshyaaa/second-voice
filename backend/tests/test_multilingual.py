"""Phase 4 (Hindi/English only): Devanagari defaults, segment spans,
script checks, translation guards, per-language vocabulary review.
All offline. Marathi support removed."""
import pytest

from app.core.config import settings
from app.services import language_service as ls


def test_devanagari_without_marathi_defaults_hindi():
    r = ls.detect_language("मला बाळासाठी पाणी हवं आहे")
    assert r["language"] == "hi", r
    assert "devanagari-script default" in r["confidence_note"], r


def test_hindi_devanagari_stays_hindi():
    r = ls.detect_language("मुझे पानी चाहिए")
    assert r["language"] == "hi", r
    assert r["ambiguous"] is False


def test_no_close_call_flag_without_marathi():
    r = ls.detect_language("mala nahi hai")
    assert r["language"] == "hi", r
    assert r["ambiguous"] is False, r


def test_unrecognized_latin_stays_english():
    r = ls.detect_language("mala pani pahije please")
    assert r["language"] == "en", r
    assert r["code_switch"] is False
    assert r["languages_present"] == ["en"]


def test_hindi_english_mix_spans():
    r = ls.detect_language("mujhe doctor se milna hai tomorrow")
    assert r["language"] == "hinglish"
    assert {s["lang"] for s in r["spans"]} >= {"hi", "en"}


def test_script_checks():
    assert ls.script_of("मुझे मदद चाहिए") == "native"
    assert ls.script_of("I need help") == "latin"
    assert ls.script_of("mujhe मदद chahiye") == "mixed"
    assert ls.check_script("मुझे मदद चाहिए", "native")["match"] is True
    assert ls.check_script("मुझे मदद चाहिए", "roman")["match"] is False


def test_translation_guards_clean_and_violations():
    assert ls.translation_guards("I need 2 tablets", "मुझे २ गोलियां चाहिए") == []
    assert ls.translation_guards("मुझे मदद चाहिए", "I need help.") == []
    assert any("numbers" in w for w in ls.translation_guards("I need 2 tablets", "I need 3 tablets"))
    assert any("negation" in w for w in ls.translation_guards("I don't want water", "मुझे पानी चाहिए"))
    assert ls.translation_guards("hello", "") == ["empty translation output"]


def test_translate_endpoint_guards_phrasebook(monkeypatch):
    import os

    monkeypatch.setattr(settings, "META_API_KEY", "")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_lang4.db")
    if os.path.exists("./test_lang4.db"):
        os.remove("./test_lang4.db")
    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    init_db()
    client = TestClient(app)
    r = client.post("/api/v1/auth/register", json={"email": "lang4@test.app", "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    out = client.post("/api/v1/languages/translate",
                      json={"text": "मुझे मदद चाहिए", "target": "en"}, headers=h).json()
    assert out["translated"] == "I need help." and out["guard_warnings"] == [], out
    d = client.post("/api/v1/languages/detect?text=mala pani pahije", headers=h).json()
    assert d["language"] == "en", d


def test_vocabulary_language_filter():
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_lang4.db")
    from fastapi.testclient import TestClient

    from app.core.database import init_db
    from app.main import app

    init_db()
    client = TestClient(app)
    r = client.post("/api/v1/auth/register", json={"email": "lang4b@test.app", "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/api/v1/vocabulary", json={"term": "Aarav", "language": "en", "category": "name"}, headers=h)
    client.post("/api/v1/vocabulary", json={"term": "पानी", "language": "hi", "category": "word"}, headers=h)
    all_terms = client.get("/api/v1/vocabulary", headers=h).json()
    assert len(all_terms) == 2
    hi_only = client.get("/api/v1/vocabulary", params={"language": "hi"}, headers=h).json()
    assert [e["term"] for e in hi_only] == ["पानी"]
