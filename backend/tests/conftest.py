"""Suite-wide test database (Phase 1 fix).

Root cause found 2026-11-01: the app binds its engine at import time, and
pytest imports conftest.py before any test module — but every test module
set DATABASE_URL itself at its own import. Net effect: whichever import ran
first won, and in practice the whole suite silently shared the committed
dev file backend/secondvoice.db. Any schema change then broke API tests
with "no such column" until someone deleted that file by hand.

This conftest pins one fresh DATABASE_URL before any app import, so the
suite always builds the current schema from models. Per-module setenv calls
remain as documentation; conftest wins because it runs first.
"""
import os

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".suite.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = "sqlite:///" + _DB
