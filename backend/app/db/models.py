"""SQLAlchemy ORM models (ARCH §8.2, DEV_PLAN Tasks 5.2, 5.14).

SQLAlchemy 2.0 typed style (`Mapped` + `mapped_column`) so the attributes
carry their real Python types — endpoints and services depend on that.
`alembic` migration 0001 mirrors this schema exactly.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base with full runtime typing support."""


def generate_uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime.datetime:
    """Timezone-naive UTC timestamp (consistent with historical rows)."""
    return datetime.datetime.now(tz=datetime.UTC).replace(tzinfo=None)


class User(Base):
    """User account for farmers, agronomists, or researchers (ARCH §8.2, §13)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # farmer, agronomist, researcher
    role: Mapped[str] = mapped_column(String(32), default="farmer", nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class Farm(Base):
    """Registered farm profile belonging to a user (ARCH §8.2)."""

    __tablename__ = "farms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_crop: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PredictionDisease(Base):
    """Persisted disease diagnosis records."""

    __tablename__ = "predictions_disease"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # null = anonymous (ARCH §8.2)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    overlay_url: Mapped[str] = mapped_column(String(512), nullable=False)
    crop: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    disease_class: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity_band: Mapped[str] = mapped_column(String(32), nullable=False)
    severity_ratio_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PredictionYield(Base):
    """Persisted yield prediction records."""

    __tablename__ = "predictions_yield"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # null = anonymous (ARCH §8.2)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    crop: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_yield_tha: Mapped[float] = mapped_column(Float, nullable=False)
    interval_lower: Mapped[float] = mapped_column(Float, nullable=False)
    interval_upper: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class DiseaseKnowledge(Base):
    """Curated knowledge base recommendations per disease class."""

    __tablename__ = "disease_knowledge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    class_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(64), nullable=False)
    disease_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    symptoms_json: Mapped[str] = mapped_column(Text, nullable=False)
    actions_json: Mapped[str] = mapped_column(Text, nullable=False)
    prevention_json: Mapped[str] = mapped_column(Text, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
