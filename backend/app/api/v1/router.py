"""Versioned API router. All endpoint routers are mounted here (ARCH §7.1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, disease, health, storage, weather, yield_

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(disease.router)
api_router.include_router(yield_.router)
api_router.include_router(weather.router)
api_router.include_router(storage.router)
