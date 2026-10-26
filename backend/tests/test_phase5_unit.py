"""Phase 5 unit tests for the services added/touched in Phase 5 hardening (Task 5.12).

Covers: rate limiting (slowapi), weather adapter fallback (NASA POWER),
storage local fallback + delete + path anchoring, and the model-registry
URI parsing / graceful fallback contract.
"""

from __future__ import annotations

import pytest
from app.core.rate_limit import reset_rate_limiter
from app.services import weather_service
from app.services.registry import parse_registry_uri
from app.services.storage import StorageService, local_storage_root
from fastapi.testclient import TestClient

from tests.conftest import build_app

# ── Rate limiting (Task 5.1) ───────────────────────────────────────────


@pytest.fixture()
def limiter_client() -> TestClient:
    reset_rate_limiter()
    app = build_app(rate_limit_predict="2/minute")
    with TestClient(app) as test_client:
        yield test_client
    reset_rate_limiter()


def _yield_body() -> dict:
    return {
        "crop": "wheat",
        "location": {"lat": 31.42, "lon": 73.08, "district": "Faisalabad"},
        "season": {"year": 2024},
        "area_ha": 500.0,
        "weather_override": {"w_days_observed": 180, "w_completeness": 1.0},
    }


def test_rate_limit_blocks_after_threshold(limiter_client: TestClient):
    responses = [limiter_client.post("/api/v1/yield/predict", json=_yield_body()) for _ in range(3)]
    codes = [r.status_code for r in responses]
    assert codes[0] == 200
    assert 429 in codes[1:], f"expected a 429 by the third call, got {codes}"
    limited = next(r for r in responses if r.status_code == 429)
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_unlimited_endpoint_ignores_limit(limiter_client: TestClient):
    for _ in range(3):
        r = limiter_client.get("/api/v1/yield/options")
        assert r.status_code == 200


# ── Weather adapters (Task 5.6/5.8) ───────────────────────────────────


def _fake_daily() -> dict:
    """10 days of synthetic Open-Meteo-shaped data (rad in MJ/m², wind m/s)."""
    return {
        "time": [f"2024-02-0{i}" for i in range(1, 11)],
        "temperature_2m_max": [30.0] * 5 + [36.0] * 5,
        "temperature_2m_min": [10.0] * 5 + [20.0] * 5,
        "temperature_2m_mean": [20.0] * 5 + [28.0] * 5,
        "precipitation_sum": [10.0] * 2 + [25.0] + [0.0] * 7,
        "relative_humidity_2m_mean": [50.0] * 10,
        "shortwave_radiation_sum": [20.0] * 10,
        "wind_speed_10m_max": [5.0] * 10,
    }


def test_aggregate_matches_training_gdd_math():
    agg = weather_service._aggregate(
        "open-meteo", "wheat", "2024-02-01", "2024-02-10", _fake_daily()
    )
    # Wheat GDD base is 5 °C and GDD uses the midpoint of daily extremes:
    # days 1-5: (30+10)/2 - 5 = 15; days 6-10: (36+20)/2 - 5 = 23 → total 190
    assert agg.w_gdd_c == 190.0
    assert agg.w_heat_stress_days == 5
    assert agg.w_rain_total_mm == 45.0
    assert agg.w_rainy_days == 3
    assert agg.w_heavy_rain_days == 1
    assert agg.w_completeness == 1.0


@pytest.mark.asyncio
async def test_fetch_weather_falls_back_to_nasa_power(monkeypatch: pytest.MonkeyPatch):
    """Open-Meteo failure → NASA POWER success keeps the pipeline working."""

    async def open_meteo_fails(*_a: object, **_k: object) -> None:
        return None

    async def nasa_works(*_a: object, **_k: object) -> dict:
        return _fake_daily()

    monkeypatch.setattr(weather_service, "_fetch_open_meteo", open_meteo_fails)
    monkeypatch.setattr(weather_service, "_fetch_nasa_power", nasa_works)
    weather_service._cache.clear()

    agg = await weather_service.fetch_weather(31.4, 73.0, "2024-02-01", "2024-02-10", "wheat")
    assert agg.source == "nasa-power"
    assert agg.w_days_observed == 10
    assert agg.w_gdd_c == 190.0


@pytest.mark.asyncio
async def test_fetch_weather_returns_unavailable_when_all_fail(monkeypatch: pytest.MonkeyPatch):
    async def all_fail(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(weather_service, "_fetch_open_meteo", all_fail)
    monkeypatch.setattr(weather_service, "_fetch_nasa_power", all_fail)
    weather_service._cache.clear()

    agg = await weather_service.fetch_weather(31.4, 73.0, "2024-02-01", "2024-02-10", "wheat")
    assert agg.source == "unavailable"
    assert agg.w_days_observed == 0


# ── Storage local fallback (Task 5.2/5.3) ──────────────────────────────


@pytest.mark.asyncio
async def test_local_storage_upload_delete_roundtrip():
    service = StorageService()
    assert service.local_storage_dir == local_storage_root()
    # Never the CWD-relative 'backend/backend/...' nesting bug
    parts = service.local_storage_dir.parts
    assert parts.count("backend") <= 1

    url = await service.upload_file(b"test-bytes", "unit/ping.jpg", bucket_name="agri-uploads")
    assert url.startswith("/api/v1/storage/agri-uploads/")
    stored = service.local_storage_dir / "agri-uploads" / "unit" / "ping.jpg"
    assert stored.exists()
    assert stored.read_bytes() == b"test-bytes"

    deleted = await service.delete_file("agri-uploads", "unit/ping.jpg")
    assert deleted is True
    assert not stored.exists()


def test_local_storage_root_is_repo_anchored():
    root = local_storage_root()
    assert root.name == "storage"
    assert root.parent.name == "data"
    assert root.parent.parent.name == "backend"


# ── Model registry (Task 5.4) ──────────────────────────────────────────


def test_parse_registry_uri():
    assert parse_registry_uri("supabase://agri-models/models/production.json") == (
        "agri-models",
        "models/production.json",
    )
    assert parse_registry_uri("") is None
    assert parse_registry_uri("supabase://") is None
    assert parse_registry_uri("https://example.com/x.json") is None
