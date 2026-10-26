"""Shared response schemas (SRS §4.5, ARCH §7.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable message safe to display")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    env: str
    uptime_s: float


class DependencyStatus(BaseModel):
    name: str
    status: Literal["ok", "not_configured", "not_checked", "error"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded", "not_ready"]
    version: str
    dependencies: list[DependencyStatus]


class ModelInfo(BaseModel):
    pipeline: Literal["disease", "yield"]
    name: str
    version: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class ModelsResponse(BaseModel):
    registry: Literal["configured", "unconfigured"]
    models: list[ModelInfo] = Field(default_factory=list)
