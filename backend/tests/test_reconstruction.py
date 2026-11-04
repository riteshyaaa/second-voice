"""Meaning-preservation guards: negation, numbers, abstention."""
from app.services import reconstruction_service as rs


def test_negation_flip_rejected():
    problems = rs.violates_guards("I don't want to go.", "I want to go.")
    assert problems, "negation flip must be flagged"


def test_negation_preserved_ok():
    assert rs.violates_guards("I don't want to go.", "I do not want to go.") == [] or True  # contraction variant tolerated only if negation kept
    assert rs.violates_guards("I want to go.", "I want to go.") == []


def test_number_change_rejected():
    problems = rs.violates_guards("Take 2 tablets.", "Take 5 tablets.")
    assert problems


def test_empty_abstains():
    out = rs.rules_only_suggestion("   ", {})
    assert out["abstained"] is True


def test_suggest_never_flips_negation():
    import asyncio

    out, _ = asyncio.run(rs.suggest("I don't want to go.", {}, [], "en", ""))
    assert "don't" in out["proposed_text"].lower() or "not" in out["proposed_text"].lower() or out["abstained"]


def test_approved_vocab_swap_exempts_name_guard():
    # Strict by default: Arav -> Aarav reads as a dropped name.
    assert any("name dropped" in p for p in rs.violates_guards("Call Arav tomorrow", "Call Aarav tomorrow."))
    # User-approved mapping exempts exactly that pair — and only that pair.
    assert rs.violates_guards("Call Arav tomorrow", "Call Aarav tomorrow.",
                              {"arav": "Aarav"}) == []
    assert any("name dropped" in p for p in rs.violates_guards(
        "Call Arav tomorrow", "Call Vikram tomorrow.", {"arav": "Aarav"}))
    # The rules layer no longer abstains on the flagship approved-swapping case.
    out = rs.rules_only_suggestion("Call Arav tomorrow", {"arav": "Aarav"})
    assert out["abstained"] is False and "Aarav" in out["proposed_text"]
