"""Phase 7: extended semantic guards, escalation, evidence packaging."""
from app.services import reconstruction_service as rs
from app.services import uncertainty_service as u


def _v(original, proposed):
    return rs.violates_guards(original, proposed)


def test_name_drop_flagged_but_additions_ok():
    assert any("name dropped" in p for p in _v("Call Aarav tomorrow", "Call tomorrow"))
    assert _v("call aarav tomorrow", "Call Aarav tomorrow.") == []


def test_date_time_and_months():
    assert any("date/time" in p for p in _v("Meet at 10:30", "Meet at 11:30"))
    assert any("date/time" in p for p in _v("See you in March", "See you in April"))
    assert _v("Meet at 10:30", "Meet at 10:30 please") == []


def test_modals_conditionals_units():
    assert any("modal" in p for p in _v("I can go", "I must go"))
    assert any("conditional" in p for p in _v("If it rains I stay", "It rains so I stay"))
    assert any("unit" in p for p in _v("Take 2 tablets", "Take 2 spoons"))
    assert _v("I can go tomorrow", "I can go tomorrow.") == []


def test_medical_never_dropped():
    assert any("medical" in p for p in _v("I need help", "I need time"))
    assert _v("I need help", "I need help.") == []
    assert rs.risk_floor("Call the doctor") == "medium"
    assert rs.risk_floor("I need water") == "low"


def test_escalate_logic():
    base = {"original_text": "I need help", "proposed_text": "I need help.",
            "explanation": "ok", "meaning_risk": "low", "needs_clarification": False,
            "clarification_question": "", "abstained": False}
    assert rs.escalate(base, [])["meaning_risk"] == "medium"  # medical floor
    assert rs.escalate({**base, "original_text": "hi"}, [])["meaning_risk"] == "low"
    risk = rs.escalate({**base, "original_text": "hi"},
                       [{"kind": "poor_audio", "severity": "risk", "message": "m"}])
    assert risk["meaning_risk"] == "medium" and "Risk raised" in risk["explanation"]
    div = rs.escalate({**base, "original_text": "hi"},
                      [{"kind": "meaning_divergence", "severity": "risk", "message": "m"}])
    assert div["needs_clarification"] is True
    abst = rs.escalate({**base, "abstained": True}, [{"kind": "x", "severity": "risk"}])
    assert abst["meaning_risk"] == "low"  # abstentions pass through untouched


def test_pack_evidence_carries_secondary():
    multi = {"primary": {"text": "a"}, "secondary": {"text": "b"},
             "comparison": {"verdict": "disagree"},
             "evidence_package": {"providers": [], "model_confidence": None}}
    ev = u.pack_evidence(multi, [{"kind": "x"}])
    assert ev["secondary_text"] == "b" and ev["comparison_verdict"] == "disagree"
    assert ev["uncertainty"] == [{"kind": "x"}]
    ev2 = u.pack_evidence({"evidence_package": {}, "comparison": {}, "secondary": None}, [])
    assert ev2["secondary_text"] is None


def test_suggest_output_carries_evidence_keys():
    import asyncio
    out, _ = asyncio.run(rs.suggest("I need help", {}, [], "en", ""))
    for k in ("evidence_for", "evidence_missing", "uncertainty_reasons"):
        assert k in out, k
    assert out["meaning_risk"] == "medium"  # medical floor via escalate
