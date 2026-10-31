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


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)
    # Stamp the alembic version so `upgrade head` also works on databases
    # whose tables were created here (verified: fresh `up` + `upgrade head`
    # failed before this with "table already exists").
    try:
        import logging as _logging

        if settings.DATABASE_URL.startswith("sqlite"):
            return  # local/test databases are not alembic-managed; stamping
            # would point at the ini's postgres URL and block on connect.

        import app as _app
        from alembic import command
        from alembic.config import Config

        ini = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(_app.__file__)), "..", "alembic.ini"))
        if os.path.exists(ini):
            command.stamp(Config(ini), "head")
            _logging.getLogger("secondvoice").info("stamped alembic head (%s)", ini)
        else:
            _logging.getLogger("secondvoice").warning("alembic.ini not found at %s; skipping stamp", ini)
    except Exception as exc:  # migrations stay manual; never block startup
        import logging as _logging

        _logging.getLogger("secondvoice").warning("alembic stamp skipped: %r", exc)
