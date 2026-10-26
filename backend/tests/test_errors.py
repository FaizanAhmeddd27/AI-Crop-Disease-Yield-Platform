from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import build_app


def _app_with_test_routes() -> FastAPI:
    app = build_app()

    @app.get("/boom", include_in_schema=False)
    async def _boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/needs-int", include_in_schema=False)
    async def _needs_int(q: int) -> dict[str, int]:
        return {"q": q}

    return app


def test_health_before_boom() -> None:  # guard against fixture mistakes
    with TestClient(_app_with_test_routes()) as client:
        assert client.get("/api/v1/health").status_code == 200


def test_unknown_route_returns_standard_body() -> None:
    with TestClient(_app_with_test_routes()) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_validation_error_maps_to_invalid_input() -> None:
    with TestClient(_app_with_test_routes()) as client:
        response = client.get("/needs-int", params={"q": "not-a-number"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_INPUT"
    assert error["details"]["errors"][0]["loc"] == ["query", "q"]


def test_unhandled_error_is_redacted() -> None:
    app = _app_with_test_routes()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]
