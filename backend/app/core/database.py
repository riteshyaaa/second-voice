"""SQLAlchemy session + table creation (Alembic migration mirrors this schema)."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _engine():
    url = settings.DATABASE_URL
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        path = url.replace("sqlite:///", "")
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    return create_engine(url, **kwargs)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_ini() -> str | None:
    import app as _app

    ini = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(_app.__file__)), "..", "alembic.ini"))
    return ini if os.path.exists(ini) else None


def init_db() -> None:
    """Phase 12: postgres databases migrate on startup (`upgrade head`).
    Legacy path (create_all + stamp) is kept as a fallback so a broken
    migration state can never block startup; sqlite stays unmanaged."""
    import logging as _logging

    log = _logging.getLogger("secondvoice")
    from app import models  # noqa: F401  (register tables)

    if not settings.DATABASE_URL.startswith("sqlite"):
        try:
            from alembic import command
            from alembic.config import Config

            ini = _alembic_ini()
            if ini is None:
                log.warning("alembic.ini not found; using create_all fallback")
            else:
                command.upgrade(Config(ini), "head")
                log.info("alembic upgrade head ok")
                return
        except Exception as exc:
            log.warning("alembic upgrade failed, create_all fallback: %r", exc)
        Base.metadata.create_all(bind=engine)
        try:
            from alembic import command
            from alembic.config import Config

            ini = _alembic_ini()
            if ini is not None:
                command.stamp(Config(ini), "head")
                log.info("stamped alembic head (%s)", ini)
        except Exception as exc:
            log.warning("alembic stamp skipped: %r", exc)
        return
    # local/test databases are not alembic-managed; stamping would point at
    # the ini's postgres URL and block on connect.
    Base.metadata.create_all(bind=engine)
