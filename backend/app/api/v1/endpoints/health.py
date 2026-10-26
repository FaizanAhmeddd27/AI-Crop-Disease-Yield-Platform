"""Health, readiness and model-metadata endpoints (FR-M-005, FR-M-003)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response, status

from app.core.config import Settings
from app.schemas.common import (
    DependencyStatus,
    HealthResponse,
    ModelsResponse,
    ReadinessResponse,
)

router = APIRouter(tags=["platform"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(request: Request) -> HealthResponse:
    """Cheap liveness check — used by hosts and uptime monitors."""
    settings: Settings = request.app.state.settings
    started_at: float = request.app.state.started_at
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        uptime_s=round(time.monotonic() - started_at, 3),
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"description": "A required dependency is unavailable"}},
)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    """Reports per-dependency state.

    `MODEL_NOT_READY` (503) is returned only when models are *required* and
    missing (AC-5). While `REQUIRE_MODELS=false` — Phase 0 up to model
    promotion — missing models read as `degraded`, not `not_ready`, so the
    skeleton stays deployable.
    """
    settings: Settings = request.app.state.settings
    registry = request.app.state.registry
    dependencies: list[DependencyStatus] = []

    if registry.configured:
        dependencies.append(
            DependencyStatus(
                name="models",
                status="ok" if registry.is_ready else "error",
                detail=None if registry.is_ready else "production models not loaded",
            )
        )
    else:
        dependencies.append(
            DependencyStatus(
                name="models",
                status="not_configured",
                detail="no production model registry configured",
            )
        )

    # DB and object storage are wired in Phase 5 (tasks 5.2 / 5.3).
    dependencies.append(
        DependencyStatus(
            name="database",
            status="not_configured" if not settings.database_url else "not_checked",
            detail=None if not settings.database_url else "connectivity check added in Phase 5",
        )
    )
    dependencies.append(
        DependencyStatus(
            name="object_storage",
            status="not_configured" if not settings.storage_configured else "not_checked",
            detail=(
                None if not settings.storage_configured else "connectivity check added in Phase 5"
            ),
        )
    )

    models_missing = settings.require_models and not registry.is_ready
    has_error = any(dep.status == "error" for dep in dependencies)
    if models_missing or has_error:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall = "not_ready"
    elif all(dep.status == "ok" for dep in dependencies):
        overall = "ready"
    else:
        overall = "degraded"

    return ReadinessResponse(
        status=overall,
        version=settings.app_version,
        dependencies=dependencies,
    )


@router.get("/models", response_model=ModelsResponse, summary="Active model metadata")
async def models(request: Request) -> ModelsResponse:
    """Feeds the About / Model-transparency page (FR-UI-009)."""
    registry = request.app.state.registry
    return ModelsResponse(
        registry="configured" if registry.configured else "unconfigured",
        models=registry.models(),
    )
