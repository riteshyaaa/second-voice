"""Seed a demo account with vocabulary + board phrases. Run from repo root:
PYTHONPATH=backend python infrastructure/scripts/seed_demo.py (or via docker)."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.join(_HERE, "..", "..", "backend"), "/srv", os.getcwd()):
    if os.path.isdir(os.path.join(_cand, "app")):
        sys.path.insert(0, _cand)
        break

from app import models
from app.core.database import SessionLocal, init_db
from app.core.security import hash_password

init_db()
db = SessionLocal()
email = "demo@secondvoice.app"
user = db.query(models.User).filter(models.User.email == email).first()
if user is None:
    user = models.User(email=email, password_hash=hash_password("demo1234"), display_name="Demo")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(models.UserPreference(user_id=user.id, preferred_language="hinglish", output_language="hinglish"))
    for term, lang, cat in [("Aarav", "en", "name"), ("dhanyavad", "hinglish", "word"), ("doctor", "en", "word")]:
        db.add(models.VocabularyEntry(user_id=user.id, term=term, normalized=term.lower(), language=lang, category=cat))
    for phrase in ["I need help.", "Please wait.", "मुझे पानी चाहिए।", "Thank you.", "I need a break."]:
        db.add(models.CommMemory(user_id=user.id, kind="phrase", content=phrase))
    db.commit()
    print("demo seeded: demo@secondvoice.app / demo1234")
else:
    print("demo already exists")
