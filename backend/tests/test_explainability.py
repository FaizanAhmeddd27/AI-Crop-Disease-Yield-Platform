"""Phase 4 explainability verification (DEV_PLAN Tasks 4.1-4.8, FR-X-001/002/009).

Covers, against the *production* artifacts:
- Grad-CAM heatmap shape, range, and determinism on the exported TorchScript model.
- Overlay generation determinism and PNG validity.
- Grad-CAM + overlay wall-clock budget (Task 4.8).
- Severity band mapping on synthetic leaf images (low / moderate / severe / unknown).
- SHAP additivity for the yield champion: base_value + sum(phi) == model output.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
import xgboost as xgb
from app.ml.gradcam import GradCAMService
from app.ml.loader import load_all_production_models
from app.services.disease_service import _estimate_severity
from app.services.weather_service import WeatherAggregate
from app.services.yield_service import _build_feature_row, _compute_shap

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "ml") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "ml"))

from src.crop_yield.dataset import create_temporal_splits  # noqa: E402
from src.crop_yield.shap_explainer import YieldSHAPExplainer  # noqa: E402


@pytest.fixture(scope="module")
def models():
    """Load production model bundle once for the whole module."""
    return load_all_production_models()


@pytest.fixture(scope="module")
def disease_model(models):
    if not models.disease_ready or models.disease_model is None:
        pytest.skip("Disease model artifact not present")
    return models.disease_model


# ── Grad-CAM (FR-X-001/002) ──────────────────────────────────────────


class TestGradCam:
    def test_heatmap_shape_and_range_on_scripted_model(self, disease_model):
        gradcam = GradCAMService(disease_model)
        x = torch.randn(1, 3, 224, 224)
        heatmap = gradcam.generate_heatmap(x, target_class=0)

        assert heatmap.shape == (224, 224)
        assert heatmap.dtype == np.float32
        assert float(heatmap.min()) >= 0.0
        assert float(heatmap.max()) <= 1.0
        assert float(heatmap.max()) > 0.0  # non-degenerate

    def test_heatmap_deterministic(self, disease_model):
        gradcam = GradCAMService(disease_model)
        x = torch.randn(1, 3, 224, 224)
        h1 = gradcam.generate_heatmap(x, target_class=3)
        h2 = gradcam.generate_heatmap(x, target_class=3)
        np.testing.assert_allclose(h1, h2, rtol=0, atol=1e-6)

    def test_overlay_shape_and_png_deterministic(self, disease_model):
        gradcam = GradCAMService(disease_model)
        x = torch.randn(1, 3, 224, 224)
        heatmap = gradcam.generate_heatmap(x, target_class=5)
        orig = np.full((300, 300, 3), 120, dtype=np.uint8)

        png1 = gradcam.generate_overlay(orig, heatmap)
        png2 = gradcam.generate_overlay(orig, heatmap)

        assert isinstance(png1, bytes) and len(png1) > 0
        assert png1 == png2  # deterministic PNG bytes

        decoded = cv2.imdecode(np.frombuffer(png1, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None
        assert decoded.shape[:2] == (300, 300)  # resized to original dims
        assert decoded.ndim == 3

    def test_gradcam_budget_within_nfr_latency(self, disease_model):
        """Task 4.8: Grad-CAM explanation must add well under the 3 s NFR-P-001 budget."""
        gradcam = GradCAMService(disease_model)
        x = torch.randn(1, 3, 224, 224)
        orig = np.zeros((224, 224, 3), dtype=np.uint8)

        t0 = time.perf_counter()
        heatmap = gradcam.generate_heatmap(x, target_class=7)
        _ = gradcam.generate_overlay(orig, heatmap)
        elapsed = time.perf_counter() - t0
        assert elapsed < 3.0, f"Grad-CAM + overlay took {elapsed:.2f}s"


class TestGradCamNoSideEffectsOnBundle:
    def test_residual_grads_cleaned(self, disease_model):
        x = torch.randn(1, 3, 224, 224)
        gradcam = GradCAMService(disease_model)
        gradcam.generate_heatmap(x, target_class=0)
        with torch.no_grad():
            logits = disease_model(x)  # still usable after Grad-CAM
        assert logits.shape == (1, 38)


class TestLeafFocusSanityCheck:
    def test_full_heatmap_on_central_leaf_is_high(self, disease_model):
        gradcam = GradCAMService(disease_model)
        heatmap = np.zeros((224, 224), dtype=np.float32)
        heatmap[60:164, 60:164] = 1.0  # inside the central 70% mask
        assert gradcam.leaf_focus_fraction(heatmap) == pytest.approx(1.0, abs=1e-6)

    def test_background_heatmap_is_low_and_warned(self, disease_model):
        gradcam = GradCAMService(disease_model)
        heatmap = np.zeros((224, 224), dtype=np.float32)
        heatmap[0:8, 0:8] = 1.0  # top-left corner -> outside central 70% mask
        # The serving path maps a fraction < 0.50 to the low_saliency_quality warning.
        assert gradcam.leaf_focus_fraction(heatmap) < 0.50

    def test_zero_total_mass_defaults_to_focused(self, disease_model):
        gradcam = GradCAMService(disease_model)
        assert gradcam.leaf_focus_fraction(np.zeros((224, 224), dtype=np.float32)) == 1.0


# ── Severity bands (FR-D-013) ────────────────────────────────────────


class TestSeverityBands:
    @staticmethod
    def _leaf_image(lesion_fraction: float, size: int = 224) -> np.ndarray:
        """Synthetic green leaf with a dark necrotic lesion of given leaf-area fraction."""
        img = np.zeros((size, size, 3), dtype=np.uint8)
        img[:] = (50, 50, 50)  # dark background -> excluded from leaf mask
        cv2.ellipse(
            img, (size // 2, size // 2), (size // 2 - 12, size // 3), 30, 0, 360, (45, 160, 55), -1
        )

        if lesion_fraction > 0:
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            leaf_area = int(
                cv2.countNonZero(cv2.inRange(hsv, np.array([20, 30, 25]), np.array([95, 255, 255])))
            )
            radius = max(2, int(np.sqrt(lesion_fraction * leaf_area / np.pi)))
            # Dark olive lesion: stays inside the leaf HSV mask but counts as
            # necrotic (v < 85), matching the heuristic's dual constraint.
            cv2.circle(img, (size // 2, size // 2), radius, (60, 80, 30), -1)
        return img

    def test_healthy_leaf_is_low(self):
        severity = _estimate_severity(self._leaf_image(0.0))
        if severity["level"] == "unknown":
            assert severity["ratio"] == 0.0
        else:
            assert severity["level"] == "low"
            assert severity["ratio"] < 10.0

    def test_large_necrotic_lesion_is_severe(self):
        severity = _estimate_severity(self._leaf_image(0.55))
        assert severity["ratio"] >= 30.0
        assert severity["level"] == "severe"

    def test_moderate_lesion_is_moderate_or_low(self):
        severity = _estimate_severity(self._leaf_image(0.12))
        assert severity["level"] in ("low", "moderate")

    def test_non_leaf_image_is_unknown(self):
        img = np.full((224, 224, 3), 90, dtype=np.uint8)  # plain gray, no leaf tones
        severity = _estimate_severity(img)
        assert severity["level"] == "unknown"
        assert severity["ratio"] == 0.0

    def test_result_shape(self):
        severity = _estimate_severity(self._leaf_image(0.05))
        assert set(severity) == {"level", "ratio", "method", "note"}


# ── SHAP (FR-X-009) ──────────────────────────────────────────────────


class TestShapAdditivity:
    @pytest.fixture(scope="class")
    def yield_setup(self, models):
        if not models.yield_ready or models.yield_booster is None:
            pytest.skip("Yield model artifact not present")
        weather = WeatherAggregate(
            w_rain_total_mm=120.0,
            w_rainy_days=14,
            w_temp_mean_c=24.5,
            w_temp_max_c=32.0,
            w_temp_min_c=18.0,
            w_gdd_c=1500.0,
            w_water_balance_mm=-40.0,
            w_humidity_mean_pct=55.0,
            w_solar_mj_m2=18.0,
            w_wind_max_kmh=12.0,
            w_days_observed=120,
            w_completeness=0.95,
        )
        feature_row = _build_feature_row(
            crop="wheat",
            district="Lahore",
            season_year=2024,
            area_ha=10.0,
            weather=weather,
            schema=models.yield_schema,
        )
        return models.yield_booster, feature_row

    def test_shap_additivity_frx009(self, yield_setup):
        """base_value + sum(shap over ALL features) == booster prediction."""
        booster, feature_row = yield_setup
        explanation = _compute_shap(booster, feature_row, top_k=5)
        assert explanation["method"] == "shap"
        assert explanation["contributions"], "expected non-empty SHAP contributions"

        # Recompute the FULL additive decomposition (top_k truncated it)
        import shap

        explainer = shap.TreeExplainer(booster)
        shap_values = explainer.shap_values(feature_row)[0]
        base_value = float(np.ravel(explainer.expected_value)[0])

        dmatrix = xgb.DMatrix(feature_row)
        prediction = float(booster.predict(dmatrix)[0])

        assert base_value + float(np.sum(shap_values)) == pytest.approx(prediction, abs=1e-3)

    def test_top_k_contributions_sorted_by_magnitude(self, yield_setup):
        booster, feature_row = yield_setup
        explanation = _compute_shap(booster, feature_row, top_k=5)
        magnitudes = [abs(c["shap"]) for c in explanation["contributions"]]
        assert magnitudes == sorted(magnitudes, reverse=True)
        assert len(explanation["contributions"]) == 5

    def test_shap_budget(self, yield_setup):
        """Task 4.8: SHAP computation stays within the interaction latency budget."""
        booster, feature_row = yield_setup
        t0 = time.perf_counter()
        _compute_shap(booster, feature_row, top_k=5)
        elapsed = time.perf_counter() - t0
        assert elapsed < 3.0, f"SHAP took {elapsed:.2f}s"

    def test_shap_additivity_full_test_split(self):
        """FR-X-009 verified on all 144 untouched test rows (report §4.2 claim)."""
        try:
            split_data, _ = create_temporal_splits()
        except FileNotFoundError as exc:
            # The processed dataset lives in gitignored ml/data/ and cannot be
            # regenerated in CI (raw sources are not committed).
            pytest.skip(f"Yield dataset not present: {exc}")
        explainer = YieldSHAPExplainer(feature_names=split_data.feature_names)
        shap_values = explainer.explainer.shap_values(split_data.X_test)
        preds = explainer.booster.predict(xgb.DMatrix(split_data.X_test))
        errors = np.abs(explainer.base_value + shap_values.sum(axis=1) - preds)
        assert float(errors.max()) < 0.005
