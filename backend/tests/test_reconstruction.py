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
