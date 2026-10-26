"""SHAP (SHapley Additive exPlanations) Feature Attribution for Crop Yield Models.

Fulfills DEV_PLAN Task 4.6 (FR-X-005).
Uses TreeExplainer to decompose tabular crop yield predictions into exact,
additive feature contributions for both global importance and localized farmer advisories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

try:
    from src.common.paths import resolve_artifact_root
except ImportError:
    def resolve_artifact_root() -> Path:
        return Path(__file__).resolve().parents[2] / "artifacts"


class YieldSHAPExplainer:
    """Wrapper around shap.TreeExplainer for the production XGBoost yield model."""

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        feature_names: Optional[List[str]] = None,
    ):
        path = model_path or (resolve_artifact_root() / "models" / "yield" / "v0.1.0" / "xgb_yield_model.json")
        self.model_path = Path(path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Trained XGBoost model not found at {self.model_path}")

        # Load native booster
        self.booster = xgb.Booster()
        self.booster.load_model(str(self.model_path))

        self.explainer = shap.TreeExplainer(self.booster)
        self.feature_names = feature_names or []
        exp_val = self.explainer.expected_value
        self.base_value = float(np.ravel(exp_val)[0]) if hasattr(exp_val, "__iter__") else float(exp_val)

    def explain_instance(
        self,
        features_df: pd.DataFrame,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Compute local feature attributions for a single district-year feature record."""
        if len(features_df) != 1:
            raise ValueError("explain_instance expects a single-row DataFrame.")

        cols = self.feature_names if self.feature_names else features_df.columns.tolist()
        dmatrix = xgb.DMatrix(features_df[cols])

        # Point prediction
        predicted_yield = float(self.booster.predict(dmatrix)[0])

        # SHAP values
        shap_values = self.explainer.shap_values(features_df[cols])[0]

        # Additivity verification: sum(shap_values) == predicted_yield - base_value
        sum_shap = float(np.sum(shap_values))
        additivity_diff = abs((self.base_value + sum_shap) - predicted_yield)
        is_additive = additivity_diff < 0.01

        # Rank features by absolute magnitude
        attributions: List[Dict[str, Any]] = []
        for name, phi, val in zip(cols, shap_values, features_df.iloc[0].values):
            attributions.append({
                "feature": name,
                "feature_value": float(val) if isinstance(val, (int, float, np.number)) else str(val),
                "shap_value": round(float(phi), 4),
                "impact": "positive" if phi > 0 else ("negative" if phi < 0 else "neutral"),
                "abs_magnitude": round(abs(float(phi)), 4),
            })

        attributions.sort(key=lambda x: x["abs_magnitude"], reverse=True)

        # Generate top drivers and human-readable narrative
        top_drivers = attributions[:top_k]
        narratives = self._generate_farmer_narratives(top_drivers)

        return {
            "base_value_tha": round(self.base_value, 4),
            "predicted_yield_tha": round(predicted_yield, 4),
            "is_additive": is_additive,
            "additivity_error": round(additivity_diff, 6),
            "top_drivers": top_drivers,
            "narratives": narratives,
            "all_attributions": attributions,
        }

    def compute_global_summary(
        self,
        X_eval: pd.DataFrame,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Compute mean absolute SHAP values across evaluation split."""
        cols = self.feature_names if self.feature_names else X_eval.columns.tolist()
        shap_values = self.explainer.shap_values(X_eval[cols])
        mean_abs = np.mean(np.abs(shap_values), axis=0)

        global_rank = [
            {"feature": name, "mean_abs_shap": round(float(val), 4)}
            for name, val in zip(cols, mean_abs)
        ]
        global_rank.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
        return global_rank[:top_k]

    def _generate_farmer_narratives(self, top_drivers: List[Dict[str, Any]]) -> List[str]:
        """Convert technical feature contributions into intuitive agronomic messages."""
        messages: List[str] = []

        descriptions = {
            "w_heat_stress_days": "Terminal heat stress (days >= 35°C during grain filling)",
            "w_rain_total_mm": "Seasonal cumulative rainfall",
            "w_water_balance_mm": "Seasonal soil water balance",
            "w_gdd_c": "Growing degree days (thermal energy accumulation)",
            "yield_roll3_tha": "District 3-year historical baseline yield",
            "is_barani": "Rainfed (Barani) production constraint",
            "soil_soc_g_kg": "Soil organic carbon content",
            "soil_awc_pct": "Soil available water holding capacity",
            "area_000ha": "Total cultivated area scale factor",
        }

        for item in top_drivers:
            feat = item["feature"]
            phi = item["shap_value"]
            val = item["feature_value"]
            label = descriptions.get(feat, feat)

            if abs(phi) < 0.01:
                continue

            sign_str = f"+{phi:.2f}" if phi > 0 else f"{phi:.2f}"
            effect = "boosted" if phi > 0 else "reduced"

            messages.append(f"{label} ({val}) {effect} expected yield by {sign_str} t/ha.")

        return messages


if __name__ == "__main__":
    print("Testing YieldSHAPExplainer...")
    from src.crop_yield.dataset import create_temporal_splits

    split_data, _ = create_temporal_splits()
    explainer = YieldSHAPExplainer(feature_names=split_data.feature_names)

    sample_row = split_data.X_test.iloc[[0]]
    result = explainer.explain_instance(sample_row)

    print("Explanation computed successfully!")
    print(f"Base Value: {result['base_value_tha']} t/ha | Predicted: {result['predicted_yield_tha']} t/ha")
    print(f"Additivity Verified: {result['is_additive']}")
    print("Top 3 Drivers:")
    for d in result["top_drivers"][:3]:
        print(f"  - {d['feature']}: {d['shap_value']:+.3f} t/ha (Value={d['feature_value']})")
    print("\nNarrative Guidance:")
    for n in result["narratives"][:3]:
        print(f"  * {n}")
    print("SHAP explainer verified.")
