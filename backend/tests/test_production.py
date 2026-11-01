"""Phase 12: bounded Meta retries, auth rate limiting, never-block startup."""
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_production.db")
if os.path.exists("./test_production.db"):
    os.remove("./test_production.db")

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import init_db
from app.core.config import settings
from app.middleware import rate_limit
from app.middleware.rate_limit import AuthRateLimitMiddleware
from app.services import meta_http
from app.services.meta_http import MetaHTTPError, meta_post

init_db()


class _StubClient:
    """Stand-in for httpx.AsyncClient: scripted raise/response sequence."""
    behavior: list = []
    calls: int = 0

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        type(self).calls += 1
        kind = type(self).behavior.pop(0)
        if kind[0] == "raise":
            raise kind[1]
        return httpx.Response(kind[1], text=kind[2],
                              request=httpx.Request("POST", "http://x.test/"))


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(meta_http.httpx, "AsyncClient", _StubClient)
    monkeypatch.setattr(settings, "META_RETRY_BACKOFF_S", 0.0)
    _StubClient.calls = 0
    return _StubClient


def _call(**kw):
    args = dict(url="http://x.test/", label="t", model="m", headers={},
                timeout_s=5.0, content={"json": {}})
    args.update(kw)
    return asyncio.run(meta_post(**args))


def test_transport_retry_then_success(stub):
    stub.behavior = [("raise", httpx.ConnectError("down")), ("resp", 200, "ok")]
    assert _call().text == "ok"
    assert stub.calls == 2


def test_429_retried_then_success(stub):
    stub.behavior = [("resp", 429, "slow"), ("resp", 200, "ok")]
    assert _call().text == "ok"
    assert stub.calls == 2


def test_400_not_retried(stub):
    stub.behavior = [("resp", 400, "bad"), ("resp", 200, "ok")]
    with pytest.raises(MetaHTTPError) as e:
        _call()
    assert e.value.status == 400
    assert stub.calls == 1  # retrying a 400 can never succeed


def test_retries_exhausted_raises_last(stub):
    stub.behavior = [("raise", httpx.ConnectError("a")), ("raise", httpx.ConnectError("b"))]
    with pytest.raises(httpx.ConnectError):
        _call()
    assert stub.calls == 1 + settings.META_RETRIES


def _limited_app():
    app = FastAPI()
    app.add_middleware(AuthRateLimitMiddleware)

    @app.post("/api/v1/auth/login")
    def login():
        return {"ok": True}

    @app.get("/api/v1/memory")
    def memory():
        return {"ok": True}

    return app


def test_auth_rate_limited_per_minute(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    rate_limit.reset()
    client = TestClient(_limited_app())
    assert client.post("/api/v1/auth/login").status_code == 200
    assert client.post("/api/v1/auth/login").status_code == 200
    r = client.post("/api/v1/auth/login")
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "RATE_LIMITED"
    assert r.json()["detail"]["retryable"] is True


def test_non_auth_paths_unaffected(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    rate_limit.reset()
    client = TestClient(_limited_app())
    for _ in range(5):
        assert client.get("/api/v1/memory").status_code == 200


def test_startup_never_blocked_by_broken_migrations(monkeypatch):
    import alembic.command as alembic_command

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg2://nobody@localhost/nowhere")
    monkeypatch.setattr(alembic_command, "upgrade", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("broken")))
    monkeypatch.setattr(alembic_command, "stamp", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("broken")))
    init_db()  # must not raise: fallback path absorbs both failures
    monkeypatch.undo()
