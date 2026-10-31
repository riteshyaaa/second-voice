"""WER/CER metrics + guard report."""
from app.services import evaluation_service as ev


def test_wer_perfect():
    assert ev.wer("hello world", "hello world")["wer"] == 0.0


def test_wer_one_error():
    r = ev.wer("I want to go", "I want go")
    assert r["wer"] == 0.25


def test_cer():
    assert ev.cer("abc", "abc")["cer"] == 0.0


def test_guard_report_flags_negation():
    rep = ev.guard_report("I don't want to go.", "I want to go.")
    assert rep["passed"] is False
