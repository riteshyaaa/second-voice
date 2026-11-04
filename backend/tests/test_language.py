"""Language detect: en/hi/hinglish + preservation (no auto-translate)."""
from app.services import language_service as ls


def test_hindi_devanagari():
    assert ls.detect_language("मुझे मदद चाहिए")["language"] == "hi"


def test_hinglish_code_switch():
    r = ls.detect_language("mujhe doctor se milna hai tomorrow")
    assert r["language"] == "hinglish" and r["code_switch"] is True


def test_english():
    assert ls.detect_language("I need some water please")["language"] == "en"


def test_unsupported_latin_defaults_english():
    # No Marathi support: unrecognized Latin words are not assigned anywhere.
    assert ls.detect_language("mala pani pahije")["language"] == "en"


def test_explicit_translation_keeps_original():
    out = ls.translate_explicit("मुझे मदद चाहिए", "en")
    assert out["text"] == "I need help."
    # unknown mapping preserves original, never invents
    out2 = ls.translate_explicit("xyzzy blorp", "hi")
    assert out2["text"] == "xyzzy blorp"
