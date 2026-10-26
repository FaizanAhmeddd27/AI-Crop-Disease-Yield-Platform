"""Alembic migration environment (backend databases, DEV_PLAN Task 5.2).

The URL can be provided three ways, in order:
1. `alembic -x db_url=<url> upgrade head` (ad-hoc overrides)
2. `DATABASE_URL` environment variable
3. `backend/.env` via app settings
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- ensure backend/ is importable -------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("db_url") or get_settings().database_url
    if not url:
        # Deterministic local fallback so migrations can always run.
        url = "sqlite:///./migrations_local.db"
    if url.startswith("postgresql://"):
        # SQLAlchemy 2.1 defaults to the psycopg (v3) driver.
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_url()
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = url
    connect_args = {"check_same_thread": False} if "sqlite" in url else {}
    engine = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
