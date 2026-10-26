"""Pydantic schemas for authentication and user accounts (ARCH §8.2, §13)."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Registration request payload."""

    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: str | None = Field(None, max_length=255)
    phone_number: str | None = Field(None, max_length=64)
    role: str = Field("farmer", pattern="^(farmer|agronomist|researcher)$")
    preferred_language: str = Field("en", max_length=10)


class UserLogin(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public user profile representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    phone_number: str | None = None
    role: str
    preferred_language: str
    is_active: bool
    created_at: datetime.datetime


class UserUpdate(BaseModel):
    """Profile update payload."""

    full_name: str | None = None
    phone_number: str | None = None
    preferred_language: str | None = None


class PasswordChange(BaseModel):
    """Password change request."""

    old_password: str
    new_password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """Access token envelope."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 scheme keyword, not a secret
    expires_in: int
    user: UserResponse


class DiseaseHistoryItem(BaseModel):
    """Item in disease scan history."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    image_url: str
    overlay_url: str
    crop: str
    disease_class: str
    confidence: float
    is_healthy: bool
    severity_band: str
    severity_ratio_pct: float
    created_at: datetime.datetime


class YieldHistoryItem(BaseModel):
    """Item in yield prediction history."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    crop: str
    district: str
    season_year: int
    area_ha: float
    predicted_yield_tha: float
    interval_lower: float
    interval_upper: float
    risk_level: str
    created_at: datetime.datetime


class HistoryStatsResponse(BaseModel):
    """Aggregated scan & yield statistics for user's dashboard."""

    total_disease_scans: int
    healthy_count: int
    diseased_count: int
    total_yield_forecasts: int
    avg_predicted_yield_tha: float | None = None
