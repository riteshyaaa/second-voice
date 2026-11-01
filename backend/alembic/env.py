"""Alembic env — imports Base metadata from the app (single source of truth)."""
from logging.config import fileConfig

from alembic import context
from app.core.database import Base
import app.models  # noqa: F401

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

# Phase 12: DATABASE_URL env wins over the ini default; `-x url=...` wins
# over both (scratch-database verification). Unset → ini default unchanged.
import os as _os

_override = _os.getenv("DATABASE_URL")
for _opt in (getattr(config.cmd_opts, "x", None) or []):
    if _opt.startswith("url="):
        _override = _opt[4:]
if _override:
    config.set_main_option("sqlalchemy.url", _override)


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True,
                      compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    from sqlalchemy import engine_from_config

    engine = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.")
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_server_default=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
