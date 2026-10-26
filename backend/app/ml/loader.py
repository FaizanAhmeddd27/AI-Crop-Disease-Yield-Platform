"""Model loader, artifact locator, and runtime warm-up (ARCH §6.4, DEV_PLAN Task 5.4)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import torch
import xgboost as xgb

logger = logging.getLogger(__name__)


def find_model_root() -> Path:
    """Locate models directory across local repo and container environments."""
    candidates = [
        Path("ml/artifacts/models"),
        Path(__file__).resolve().parents[3] / "ml" / "artifacts" / "models",
        Path("artifacts/models"),
        Path("/tmp/models"),  # noqa: S108 - registry cache dir inside ephemeral container fs
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return candidates[0]


def model_root_available() -> bool:
    """True when any candidate model directory exists."""
    candidates = [
        Path("ml/artifacts/models"),
        Path(__file__).resolve().parents[3] / "ml" / "artifacts" / "models",
        Path("artifacts/models"),
        Path("/tmp/models"),  # noqa: S108 - registry cache dir inside ephemeral container fs
    ]
    return any(c.exists() for c in candidates)


class ProductionModelBundle:
    """Container holding active in-memory models and metadata."""

    def __init__(self) -> None:
        self.disease_model: torch.jit.ScriptModule | None = None
        self.disease_labels: dict[str, str] = {}
        self.disease_config: dict[str, Any] = {}
        self.disease_card: dict[str, Any] = {}

        self.yield_booster: xgb.Booster | None = None
        self.quantile_ensemble: Any | None = None
        self.yield_schema: dict[str, Any] = {}
        self.risk_config: dict[str, Any] = {}
        self.history_tables: dict[str, Any] = {}
        self.yield_card: dict[str, Any] = {}

        self.disease_ready: bool = False
        self.yield_ready: bool = False

    def load_disease_pipeline(self, base_dir: Path) -> bool:
        """Load TorchScript disease model and class labels."""
        disease_dir = base_dir / "disease" / "v0.1.0"
        pt_path = disease_dir / "model.pt"
        labels_path = disease_dir / "labels.json"
        config_path = disease_dir / "config.json"
        card_path = disease_dir / "card.json"

        if not pt_path.exists():
            logger.warning(f"Disease model weights missing at {pt_path}")
            return False

        try:
            self.disease_model = torch.jit.load(str(pt_path), map_location="cpu")
            self.disease_model.eval()

            # Warm-up with dummy inference
            dummy = torch.randn(1, 3, 224, 224)
            with torch.no_grad():
                _ = self.disease_model(dummy)

            if labels_path.exists():
                with open(labels_path, encoding="utf-8") as f:
                    self.disease_labels = json.load(f)

            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    self.disease_config = json.load(f)

            if card_path.exists():
                with open(card_path, encoding="utf-8") as f:
                    self.disease_card = json.load(f)

            self.disease_ready = True
            logger.info("Disease classification model warmed up and ready.")
            return True
        except Exception as e:
            logger.error(f"Failed to load disease model: {e}")
            return False

    def load_yield_pipeline(self, base_dir: Path) -> bool:
        """Load XGBoost point regressor, quantile ensemble, and risk rules."""
        yield_dir = base_dir / "yield" / "v0.1.0"
        model_json = yield_dir / "xgb_yield_model.json"
        quantile_joblib = yield_dir / "quantile_yield_ensemble.joblib"
        schema_path = yield_dir / "feature_schema.json"
        risk_path = yield_dir / "risk_config.json"
        history_path = yield_dir / "history_tables.json"
        card_path = yield_dir / "card.json"

        if not model_json.exists():
            logger.warning(f"Yield model weights missing at {model_json}")
            return False

        try:
            self.yield_booster = xgb.Booster()
            self.yield_booster.load_model(str(model_json))

            if quantile_joblib.exists():
                self.quantile_ensemble = joblib.load(str(quantile_joblib))

            if schema_path.exists():
                with open(schema_path, encoding="utf-8") as f:
                    self.yield_schema = json.load(f)

            if risk_path.exists():
                with open(risk_path, encoding="utf-8") as f:
                    self.risk_config = json.load(f)

            if history_path.exists():
                with open(history_path, encoding="utf-8") as f:
                    self.history_tables = json.load(f)
            else:
                logger.warning(
                    "history_tables.json missing — history features will use crop-mean fallbacks"
                )

            if card_path.exists():
                with open(card_path, encoding="utf-8") as f:
                    self.yield_card = json.load(f)

            self.yield_ready = True
            logger.info("Crop yield models loaded and ready.")
            return True
        except Exception as e:
            logger.error(f"Failed to load yield models: {e}")
            return False


# Singleton instance
production_bundle = ProductionModelBundle()


def load_all_production_models(model_root: Path | None = None) -> ProductionModelBundle:
    root = model_root or find_model_root()
    production_bundle.load_disease_pipeline(root)
    production_bundle.load_yield_pipeline(root)
    return production_bundle
