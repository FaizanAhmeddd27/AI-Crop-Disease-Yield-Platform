"""Phase 2 verification against the *exported* disease artifact (DEV_PLAN Tasks 2.9, 2.11, 2.12).

The D-01..D-07 training runs executed on Kaggle and their run records were never
committed to `ml/artifacts/runs` (documented gap in docs/reports/disease_experiments.md).
These tests validate what still can be verified locally without the dataset:

- Train/serve preprocessing parity (eval transform vs. serving resize) — the
  production preprocess now mirrors `Resize(256) -> CenterCrop(224) -> Normalize`.
- Exported calibration temperature is applied at serving (NFR-ML-003).
- TorchScript artifact loads through the backend bundle and answers within the
  single-image CPU latency budget (NFR-P-001).
- 38-class label map integrity.
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import torch
from app.ml.loader import load_all_production_models
from app.services.disease_service import classify_with_temperature, preprocess_image
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = REPO_ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from src.disease.transforms import get_transforms  # noqa: E402  (ml package)


@pytest.fixture(scope="module")
def bundle():
    models = load_all_production_models()
    if not models.disease_ready or models.disease_model is None:
        pytest.skip("Disease model artifact not present")
    return models


@pytest.fixture(scope="module")
def sample_image_bytes() -> bytes:
    """Synthetic smooth leaf-toned photo (low-frequency, so cross-library
    resize interpolation differences stay negligible and the test isolates
    the geometric parity contract)."""
    h, w = 480, 640
    base = np.array([40, 90, 35], dtype=float)
    col_gain = np.linspace(0.9, 1.25, w)
    row_gain = np.linspace(1.1, 0.85, h)
    img = np.empty((h, w, 3), dtype=float)
    img[:, :, :] = base[None, None, :]
    img *= col_gain[None, :, None]
    img *= row_gain[:, None, None]
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


class TestTrainServeParity:
    def test_preprocessing_matches_training_eval_transform(self, sample_image_bytes):
        """Serving tensor must match the training-side val/test transform."""
        serving_tensor, _ = preprocess_image(sample_image_bytes)

        train_transform = get_transforms("val")
        reference_tensor = train_transform(
            Image.open(io.BytesIO(sample_image_bytes)).convert("RGB")
        )

        assert serving_tensor.dim() == 4
        np.testing.assert_allclose(
            serving_tensor[0].numpy(),
            (
                reference_tensor if reference_tensor.dim() == 4 else reference_tensor.unsqueeze(0)
            ).numpy()[0],
            atol=0.1,  # cv2.INTER_AREA vs PIL bicubic rounding differences
            rtol=0,
        )

    def test_output_is_imagenet_normalized(self, sample_image_bytes):
        serving_tensor, _ = preprocess_image(sample_image_bytes)
        assert float(serving_tensor.mean()) < 3.0  # normalized units, not [0,255]
        assert float(serving_tensor.std()) > 0.1

    def test_serving_tensor_matches_paradigm_crop(self, sample_image_bytes):
        """Shape contract: (1, 3, 224, 224) as declared in config.json."""
        serving_tensor, img_rgb = preprocess_image(sample_image_bytes)
        assert serving_tensor.shape == (1, 3, 224, 224)
        # original image returned untouched for severity/overlay
        assert img_rgb.shape == (480, 640, 3)


class TestCalibrationApplied:
    def test_softmax_temperature_math(self):
        logits = torch.tensor([[2.0, 1.0, 0.5, -1.0]])
        hot = classify_with_temperature(logits, temperature=2.0)
        cold = classify_with_temperature(logits, temperature=0.5)
        identity = classify_with_temperature(logits, temperature=1.0)

        # Higher T -> flatter (closer to uniform); lower T -> sharper
        assert float(hot.max()) < float(identity.max())
        assert float(cold.max()) > float(identity.max())
        assert float(hot.sum()) == pytest.approx(1.0, abs=1e-6)
        assert float(cold.sum()) == pytest.approx(1.0, abs=1e-6)

    def test_exported_temperature_is_used_by_bundle_config(self, bundle):
        assert "temperature" in bundle.disease_config
        assert bundle.disease_config["temperature"] == pytest.approx(1.183)


class TestExportedArtifact:
    def test_model_answers_within_latency_budget(self, bundle, sample_image_bytes):
        """Single-image CPU forward pass (TorchScript) — NFR-P-001 sub-3s budget."""
        tensor, _ = preprocess_image(sample_image_bytes)
        t0 = time.perf_counter()
        with torch.no_grad():
            logits = bundle.disease_model(tensor)
        elapsed = time.perf_counter() - t0
        assert logits.shape == (1, 38)
        assert elapsed < 3.0

    def test_labels_cover_38_classes(self, bundle):
        assert len(bundle.disease_labels) >= 38
        ids = sorted(int(k) for k in bundle.disease_labels)
        assert ids[:2] == [0, 1]
        assert ids[-1] == len(bundle.disease_labels) - 1

    def test_confidence_threshold_gating_value(self, bundle):
        assert 0.0 < bundle.disease_config["confidence_threshold"] <= 1.0
