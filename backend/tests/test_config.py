from __future__ import annotations

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    # `_env_file=None` keeps these tests independent of the developer's .env,
    # which holds real credentials once the project is configured.
    return Settings(_env_file=None, app_env="development", **overrides)  # type: ignore[arg-type]


def test_storage_is_unconfigured_by_default() -> None:
    settings = _settings()

    assert settings.storage_configured is False
    assert settings.storage_s3_endpoint == ""


def test_storage_needs_a_url_and_a_credential() -> None:
    assert _settings(supabase_url="https://abc.supabase.co").storage_configured is False
    assert _settings(supabase_service_role_key="key").storage_configured is False
    assert (
        _settings(
            supabase_url="https://abc.supabase.co",
            supabase_service_role_key="key",
        ).storage_configured
        is True
    )
    assert (
        _settings(
            supabase_url="https://abc.supabase.co",
            supabase_s3_access_key_id="s3-key",
        ).storage_configured
        is True
    )


def test_s3_endpoint_is_derived_from_the_project_url() -> None:
    settings = _settings(supabase_url="https://abc.supabase.co/")

    assert settings.storage_s3_endpoint == "https://abc.supabase.co/storage/v1/s3"


def test_upload_limit_is_bytes() -> None:
    assert _settings(max_upload_mb=10).max_upload_bytes == 10 * 1024 * 1024
