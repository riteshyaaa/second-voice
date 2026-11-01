"""Phase 8: targeted questions, answer/skip, blocker gate, audio replay."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_clarify.db")
if os.path.exists("./test_clarify.db"):
    os.remove("./test_clarify.db")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app
from app.services import clarification_service as cs

init_db()
client = TestClient(app)


def _user(email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _primary(text):
    return {"text": text, "language": "en", "provider": "meta-asr", "model_version": "m"}


def test_builder_divergence_blocker():
    ev = {"secondary_text": "I don't want to go", "uncertainty": [],
          "providers": [{"name": "meta-asr"}, {"name": "second"}]}
    qs = cs.build_questions("I want to go", ev, None, [], "meta-asr", "second")
    assert len(qs) == 1 and qs[0]["severity"] == "blocks_speech", qs
    assert len(qs[0]["options"]) == 2
    assert qs[0]["options"][0]["source"] == "meta-asr reading"


def test_builder_quiet_when_nothing_uncertain():
    ev = {"secondary_text": None, "uncertainty": [{"kind": "single_engine", "severity": "info", "message": "m"}],
          "providers": [{"name": "meta-asr"}]}
    assert cs.build_questions("I need help", ev, None, [], "meta-asr", None) == []
    fb = cs.build_questions("I need help",
                            {"secondary_text": None, "uncertainty": [], "providers": []},
                            {"needs_clarification": True, "clarification_question": "Which word?",
                             "alternatives": []}, [], "manual-entry", None)
    assert len(fb) == 1 and fb[0]["severity"] == "advisory" and fb[0]["options"] == []


def test_builder_ambiguous_pattern_and_cap():
    names = ["wa", "wb", "wc", "wd", "we"]
    pats = [{"from": w, "to": f"{w}-a", "count": 2, "sources": ["correction"], "ambiguous": True} for w in names]
    pats += [{"from": w, "to": f"{w}-b", "count": 1, "sources": ["correction"], "ambiguous": True} for w in names]
    qs = cs.build_questions("wa wb wc wd we here", {"secondary_text": None, "uncertainty": [],
                                                    "providers": []}, None, pats, "m", None)
    assert len(qs) == 3, qs  # capped, one per term
    assert all(q["severity"] == "blocks_speech" for q in qs)
    assert {o["label"] for o in qs[0]["options"]} == {"wa-a", "wa-b"}
    # single stable reading asks nothing
    stable = [{"from": "arav", "to": "Aarav", "count": 4, "sources": ["correction"], "ambiguous": False}]
    assert cs.build_questions("Arav is here", {"secondary_text": None, "uncertainty": [],
                                               "providers": []}, None, stable, "m", None) == []


def test_trivial_diffs_never_interrogated():
    assert cs._trivial_diff({"from": "the", "to": "a"}) is True
    assert cs._trivial_diff({"from": "go", "to": "go home"}) is False


def test_answers_and_blockers():
    q = {"id": "q1", "options": [{"id": "q1a", "label": "there", "source": "x"}]}
    assert cs.apply_answer(q, "select", "q1a")["label"] == "there"
    try:
        cs.apply_answer(q, "select", "q9")
        assert False, "bad option must fail"
    except ValueError:
        pass
    try:
        cs.apply_answer(q, "type", "   ")
        assert False, "empty type must fail"
    except ValueError:
        pass
    try:
        cs.apply_answer(q, "yell", "x")
        assert False, "unknown kind must fail"
    except ValueError:
        pass
    sk = cs.apply_answer(q, "skip", None)
    assert sk["skipped"] is True
    qs = [{"id": "q1", "severity": "blocks_speech"}, {"id": "q2", "severity": "advisory"}]
    assert [x["id"] for x in cs.unresolved_blockers(qs, {})] == ["q1"]
    assert cs.unresolved_blockers(qs, {"q1": sk}) == []


def _correct(h, audio_id, original, corrected):
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": audio_id, "manual_transcript": original, "language": "en"},
                    headers=h).json()
    sg = client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()
    client.post("/api/v1/feedback", json={"suggestion_id": sg["suggestion_id"], "final_text": corrected}, headers=h)


def _suggest(h, audio_id, text):
    t = client.post("/api/v1/transcription/manual",
                    params={"audio_id": audio_id, "manual_transcript": text, "language": "en"},
                    headers=h).json()
    return client.post("/api/v1/reconstruction", json={"transcript_id": t["transcript_id"]}, headers=h).json()


def test_end_to_end_block_answer_confirm_replay():
    h = _user("clarify@test.app")
    s = client.post("/api/v1/audio/sessions", json={"title": "c"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    _correct(h, up["audio_id"], "Arav is here", "Aarav is there")
    _correct(h, up["audio_id"], "Arav is here", "Aarav is home")
    sg = _suggest(h, up["audio_id"], "Arav is here")
    q = client.get(f"/api/v1/reconstruction/questions/{sg['suggestion_id']}", headers=h).json()
    assert q["unresolved_blockers"] == ["q1"], q
    assert {o["label"] for o in q["questions"][0]["options"]} == {"there", "home"}
    assert q["audio_url"].endswith(f"/audio/{up['audio_id']}")
    # blocked without resolution
    r = client.post("/api/v1/confirmation",
                    json={"suggestion_id": sg["suggestion_id"], "final_text": "Aarav is there", "language": "en"},
                    headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "CLARIFICATION_PENDING"
    # answer then confirm
    opt = [o["id"] for o in q["questions"][0]["options"] if o["label"] == "there"][0]
    a = client.post(f"/api/v1/reconstruction/questions/{sg['suggestion_id']}/answer",
                    json={"question_id": "q1", "kind": "select", "value": opt}, headers=h).json()
    assert a["unresolved_blockers"] == []
    c = client.post("/api/v1/confirmation",
                    json={"suggestion_id": sg["suggestion_id"], "final_text": "Aarav is there", "language": "en"},
                    headers=h).json()
    assert "approved_message_id" in c and "forced" not in c
    # replay serves the original bytes
    ar = client.get(q["audio_url"], headers=h)
    assert ar.status_code == 200 and ar.headers["content-type"].startswith("audio")
    # bad answers rejected
    assert client.post(f"/api/v1/reconstruction/questions/{sg['suggestion_id']}/answer",
                       json={"question_id": "q9", "kind": "skip"}, headers=h).status_code == 404
    assert client.post(f"/api/v1/reconstruction/questions/{sg['suggestion_id']}/answer",
                       json={"question_id": "q1", "kind": "select", "value": "q1zzz"}, headers=h).status_code == 422


def test_skip_and_force_paths():
    h = _user("clarify2@test.app")
    s = client.post("/api/v1/audio/sessions", json={"title": "c"}, headers=h).json()
    up = client.post(f"/api/v1/audio/sessions/{s['id']}/audio", content=b"RIFF....",
                     headers={**h, "Content-Type": "audio/wav"}).json()
    _correct(h, up["audio_id"], "Arav is here", "Aarav is there")
    _correct(h, up["audio_id"], "Arav is here", "Aarav is home")
    sg = _suggest(h, up["audio_id"], "Arav is here")
    # force override is audited
    c = client.post("/api/v1/confirmation",
                    json={"suggestion_id": sg["suggestion_id"], "final_text": "Aarav is there",
                          "language": "en", "force": True}, headers=h).json()
    assert c.get("forced") is True and c["forced_over"] == ["q1"], c
    # skip also unblocks, preserving uncertainty
    sg2 = _suggest(h, up["audio_id"], "Arav is here")
    sk = client.post(f"/api/v1/reconstruction/questions/{sg2['suggestion_id']}/answer",
                     json={"question_id": "q1", "kind": "skip"}, headers=h).json()
    assert sk["recorded"]["skipped"] is True and sk["unresolved_blockers"] == []
    c2 = client.post("/api/v1/confirmation",
                     json={"suggestion_id": sg2["suggestion_id"], "final_text": "Aarav is there", "language": "en"},
                     headers=h).json()
    assert "approved_message_id" in c2
    # isolation: another user sees nothing
    other = _user("clarify-other@test.app")
    assert client.get(f"/api/v1/reconstruction/questions/{sg['suggestion_id']}", headers=other).status_code == 404
