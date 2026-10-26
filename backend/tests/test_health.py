from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import build_app


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["env"] == "development"
    assert body["uptime_s"] >= 0


def test_request_id_header_is_always_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["X-Request-ID"]


def test_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc"})

    assert response.headers["X-Request-ID"] == "trace-abc"


def test_readiness_reports_status(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ready", "degraded")
    models = next((dep for dep in body["dependencies"] if dep["name"] == "models"), None)
    if models:
        assert models["status"] in ("ok", "ready", "configured", "not_configured")


def test_readiness_fails_when_models_are_required_but_missing(monkeypatch) -> None:
    from app.services.registry import ModelRegistry

    monkeypatch.setattr(ModelRegistry, "is_ready", property(lambda self: False))

    app = build_app(
        require_models=True,
        model_registry_uri="supabase://agri-models/models/production.json",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    models = next(dep for dep in body["dependencies"] if dep["name"] == "models")
    assert models["status"] == "error"


def test_readiness_marks_configured_storage_as_not_checked() -> None:
    app = build_app(
        supabase_url="https://abc.supabase.co",
        supabase_service_role_key="test-key",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    storage = next(dep for dep in body["dependencies"] if dep["name"] == "object_storage")
    assert storage["status"] == "not_checked"


def test_models_endpoint_reports_registry(client: TestClient) -> None:
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["registry"] in ("configured", "unconfigured")
    if body["registry"] == "configured":
        assert len(body["models"]) >= 1


def test_root_returns_service_links(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["health"] == "/api/v1/health"
