"""FastAPI application factory.

Startup order matters: logging first (so every line is structured), then the
model registry (warm-load in Phase 5), then routers. See ARCH §7.1.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.rate_limit import limiter, set_predict_limit
from app.services.registry import ModelRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "starting application",
        extra={"env": settings.app_env, "version": settings.app_version},
    )

    # Initialize database tables and seed knowledge base
    from app.db.session import init_db

    init_db()

    registry = ModelRegistry(settings)
    registry.load()
    app.state.registry = registry

    if settings.require_models and not registry.is_ready:
        # Stay up so /health/ready can report the failure with a reason and the
        # orchestrator sees a 503 instead of a crash loop (AC-5, NFR-R-004).
        logger.error("production models are required but not loaded")

    logger.info("application ready", extra={"models_ready": registry.is_ready})
    try:
        yield
    finally:
        logger.info("shutting down application")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Crop disease detection and yield prediction API. "
            "Decision support only — not a substitute for a local agronomist."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.state.settings = settings
    app.state.started_at = time.monotonic()

    # Order: outermost first. CORS must wrap everything so error responses
    # still carry the headers the browser needs to read them.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Rate limiting (slowapi): predict endpoints are decorated with
    # limiter.limit; the Limiter reads app.state settings/limits. The 429 →
    # RATE_LIMITED envelope mapping lives in core.errors.
    app.state.limiter = limiter
    set_predict_limit(settings.rate_limit_predict)

    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
