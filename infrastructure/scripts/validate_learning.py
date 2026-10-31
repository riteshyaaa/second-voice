"""Live learning-loop + isolation + confirmation-gate battery via backend API.

Uses TestClient (in-process) with the real META_API_KEY from repo .env
(never printed) and REAL cached speech for the first transcription.
Writes validation_learning_results.json (committed evidence).
"""
import json
import os
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "backend"))

SCRATCH = os.path.join(tempfile.gettempdir(), "sv-validation.db")
if os.path.exists(SCRATCH):
    os.remove(SCRATCH)
os.environ["DATABASE_URL"] = "sqlite:///" + SCRATCH
os.environ["STORAGE_DIR"] = os.path.join(tempfile.gettempdir(), "sv-validation-audio")
with open(os.path.join(_HERE, "..", "..", ".env")) as f:
    for line in f:
        line = line.strip()
        if line.startswith("META_API_KEY="):
            os.environ["META_API_KEY"] = line.split("=", 1)[1]

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)
CHECKS: list[dict] = []


def check(name, ok, detail=""):
    CHECKS.append({"check": name, "pass": bool(ok), "detail": str(detail)[:200]})
    safe = str(detail).encode("ascii", "backslashreplace").decode()
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {safe[:120]}")


def register(email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def main():
    a = register("asha-valid@test.app")
    b = register("bima-valid@test.app")

    # ---- 1. real-audio transcription (live ASR) ----
    with open(os.path.join(tempfile.gettempdir(), "sv-corpus", "hi_paani.bin"), "rb") as f:
        paani = f.read()
    s1 = client.post("/api/v1/audio/sessions", json={"title": "s1", "language": "hi"}, headers=a).json()
    up = client.post(f"/api/v1/audio/sessions/{s1['id']}/audio", content=paani,
                     headers={**a, "Content-Type": "audio/wav"}).json()
    t0 = time.time()
    tr = client.post("/api/v1/transcription", json={"audio_id": up["audio_id"]}, headers=a)
    check("live transcription via API", tr.status_code == 200, f"{tr.status_code} {tr.text[:100]}")
    tr = tr.json()
    tid, orig = tr["transcript_id"], tr["text_original"]
    check("live provider labelled meta-asr", tr.get("provider") == "meta-asr", tr.get("provider"))

    # ---- 2. reconstruct (live Spark) ----
    t0 = time.time()
    rc = client.post("/api/v1/reconstruction", json={"transcript_id": tid}, headers=a)
    check("reconstruction via API", rc.status_code == 200, f"{rc.status_code}")
    sug = rc.json()["suggestion_id"]

    # ---- 3. user correction WITH consent -> saved ----
    fb = client.post("/api/v1/feedback",
                     json={"suggestion_id": sug, "final_text": "पानी", "kind": "edit", "save": True}, headers=a)
    stats = client.get("/api/v1/feedback/stats", headers=a).json()
    check("correction saved with consent", fb.status_code == 200 and stats["corrections_approved"] >= 1,
          f"corrections={stats['corrections_approved']}")
    learning = client.get("/api/v1/learning", headers=a).json()
    check("learning events visible", len(learning) >= 1, f"{len(learning)} events")

    # ---- 4. reuse in a FUTURE session (deterministic manual transcript of the mishearing) ----
    s2 = client.post("/api/v1/audio/sessions", json={"title": "s2", "language": "hi"}, headers=a).json()
    up2 = client.post(f"/api/v1/audio/sessions/{s2['id']}/audio", content=paani,
                      headers={**a, "Content-Type": "audio/wav"}).json()
    man = client.post("/api/v1/transcription/manual",
                      params={"audio_id": up2["audio_id"], "manual_transcript": orig, "language": "hi"}, headers=a).json()
    rc2 = client.post("/api/v1/reconstruction", json={"transcript_id": man["transcript_id"]}, headers=a).json()
    check("approved correction reused next session", "पानी" in rc2["proposed_text"],
          rc2["proposed_text"][:80])

    # ---- 5. consent OFF blocks learning ----
    client.patch("/api/v1/preferences", json={"learning_enabled": False}, headers=a)
    before = client.get("/api/v1/feedback/stats", headers=a).json()["corrections_approved"]
    client.post("/api/v1/feedback", json={"suggestion_id": sug, "final_text": "पानी पानी", "kind": "edit", "save": True}, headers=a)
    after = client.get("/api/v1/feedback/stats", headers=a).json()["corrections_approved"]
    check("learning disabled blocks saving", before == after, f"{before}->{after}")
    client.patch("/api/v1/preferences", json={"learning_enabled": True}, headers=a)

    # ---- 6. rejections need opt-in ----
    n0 = len([e for e in client.get("/api/v1/learning", headers=a).json() if e["kind"] == "rejection"])
    client.post("/api/v1/feedback", json={"suggestion_id": sug, "final_text": "x", "kind": "reject"}, headers=a)
    n1 = len([e for e in client.get("/api/v1/learning", headers=a).json() if e["kind"] == "rejection"])
    client.patch("/api/v1/preferences", json={"save_rejections": True}, headers=a)
    client.post("/api/v1/feedback", json={"suggestion_id": sug, "final_text": "x", "kind": "reject"}, headers=a)
    n2 = len([e for e in client.get("/api/v1/learning", headers=a).json() if e["kind"] == "rejection"])
    check("rejections opt-in only", n0 == n1 and n2 == n1 + 1, f"{n0}/{n1}/{n2}")
    client.patch("/api/v1/preferences", json={"save_rejections": False}, headers=a)

    # ---- 7. vocab + memory CRUD ----
    v = client.post("/api/v1/vocabulary", json={"term": "Dilli", "language": "hi", "category": "place"}, headers=a).json()
    names = [e["term"] for e in client.get("/api/v1/vocabulary", headers=a).json()]
    d = client.delete(f"/api/v1/vocabulary/{v['id']}", headers=a)
    names2 = [e["term"] for e in client.get("/api/v1/vocabulary", headers=a).json()]
    check("vocab add/list/delete", "Dilli" in names and d.status_code == 200 and "Dilli" not in names2)
    m = client.post("/api/v1/memory", json={"kind": "phrase", "content": "test phrase", "language": "en"}, headers=a).json()
    d2 = client.delete(f"/api/v1/memory/{m['id']}", headers=a)
    check("memory add/delete", d2.status_code == 200)

    # ---- 8. confirmed text never silently modified ----
    exact = "Paani, PLEASE."
    cf = client.post("/api/v1/confirmation",
                     json={"suggestion_id": sug, "final_text": exact, "language": "en", "source": "edited",
                           "save_as_learning": False}, headers=a).json()
    det = client.get(f"/api/v1/sessions/{s1['id']}", headers=a).json()
    approved = [x["text"] for x in det["approved"]]
    check("confirmed text stored verbatim", exact in approved, approved)
    t0 = time.time()
    sy = client.post("/api/v1/speech/synthesize", json={"approved_message_id": cf["approved_message_id"]}, headers=a)
    check("synthesize confirmed via API", sy.status_code == 200, f"{sy.status_code} {sy.text[:100]}")
    au = client.get(sy.json()["audio_url"], headers=a)
    check("spoken audio retrievable", au.status_code == 200 and len(au.content) > 1000, len(au.content))

    # ---- 9. gate: unconfirmed / foreign / forged / anonymous ----
    db = SessionLocal()
    rogue = models.ApprovedMessage(user_id=1, session_id=s1["id"], suggestion_id=None,
                                   transcript_id=tid, final_text="never confirmed", language="en", source="edited")
    # fix user id to asha's real id
    me = client.get("/api/v1/auth/me", headers=a).json()
    rogue.user_id = me["id"]
    db.add(rogue)
    db.commit()
    db.refresh(rogue)
    rogue_id = rogue.id
    db.close()
    g1 = client.post("/api/v1/speech/synthesize", json={"approved_message_id": rogue_id}, headers=a)
    check("unconfirmed text rejected (409)", g1.status_code == 409 and "UNCONFIRMED" in g1.text, g1.status_code)
    g2 = client.post("/api/v1/speech/synthesize", json={"approved_message_id": cf["approved_message_id"]}, headers=b)
    check("cross-user synthesize rejected (404)", g2.status_code == 404, g2.status_code)
    g3 = client.post("/api/v1/speech/synthesize", json={"approved_message_id": 999999}, headers=a)
    check("forged id rejected (404)", g3.status_code == 404, g3.status_code)
    g4 = client.post("/api/v1/speech/synthesize", json={"approved_message_id": cf["approved_message_id"]})
    check("anonymous synthesize rejected (401/403)", g4.status_code in (401, 403), g4.status_code)

    # ---- 10. isolation ----
    check("sessions isolated", client.get("/api/v1/sessions", headers=b).json() == [], "b sees none")
    check("session detail isolated", client.get(f"/api/v1/sessions/{s1['id']}", headers=b).status_code == 404)
    check("vocab isolated", client.get("/api/v1/vocabulary", headers=b).json() == [])
    check("memory isolated", client.get("/api/v1/memory", headers=b).json() == [])

    # ---- 11. full wipe ----
    w = client.delete("/api/v1/account/data", headers=a)
    st = client.get("/api/v1/feedback/stats", headers=a).json()
    check("account wipe clears learning", w.status_code == 200 and st["corrections_approved"] == 0, st)

    with open(os.path.join(_HERE, "validation_learning_results.json"), "w", encoding="utf-8") as f:
        json.dump(CHECKS, f, ensure_ascii=False, indent=1)
    n = sum(1 for c in CHECKS if c["pass"])
    print(f"PASSED {n}/{len(CHECKS)}")


if __name__ == "__main__":
    main()
