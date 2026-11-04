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


def test_label_candidates_sources_and_gating():
    base = rs.rules_only_suggestion("Call Arav tomorrow", {"arav": "Aarav"})
    cands = rs.label_candidates("Call Arav tomorrow", {"arav": "Aarav"}, base,
                                secondary_text="Call Aarav tomorrow",
                                spark_text="Call Aarav tomorrow, please.")
    by_src = {}
    for c in cands:
        by_src.setdefault(c["source"], []).append(c)
    assert "rules" in by_src and "vocab" in by_src
    vocab = by_src["vocab"][0]
    assert "Aarav" in vocab["text"] and vocab["usable"] is True
    alt = [c for c in by_src.get("alternative-asr", []) if c["kind"] == "text"][0]
    assert alt["usable"] is True and alt["guards"] == []
    ctx = by_src["contextual"][0]
    assert ctx["usable"] is True
    assert "acoustic" in by_src  # engines differ -> uncertain spans flagged

    # Guard-violating second reading is kept but marked unusable, never hidden.
    bad = rs.label_candidates("I don't want to go.", {}, base,
                              secondary_text="I want to go.")
    alt2 = [c for c in bad if c["source"] == "alternative-asr" and c["kind"] == "text"][0]
    assert alt2["usable"] is False and alt2["guards"], "negation flip kept, flagged unusable"

    # Identical sides produce no vacuous candidates.
    same = rs.label_candidates("Hello world.", {}, base, secondary_text="Hello world.")
    assert [c for c in same if c["source"] == "alternative-asr"] == []


def test_suggest_output_carries_candidates_offline():
    import asyncio
    out, _ = asyncio.run(rs.suggest("Call Arav tomorrow", {"arav": "Aarav"}, [], "en", ""))
    assert "candidates" in out
    assert {c["source"] for c in out["candidates"]} >= {"rules", "vocab"}


def test_reconstruction_api_returns_and_stores_candidates():
    import io
    import wave

    from fastapi.testclient import TestClient

    from app import models
    from app.core.database import SessionLocal, init_db
    from app.main import app

    init_db()
    client = TestClient(app)
    email = "cand@test.app"
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login",
                        json={"email": email, "password": "password123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        s = models.CommSession(user_id=user.id, title="c", language="en")
        db.add(s)
        db.commit()
        db.refresh(s)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(buf.getvalue())
        tmp.close()
        a = models.AudioAsset(session_id=s.id, file_path=tmp.name, mime="audio/wav",
                              duration_s=1.0, quality={}, consent_stored=False)
        db.add(a)
        db.commit()
        db.refresh(a)
        t = models.Transcript(audio_id=a.id, text_original="Call Arav tomorrow", language="en",
                              provider="dev-fallback", model_version="rules-v1.2",
                              evidence={"secondary_text": "Call Aarav tomorrow",
                                        "comparison": {"verdict": "disagree"},
                                        "uncertainty": []})
        db.add(t)
        db.commit()
        db.refresh(t)
        tid = t.id
    finally:
        db.close()
    # approved correction so the vocab candidate fires (alias arav -> Aarav)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "cand@test.app").first()
        db.add(models.Correction(user_id=user.id, original_text="Call Arav tomorrow",
                                 corrected_text="Call Aarav tomorrow"))
        db.commit()
    finally:
        db.close()
    out = client.post("/api/v1/reconstruction", headers=h, json={"transcript_id": tid})
    assert out.status_code == 200, out.text
    body = out.json()
    srcs = {c["source"] for c in body["candidates"]}
    assert {"rules", "vocab", "alternative-asr", "acoustic"} <= srcs
    assert body["candidates"] and all("usable" in c and "guards" in c or c["kind"] == "uncertain-span"
                                      for c in body["candidates"])
    db = SessionLocal()
    try:
        row = db.query(models.Suggestion).filter(
            models.Suggestion.id == body["suggestion_id"]).first()
        assert row.candidates and {c["source"] for c in row.candidates} == srcs
    finally:
        db.close()
