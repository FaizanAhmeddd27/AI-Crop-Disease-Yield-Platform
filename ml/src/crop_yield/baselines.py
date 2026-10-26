"""Baseline models for crop yield prediction: Y-00 (Naïve) and Y-01 (Linear / Regularized).

Fulfills DEV_PLAN Tasks 3.2, 3.3.
- Y-00: Naïve prior year yield, 3-year rolling mean, district mean.
- Y-01: Linear Regression, Ridge (L2), and Lasso (L1).
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import Lasso, LinearRegression, Ridge


class NaiveYieldModel:
    """Y-00 Naïve baseline predicting directly from prior historical yields."""

    def __init__(self, strategy: str = "last_year"):
        if strategy not in ("last_year", "roll3", "district_mean"):
            raise ValueError(f"Unknown strategy: '{strategy}'. Expected 'last_year', 'roll3', or 'district_mean'.")
        self.strategy = strategy
        self.district_crop_means: Dict[str, float] = {}
        self.global_mean: float = 3.2

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "NaiveYieldModel":
        """Compute training historical means per crop and district."""
        self.global_mean = float(y.mean())
        if "district" in X.columns and "crop" in X.columns:
            df = X[["district", "crop"]].copy()
            df["y"] = y.values
            self.district_crop_means = df.groupby(["district", "crop"])["y"].mean().to_dict()
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate naïve predictions according to configured strategy."""
        n = len(X)
        preds = np.zeros(n, dtype=float)

        if self.strategy == "last_year" and "yield_lag1_tha" in X.columns:
            preds = X["yield_lag1_tha"].fillna(self.global_mean).values.astype(float)
        elif self.strategy == "roll3" and "yield_roll3_tha" in X.columns:
            preds = X["yield_roll3_tha"].fillna(self.global_mean).values.astype(float)
        else:
            # Fallback to district mean
            for i, (_, row) in enumerate(X.iterrows()):
                d = row.get("district")
                c = row.get("crop")
                preds[i] = self.district_crop_means.get((d, c), self.global_mean)

        return np.clip(preds, 0.2, 12.0)


class LinearYieldModel:
    """Y-01 Linear, Ridge, or Lasso regression model."""

    def __init__(self, model_type: str = "ridge", alpha: float = 1.0, random_state: int = 42):
        self.model_type = model_type.lower()
        self.alpha = alpha
        self.random_state = random_state

        if self.model_type == "linear":
            self.model = LinearRegression()
        elif self.model_type == "ridge":
            self.model = Ridge(alpha=self.alpha, random_state=self.random_state)
        elif self.model_type == "lasso":
            self.model = Lasso(alpha=self.alpha, random_state=self.random_state, max_iter=2000)
        else:
            raise ValueError(f"Unknown linear model type: '{model_type}'. Expected 'linear', 'ridge', or 'lasso'.")

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LinearYieldModel":
        self.model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = self.model.predict(X)
        return np.clip(preds, 0.2, 12.0)


def build_baseline_model(config: Dict[str, Any]) -> Any:
    """Factory creating baseline models from experiment config dictionary."""
    model_name = config.get("model_name", "naive_last_year").lower()

    if model_name.startswith("naive_"):
        strategy = model_name.replace("naive_", "")
        return NaiveYieldModel(strategy=strategy)
    elif model_name in ("linear", "ridge", "lasso"):
        alpha = float(config.get("alpha", 1.0))
        return LinearYieldModel(model_type=model_name, alpha=alpha)
    else:
        raise ValueError(f"Unknown baseline model name: '{model_name}'")
