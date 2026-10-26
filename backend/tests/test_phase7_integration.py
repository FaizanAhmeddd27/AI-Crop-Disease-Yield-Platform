"""Phase 7 integration and security acceptance checks."""

from __future__ import annotations

import io

from PIL import Image
from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limiter
from tests.conftest import build_app


def _small_jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (45, 160, 55)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_frontend_origins_are_allowed() -> None:
    with TestClient(build_app()) as client:
        for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
            response = client.get("/api/v1/models", headers={"Origin": origin})
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin


def test_unsupported_crop_returns_structured_error() -> None:
    with TestClient(build_app()) as client:
        response = client.post(
            "/api/v1/yield/predict",
            json={
                "crop": "unsupported",
                "location": {"lat": 31.52, "lon": 74.35, "district": "Lahore"},
                "season": {"year": 2024},
                "area_ha": 1,
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_CROP"


def test_malformed_image_is_rejected_without_internal_details() -> None:
    with TestClient(build_app()) as client:
        response = client.post(
            "/api/v1/disease/predict",
            files={"file": ("leaf.jpg", b"not-an-image", "image/jpeg")},
        )

    assert response.status_code == 415
    if response.headers.get("content-type", "").startswith("application/json"):
        assert "Traceback" not in response.text


def test_local_storage_blocks_path_traversal() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/api/v1/storage/agri-uploads/../.env")

    assert response.status_code in (403, 404)


def test_predict_rate_limit_is_enforced() -> None:
    reset_rate_limiter()
    app = build_app(rate_limit_predict="2/minute")
    payload = {"file": ("leaf.jpg", _small_jpeg(), "image/jpeg")}
    with TestClient(app) as client:
        responses = [
            client.post("/api/v1/disease/predict", files=payload),
            client.post("/api/v1/disease/predict", files=payload),
            client.post("/api/v1/disease/predict", files=payload),
        ]

    assert responses[-1].status_code == 429
    assert responses[-1].json()["error"]["code"] == "RATE_LIMITED"
    reset_rate_limiter()
