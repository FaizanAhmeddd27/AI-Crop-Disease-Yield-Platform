"""Phase 5 integration tests — all Must endpoints against a real app instance.

Exercises the full stack: lifespan (DB init + KB seed + model warm-load),
auth, disease inference on a real image, yield inference with a weather
override, storage, options and metadata endpoints (DEV_PLAN Task 5.12).
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import build_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One app instance for the whole module (startup is expensive)."""
    app = build_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200, f"status {r.status_code}"
    d = r.json()
    assert d["status"] == "ok"
    assert "uptime_s" in d


def test_ready(client: TestClient):
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200, f"status {r.status_code}"
    d = r.json()
    assert d["status"] in ("ready", "degraded")
    names = {dep["name"] for dep in d["dependencies"]}
    assert {"models", "database", "object_storage"} <= names


def test_models(client: TestClient):
    r = client.get("/api/v1/models")
    assert r.status_code == 200, f"status {r.status_code}"
    d = r.json()
    assert d["registry"] == "configured"
    model_count = len(d["models"])
    assert model_count == 2, f"Expected 2 models, got {model_count}"
    names = [m["pipeline"] for m in d["models"]]
    assert "disease" in names
    assert "yield" in names


def test_disease_classes(client: TestClient):
    r = client.get("/api/v1/disease/classes")
    assert r.status_code == 200, f"status {r.status_code}"
    d = r.json()
    assert d["total_classes"] == 38, f"Expected 38, got {d['total_classes']}"
    assert len(d["classes"]) == 38


def test_disease_predict(client: TestClient):
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    img[:] = [45, 160, 55]
    pil_img = Image.fromarray(img)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG")
    buf.seek(0)
    r = client.post(
        "/api/v1/disease/predict",
        files={"file": ("test_leaf.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert r.status_code == 200, f"status {r.status_code}: {r.text[:300]}"
    d = r.json()
    assert "prediction_id" in d
    assert d["status"] in ("ok", "uncertain")
    assert "prediction" in d
    assert "severity" in d
    assert "explanation" in d
    assert "recommendations" in d
    assert d["latency_ms"] > 0


def test_disease_predict_too_large(client: TestClient):
    big = b"x" * (11 * 1024 * 1024)  # exceeds MAX_UPLOAD_MB=10 default
    r = client.post(
        "/api/v1/disease/predict",
        files={"file": ("big.jpg", big, "image/jpeg")},
    )
    assert r.status_code == 413, f"status {r.status_code}"
    assert r.json()["error"]["code"] in ("IMAGE_TOO_LARGE", "FILE_TOO_LARGE")


def test_yield_options(client: TestClient):
    r = client.get("/api/v1/yield/options")
    assert r.status_code == 200, f"status {r.status_code}"
    d = r.json()
    n = len(d["districts"])
    assert n == 36, f"Expected 36 districts, got {n}"
    assert "wheat" in d["supported_crops"]
    assert "maize" in d["supported_crops"]
    assert d["target_unit"] == "t/ha"


def test_yield_predict(client: TestClient):
    body = {
        "crop": "wheat",
        "location": {"lat": 31.42, "lon": 73.08, "district": "Faisalabad"},
        "season": {"year": 2024},
        "area_ha": 500.0,
        "weather_override": {
            "w_rain_total_mm": 280.0,
            "w_rainy_days": 25,
            "w_heavy_rain_days": 3,
            "w_dry_days": 120,
            "w_temp_mean_c": 18.5,
            "w_temp_max_c": 38.2,
            "w_temp_min_c": 3.1,
            "w_gdd_c": 2200.0,
            "w_heat_stress_days": 5,
            "w_grain_rain_mm": 40.0,
            "w_grain_gdd_c": 600.0,
            "w_water_balance_mm": -150.0,
            "w_humidity_mean_pct": 55.0,
            "w_solar_mj_m2": 18.5,
            "w_wind_max_kmh": 45.0,
            "w_days_observed": 180,
            "w_completeness": 0.95,
        },
    }
    r = client.post("/api/v1/yield/predict", json=body)
    assert r.status_code == 200, f"status {r.status_code}: {r.text[:300]}"
    d = r.json()
    assert "prediction_id" in d
    assert d["status"] in ("ok", "degraded", "out_of_bounds")
    assert d["prediction"]["unit"] == "t/ha"
    assert d["prediction"]["yield_value"] > 0
    assert d["risk"]["level"] in ("low", "medium", "high")
    assert d["explanation"]["method"] == "shap"
    assert len(d["explanation"]["contributions"]) > 0
    assert d["latency_ms"] > 0
    y = d["prediction"]["yield_value"]
    lo = d["prediction"]["interval"]["lower"]
    hi = d["prediction"]["interval"]["upper"]
    assert lo <= y <= hi, f"point estimate outside PI80: [{lo}, {hi}] vs {y}"


def test_models_metrics_loaded(client: TestClient):
    """Warm-loaded models must expose their card metrics (FR-M-003)."""
    r = client.get("/api/v1/models")
    assert r.status_code == 200
    d = r.json()
    by_pipeline = {m["pipeline"]: m for m in d["models"]}
    disease = by_pipeline["disease"]
    yield_model = by_pipeline["yield"]
    assert disease["version"], "disease card version missing"
    assert "metrics" in disease
    assert yield_model["version"], "yield card version missing"


def test_validation_error_envelope(client: TestClient):
    """422 responses use the standard error envelope (ARCH §7.2)."""
    r = client.post("/api/v1/yield/predict", json={"crop": "unknown_crop"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "INVALID_INPUT"
    assert "request_id" in body["error"]
