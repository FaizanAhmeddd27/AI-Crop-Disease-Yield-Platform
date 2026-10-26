from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from app.core.config import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient

# --- Deterministic local environment --------------------------------
# Set BEFORE any app module import: forces the whole test suite onto the
# local SQLite database and local storage fallback so tests never touch
# the remote Supabase project (neither its Postgres nor its buckets).
os.environ["DATABASE_URL"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["SUPABASE_S3_ACCESS_KEY_ID"] = ""
os.environ["REQUIRE_MODELS"] = "false"

from app.main import create_app  # noqa: E402


def build_app(**overrides: object) -> FastAPI:
    settings = Settings(
        app_env="development",
        cors_origins="http://localhost:3000,http://127.0.0.1:3000",
        **overrides,  # type: ignore[arg-type]
    )
    return create_app(settings)


@pytest.fixture
def app() -> FastAPI:
    return build_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Lifespan (registry load) must run, so use TestClient as a context manager.
    with TestClient(app) as test_client:
        yield test_client
