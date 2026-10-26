"""Application settings loaded from environment variables / `.env`.

Every variable here mirrors `docs/ARCH.md` §13 (Configuration). Nothing is
hard-coded per environment: the same container runs locally, on staging and in
production, only the environment differs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -----------------------------------------------------
    app_name: str = "AgriSense AI API"
    app_version: str = "0.1.0"
    app_env: Environment = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- HTTP / CORS -----------------------------------------------------
    # Comma-separated allow-list, e.g. "http://localhost:3000,https://app.vercel.app"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_mb: int = Field(default=10, gt=0)
    rate_limit_predict: str = "20/minute"

    # --- Disease pipeline ------------------------------------------------
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)

    # --- Yield / weather -------------------------------------------------
    weather_primary: str = "open-meteo"
    weather_fallback: str = "nasa-power"
    weather_cache_ttl_min: int = Field(default=180, gt=0)

    # --- Model registry --------------------------------------------------
    # "supabase://agri-models/models/production.json" in deployed environments.
    # Empty means "no production models yet" (Phase 0 / local dev).
    model_registry_uri: str = ""
    # Container-local cache; ephemeral by design (ARCH §9).
    model_cache_dir: str = "/tmp/models"  # noqa: S108
    # Flip to true once real production models exist. Readiness then fails
    # (503 MODEL_NOT_READY) when a model is missing — SRS AC-5 / NFR-R-004.
    require_models: bool = False

    # --- Persistence (Phase 5) -------------------------------------------
    database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    # Legacy HS256 signing secret. Only used by the stretch auth goal; new
    # projects sign JWTs asymmetrically, in which case verification should use
    # the project's JWKS endpoint and this stays empty (ARCH §13, DEV_PLAN 5.14).
    supabase_jwt_secret: str = ""
    # Dev-only default (overridden via JWT_SECRET_KEY in every real deployment).
    jwt_secret_key: str = "agrisense-production-secure-jwt-secret-key-2026"  # noqa: S105
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    # --- Object storage: Supabase Storage (Phase 5) ----------------------
    # Backend access uses the REST API with the service-role key. Training
    # (Kaggle) uploads through the S3-compatible endpoint, which needs its own
    # access-key pair: Storage -> S3 access keys in the Supabase dashboard.
    supabase_s3_access_key_id: str = ""
    supabase_s3_secret_access_key: str = ""
    # Must match the project's region or S3 signatures are rejected.
    supabase_s3_region: str = "us-east-1"
    supabase_bucket_uploads: str = "agri-uploads"
    supabase_bucket_overlays: str = "agri-overlays"
    supabase_bucket_models: str = "agri-models"

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def storage_configured(self) -> bool:
        """Storage is usable once we have the project URL and *a* credential.

        The service-role key is what the backend uses; the S3 key pair is only
        needed by training jobs, so either one is enough to call it configured.
        """
        return bool(
            self.supabase_url and (self.supabase_service_role_key or self.supabase_s3_access_key_id)
        )

    @property
    def storage_s3_endpoint(self) -> str:
        """S3-compatible endpoint for the project (`""` when unconfigured)."""
        if not self.supabase_url:
            return ""
        return f"{self.supabase_url.rstrip('/')}/storage/v1/s3"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the `.env` file is read once per process."""
    return Settings()
