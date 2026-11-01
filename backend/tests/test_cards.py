"""Phase 9: communication cards — seeds, CRUD, tap-to-speak, isolation."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_cards.db")
if os.path.exists("./test_cards.db"):
    os.remove("./test_cards.db")

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app

init_db()
client = TestClient(app)


def _user(email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    if r.status_code == 409:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_seeds_once_with_categories():
    h = _user("cards@test.app")
    first = client.get("/api/v1/cards", headers=h).json()
    assert len(first) == 12, len(first)
    cats = {c["category"] for c in first}
    assert {"needs", "requests", "feelings", "questions", "emergency", "personal"} <= cats
    assert all(c["emoji"] and c["phrase"] for c in first)
    help_card = [c for c in first if c["label"] == "I need help."][0]
    assert help_card["label_native"] == "मुझे मदद चाहिए"
    second = client.get("/api/v1/cards", headers=h).json()
    assert len(second) == 12  # no duplicates on re-list
    needs = client.get("/api/v1/cards", params={"category": "needs"}, headers=h).json()
    assert needs and all(c["category"] == "needs" for c in needs)


def test_crud_favorite_and_isolation():
    h = _user("cards2@test.app")
    client.get("/api/v1/cards", headers=h)
    c = client.post("/api/v1/cards", json={"label": "Pाणी हवं", "language": "mr", "emoji": "💧",
                                           "category": "needs", "phrase": "मला पाणी हवं आहे"}, headers=h).json()
    assert c["language"] == "mr" and c["favorite"] is False
    assert client.post("/api/v1/cards", json={"label": "x", "category": "nope", "phrase": "x"},
                       headers=h).status_code == 422
    e = client.patch(f"/api/v1/cards/{c['id']}", json={"favorite": True}, headers=h).json()
    assert e["favorite"] is True
    favs = client.get("/api/v1/cards", params={"favorites": True}, headers=h).json()
    assert [x["id"] for x in favs] == [c["id"]]
    other = _user("cards-other@test.app")
    assert client.get("/api/v1/cards", headers=other).json() != []
    assert client.patch(f"/api/v1/cards/{c['id']}", json={"favorite": False}, headers=other).status_code == 404
    assert client.delete(f"/api/v1/cards/{c['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/cards/{c['id']}", headers=h).json() == {"deleted": c["id"]}


def test_tap_to_speak_uses_confirmed_path():
    h = _user("cards3@test.app")
    cards = client.get("/api/v1/cards", headers=h).json()
    help_card = [c for c in cards if c["label"] == "I need help."][0]
    sp = client.post(f"/api/v1/cards/{help_card['id']}/speak", headers=h).json()
    assert "audio_url" in sp, sp
    audio = client.get(sp["audio_url"], headers=h)
    assert audio.status_code == 200 and audio.headers["content-type"].startswith("audio")
    assert client.post("/api/v1/cards/999999/speak", headers=h).status_code == 404


def test_illustrate_honest_unavailable():
    h = _user("cards4@test.app")
    cards = client.get("/api/v1/cards", headers=h).json()
    r = client.post(f"/api/v1/cards/{cards[0]['id']}/illustrate", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "IMAGE_UNAVAILABLE"


def test_export_and_wipe_cover_cards():
    h = _user("cards5@test.app")
    cards = client.get("/api/v1/cards", headers=h).json()
    exp = client.post("/api/v1/account/data", headers=h).json()
    assert len(exp["cards"]) == 12
    client.patch(f"/api/v1/cards/{cards[0]['id']}", json={"favorite": True}, headers=h)
    assert client.delete("/api/v1/account/data", headers=h).json() == {"deleted": True}
    relisted = client.get("/api/v1/cards", headers=h).json()
    assert len(relisted) == 12  # re-seeded defaults...
    assert all(c["favorite"] is False for c in relisted)  # ...proving the wipe cleared the favorited rows
