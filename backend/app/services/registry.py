"""Model registry implementation managing active production models (ARCH §6.4, DEV_PLAN Task 5.4).

Two supply paths, in order:

1. `MODEL_REGISTRY_URI=supabase://<bucket>/models/production.json` — the
   pointer file is fetched at startup, then every artifact listed for the
   pointer's versions is downloaded (and cached) from Supabase Storage
   (FR-M-003). Artifacts live at `models/{pipeline}/{version}/<file>`.
2. Local artifact fallback (`ml/artifacts/models`) — what local development
   and this repo use while models are not yet promoted to storage.

Pointer format (ARCH §6.4): `{"disease": "v1.2.0", "yield": "v0.9.1"}`.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

from app.core.config import Settings
from app.ml.loader import (
    find_model_root,
    load_all_production_models,
    model_root_available,
    production_bundle,
)
from app.schemas.common import ModelInfo

logger = logging.getLogger(__name__)

# (filename, required) per pipeline; assembled by the training export.
ARTIFACTS_BY_PIPELINE: dict[str, list[tuple[str, bool]]] = {
    "disease": [
        ("model.pt", True),
        ("labels.json", True),
        ("config.json", False),
        ("card.json", False),
    ],
    "yield": [
        ("xgb_yield_model.json", True),
        ("quantile_yield_ensemble.joblib", False),
        ("feature_schema.json", True),
        ("risk_config.json", False),
        ("card.json", False),
    ],
}


def parse_registry_uri(uri: str) -> tuple[str, str] | None:
    """`supabase://<bucket>/<path>` → (bucket, path); None otherwise."""
    if not uri.startswith("supabase://"):
        return None
    remainder = uri[len("supabase://") :]
    bucket, _, pointer = remainder.partition("/")
    if not bucket or not pointer:
        return None
    return bucket, pointer.lstrip("/")


def _cache_root(settings: Settings) -> Path:
    path = Path(settings.model_cache_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:  # e.g. "/tmp/models" unusable on Windows
        fallback = Path(tempfile.gettempdir()) / "models"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def fetch_from_registry(settings: Settings) -> Path | None:
    """Download the artifacts named by `production.json`; returns load root.

    Returns None (after logging) for any of: no URI, unsupported scheme,
    pointer/artifacts not uploaded, transport error — callers then fall
    back to local artifacts.
    """
    from app.core.config import get_settings

    settings = settings or get_settings()
    parsed = parse_registry_uri(settings.model_registry_uri)
    if not parsed:
        if settings.model_registry_uri:
            logger.warning(f"Unsupported MODEL_REGISTRY_URI scheme: {settings.model_registry_uri}")
        return None
    bucket, pointer = parsed
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("MODEL_REGISTRY_URI is set but Supabase credentials are missing")
        return None

    artifact_base = pointer.rsplit("/", 1)[0] if "/" in pointer else ""
    base_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}"
    headers = {"Authorization": f"Bearer {settings.supabase_service_role_key}"}
    cache_root = _cache_root(settings)

    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            resp = client.get(f"{base_url}/{pointer}")
            if resp.status_code == 404:
                logger.info("production.json not uploaded yet — using local artifacts")
                return None
            if resp.status_code != 200:
                logger.warning(f"production.json fetch status {resp.status_code}")
                return None
            versions = resp.json()

            downloaded_all = True
            for pipeline, version in versions.items():
                files = ARTIFACTS_BY_PIPELINE.get(pipeline)
                if not files:
                    logger.warning(f"Unknown pipeline in production.json: {pipeline}")
                    continue
                dest_dir = cache_root / pipeline / str(version).lstrip("/")
                dest_dir.mkdir(parents=True, exist_ok=True)
                for filename, required in files:
                    artifact = f"{artifact_base}/{pipeline}/{version}/{filename}".lstrip("/")
                    r = client.get(f"{base_url}/{artifact}", timeout=120.0)
                    if r.status_code == 200:
                        (dest_dir / filename).write_bytes(r.content)
                    elif required:
                        logger.error(f"Required artifact missing: {artifact}")
                        downloaded_all = False
            if not downloaded_all:
                return None
        logger.info("production models synced from Supabase registry")
        return cache_root
    except Exception as e:  # noqa: BLE001 - never fail startup over registry
        logger.warning(f"Registry sync failed, falling back to local artifacts: {e}")
        return None


class ModelRegistry:
    """Manages active machine learning models and readiness states for API serving."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._models: dict[str, ModelInfo] = {}

    @property
    def configured(self) -> bool:
        """True once a registry URI is set or local artifacts are present."""
        return bool(self._settings.model_registry_uri) or model_root_available()

    @property
    def is_ready(self) -> bool:
        return production_bundle.disease_ready and production_bundle.yield_ready

    def load(self) -> None:
        """Warm-load production models: registry fetch first, then local."""
        root: Path | None = None
        if self._settings.model_registry_uri:
            root = fetch_from_registry(self._settings)
        if root is None:
            root = find_model_root()

        bundle = load_all_production_models(root)

        if bundle.disease_ready:
            d_card = bundle.disease_card
            self._models["disease"] = ModelInfo(
                pipeline="disease",
                name=d_card.get("model_name", "EfficientNet-B0 Disease Classifier"),
                version=d_card.get("version", "v0.1.0"),
                metrics=d_card.get("metrics", {}),
            )

        if bundle.yield_ready:
            y_card = bundle.yield_card
            self._models["yield"] = ModelInfo(
                pipeline="yield",
                name=y_card.get("primary_model", "XGBoost Yield Predictor"),
                version=y_card.get("version", "v0.1.0"),
                metrics=y_card.get("test_metrics", {}),
            )

        logger.info(
            "model registry loaded",
            extra={"disease_ready": bundle.disease_ready, "yield_ready": bundle.yield_ready},
        )

    def models(self) -> list[ModelInfo]:
        return list(self._models.values())
