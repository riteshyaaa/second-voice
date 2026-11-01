"""Phase 11: guard category scores, span retention, study harness, interaction."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_evaluation.db")
if os.path.exists("./test_evaluation.db"):
    os.remove("./test_evaluation.db")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app
from app.services import evaluation_harness, evaluation_service, reconstruction_service

init_db()
client = TestClient(app)


def _user(email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_guard_messages_byte_stable():
    assert reconstruction_service.violates_guards("I don't want to go", "I want to go") == [
        "negation changed — intent would reverse"]
    assert reconstruction_service.violates_guards("Take 2 pills", "Take 3 pills") == [
        "number/quantity changed without evidence"]


def test_guard_scores_categories():
    clean = reconstruction_service.guard_scores("Call Aarav at 5 pm", "Call Aarav at 5 pm")
    assert all(clean.values()) and len(clean) == 8
    neg = reconstruction_service.guard_scores("I don't want to go", "I want to go")
    assert neg["negation"] is False
    assert neg["number"] is True and neg["name"] is True
    num = reconstruction_service.guard_scores("Take 2 pills daily", "Take 3 pills daily")
    assert num["number"] is False and num["negation"] is True


def test_preservation_report_math():
    rep = evaluation_service.preservation_report("I don't want to go", "I want to go")
    assert rep["scores"]["negation"] is False
    assert rep["preserved"] == 7 and rep["of"] == 8 and rep["rate"] == 0.875


def test_empty_rate():
    assert evaluation_service.empty_rate(["a", "", "  ", None]) == {"n": 4, "empty": 3, "rate": 0.75}
    assert evaluation_service.empty_rate([]) == {"n": 0, "empty": 0, "rate": 0.0}


def test_span_retention_identical_and_merged():
    ref = [{"lang": "hi", "tokens": ["mujhe"]}, {"lang": "en", "tokens": ["doctor"]}]
    full = evaluation_service.span_retention(ref, ref)
    assert full["per_language"]["hi"]["recall"] == 1.0
    assert full["per_language"]["en"]["recall"] == 1.0
    assert full["boundaries"] == {"n": 1, "kept": 1, "rate": 1.0}
    merged = evaluation_service.span_retention(ref, [{"lang": "hi", "tokens": ["mujhe", "doctor"]}])
    assert merged["per_language"]["en"]["recall"] == 0.0  # language label lost
    assert merged["boundaries"]["rate"] == 0.0
    assert evaluation_service.span_retention([{"lang": "en", "tokens": ["hi"]}], [{"lang": "en", "tokens": ["hi"]}])["boundaries"]["rate"] is None


def test_vocab_from_train_same_length_only():
    vocab = evaluation_harness.vocab_from_train([
        {"original": "call arav today", "reference": "Call Aarav today"},
        {"original": "I want meet doctor", "reference": "I want to meet my doctor"},
    ])
    assert vocab == {"arav": "Aarav"}, vocab  # different-length pair contributes nothing


def test_study_personalization_and_isolation():
    study = {"speakers": {
        "asha": {"train": [{"original": "call arav today", "reference": "Call Aarav today"}],
                 "test": [{"original": "call arav now", "reference": "Call Aarav now"}]},
        "rohan": {"train": [{"original": "meet rohan at five", "reference": "Meet Rohan at five"}],
                  "test": [{"original": "meet rohan soon", "reference": "Meet Rohan soon"}]},
    }}
    out = evaluation_harness.run_study(study)
    asha = out["speakers"]["asha"]
    assert asha["vocab"] == {"arav": "Aarav"}
    case = asha["cases"][0]
    assert "Aarav" in case["personalized"] and "Aarav" not in case["baseline"]
    assert case["personalized_wer"] < case["baseline_wer"]
    assert out["overall"]["mean_personalized_wer"] < out["overall"]["mean_baseline_wer"]
    assert out["leakage"] == {"checks": 2, "leaks": 0}  # vocab never crosses speakers
    assert "offline deterministic" in out["scope"]


def test_study_endpoint_and_compare_still_green():
    h = _user("eval11@test.app")
    study = {"speakers": {"x": {"train": [], "test": [{"original": "Take 2 pills", "reference": "Take 2 pills"}]}}}
    r = client.post("/api/v1/evaluation/study", json=study, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["overall"]["mean_baseline_wer"] == 0.0
    assert client.post("/api/v1/evaluation/study", json={}, headers=h).json()["overall"]["speakers"] == 0
    assert client.post("/api/v1/evaluation/study", json=study).status_code in (401, 403)
    cmp = client.get("/api/v1/evaluation/compare",
                     params={"reference": "hello world", "hypothesis": "hello world"}, headers=h).json()
    assert cmp["wer"]["wer"] == 0.0 and cmp["guards"]["passed"] is True


def test_interaction_endpoint_keys_and_isolation():
    h1 = _user("interact1@test.app")
    h2 = _user("interact2@test.app")
    r1 = client.get("/api/v1/evaluation/interaction", headers=h1).json()
    assert r1["confirmed_messages"] == 0
    assert r1["tts_success_rate"] is None
    assert "session start" in r1["note"]
    assert client.get("/api/v1/evaluation/interaction").status_code in (401, 403)
    # second user's card tap (a confirmation + TTS event) must not leak into the first user
    cards = client.get("/api/v1/cards", headers=h2).json()
    assert client.post(f"/api/v1/cards/{cards[0]['id']}/speak", headers=h2).status_code == 200
    r2 = client.get("/api/v1/evaluation/interaction", headers=h2).json()
    assert r2["confirmed_messages"] >= 1
    assert r2["tts_requests"] >= 1 and r2["tts_success_rate"] == 1.0
    assert r2["confirm_timed_n"] == 0  # card taps have no session: excluded from timing
    r1b = client.get("/api/v1/evaluation/interaction", headers=h1).json()
    assert r1b["confirmed_messages"] == 0 and r1b["tts_requests"] == 0
