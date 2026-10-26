"""Disease knowledge base lookup service (ARCH §6.3, DEV_PLAN Task 5.5).

Queries the seeded `disease_knowledge` table for actionable crop disease
management recommendations.  Falls back to the JSON file when the DB row
is missing (e.g. new class added before a migration).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DiseaseKnowledge

logger = logging.getLogger(__name__)

# ── JSON fallback cache ────────────────────────────────────────────────
_kb_cache: dict[str, Any] | None = None


def _load_json_fallback() -> dict[str, Any]:
    global _kb_cache
    if _kb_cache is not None:
        return _kb_cache

    candidates = [
        Path(__file__).resolve().parents[3] / "ml" / "knowledge_base" / "disease_knowledge.json",
        Path("ml/knowledge_base/disease_knowledge.json"),
    ]
    for p in candidates:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                _kb_cache = json.load(f)
            return _kb_cache

    logger.warning("disease_knowledge.json not found in any candidate path")
    _kb_cache = {}
    return _kb_cache


# ── Public API ──────────────────────────────────────────────────────────


def get_knowledge_for_class(class_id: str, db: Session) -> dict[str, Any] | None:
    """Return structured knowledge entry for a disease class_id.

    Priority: DB row → JSON file → None.
    """
    row: DiseaseKnowledge | None = (
        db.query(DiseaseKnowledge).filter(DiseaseKnowledge.class_id == class_id).first()
    )
    if row is not None:
        return {
            "class_id": row.class_id,
            "crop": row.crop,
            "disease_name": row.disease_name,
            "is_healthy": row.is_healthy,
            "summary": row.summary,
            "symptoms": json.loads(row.symptoms_json),
            "actions": json.loads(row.actions_json),
            "prevention": json.loads(row.prevention_json),
            "disclaimer": row.disclaimer,
        }

    # JSON fallback
    fb = _load_json_fallback()
    if class_id in fb:
        return fb[class_id]

    logger.warning(f"No knowledge entry found for class_id={class_id}")
    return None


def get_all_classes(db: Session) -> list[dict[str, Any]]:
    """Return a lightweight list of all 38 disease classes."""
    rows = db.query(DiseaseKnowledge).order_by(DiseaseKnowledge.class_id).all()
    if rows:
        return [
            {
                "class_id": r.class_id,
                "crop": r.crop,
                "disease_name": r.disease_name,
                "is_healthy": r.is_healthy,
            }
            for r in rows
        ]

    # JSON fallback
    fb = _load_json_fallback()
    return [
        {
            "class_id": cid,
            "crop": item["crop"],
            "disease_name": item["disease_name"],
            "is_healthy": item["is_healthy"],
        }
        for cid, item in sorted(fb.items())
    ]
