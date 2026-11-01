"""Phase 4: Marathi/Hindi disambiguation, segment spans, script checks,
translation guards, per-language vocabulary review. All offline."""
import pytest

from app.core.config import settings
from app.services import language_service as ls


def test_marathi_devanagari_with_lla():
    r = ls.detect_language("मला बाळासाठी पाणी हवं आहे")
    assert r["language"] == "mr", r
    assert "mr" in r["languages_present"]


def test_marathi_devanagari_lexicon():
    r = ls.detect_language("मला पाणी पाहिजे")
    assert r["language"] == "mr", r


def test_hindi_devanagari_stays_hindi():
    r = ls.detect_language("मुझे पानी चाहिए")
    assert r["language"] == "hi", r
    assert r["ambiguous"] is False


def test_close_call_flagged_ambiguous():
    r = ls.detect_language("mala nahi hai")
    assert r["ambiguous"] is True, r


def test_segment_spans_tag_marathi():
    r = ls.detect_language("mala pani pahije please")
    runs = [(s["lang"], s["tokens"]) for s in r["spans"]]
    assert runs[0][0] == "mr" and runs[-1] == ("en", ["please"]), runs
    assert r["code_switch"] is True
    assert set(r["languages_present"]) >= {"mr", "en"}


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
    assert d["language"] == "mr" and "mr" in d["languages_present"], d


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
    client.post("/api/v1/vocabulary", json={"term": "पाणी", "language": "mr", "category": "word"}, headers=h)
    all_terms = client.get("/api/v1/vocabulary", headers=h).json()
    assert len(all_terms) == 2
    mr_only = client.get("/api/v1/vocabulary", params={"language": "mr"}, headers=h).json()
    assert [e["term"] for e in mr_only] == ["पाणी"]
