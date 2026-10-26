"""Database connection session management and initialization (ARCH §8)."""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base, DiseaseKnowledge

logger = logging.getLogger(__name__)

settings = get_settings()

db_url = settings.database_url

# Attempt Postgres if configured; fall back to SQLite on missing driver
_use_sqlite = False
if not db_url or "postgres" not in db_url:
    _use_sqlite = True
else:
    try:
        import psycopg  # noqa: F401  (driver v3 — SQLAlchemy 2.1 default)
    except ImportError:
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            logger.warning(
                "Neither psycopg nor psycopg2 installed — falling back to "
                "local SQLite. Install psycopg[binary] for PostgreSQL support."
            )
            _use_sqlite = True

if _use_sqlite:
    local_db_path = Path("agrisense_local.db").resolve()
    db_url = f"sqlite:///{local_db_path}"

connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create tables if missing and seed initial knowledge base."""
    Base.metadata.create_all(bind=engine)

    # Ensure user_id column exists on pre-existing tables
    with engine.begin() as conn:
        for tbl in ("predictions_disease", "predictions_yield"):
            try:
                if "sqlite" in db_url:
                    pragma = f"PRAGMA table_info({tbl})"
                    cols = [row[1] for row in conn.exec_driver_sql(pragma).fetchall()]
                    if "user_id" not in cols:
                        add_col = f"ALTER TABLE {tbl} ADD COLUMN user_id VARCHAR(36)"
                        conn.exec_driver_sql(add_col)
                else:
                    # Postgres
                    add_col = f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)"
                    conn.exec_driver_sql(add_col)
            except Exception as ex:
                logger.debug(f"Migration note for {tbl}.user_id: {ex}")

    logger.info("database tables initialized")

    # Seed knowledge base if empty
    session = SessionLocal()
    try:
        count = session.query(DiseaseKnowledge).count()
        if count == 0:
            kb_candidates = [
                (
                    Path(__file__).resolve().parents[3]
                    / "ml"
                    / "knowledge_base"
                    / "disease_knowledge.json"
                ),
                Path("ml/knowledge_base/disease_knowledge.json"),
            ]
            kb_path = next((p for p in kb_candidates if p.exists()), None)
            if kb_path:
                with open(kb_path, encoding="utf-8") as f:
                    kb_data = json.load(f)

                for cid, item in kb_data.items():
                    record = DiseaseKnowledge(
                        class_id=cid,
                        crop=item["crop"],
                        disease_name=item["disease_name"],
                        is_healthy=item["is_healthy"],
                        summary=item["summary"],
                        symptoms_json=json.dumps(item["symptoms"]),
                        actions_json=json.dumps(item["actions"]),
                        prevention_json=json.dumps(item["prevention"]),
                        disclaimer=item["disclaimer"],
                    )
                    session.add(record)
                session.commit()
                logger.info(f"seeded disease knowledge base with {len(kb_data)} classes")
    except Exception as e:
        logger.warning(f"knowledge base seed warning: {e}")
        session.rollback()
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency injecting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
