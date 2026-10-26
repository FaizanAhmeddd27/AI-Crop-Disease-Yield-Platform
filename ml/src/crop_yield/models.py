"""Tree and Gradient-Boosted models for Crop Yield prediction: Y-02 (Random Forest), Y-03 (XGBoost), and Y-06 (Quantile Regression).

Fulfills DEV_PLAN Tasks 3.4, 3.5, 3.10.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
import xgboost as xgb


class RandomForestYieldModel:
    """Y-02 Random Forest regressor for multi-crop district yield prediction."""

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: Optional[int] = 8,
        min_samples_split: int = 5,
        min_samples_leaf: int = 3,
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.n_jobs = n_jobs

        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RandomForestYieldModel":
        self.model.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = self.model.predict(X)
        return np.clip(preds, 0.2, 12.0)

    def save(self, filepath: Union[str, Path]) -> None:
        joblib.dump(self.model, str(filepath))

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "RandomForestYieldModel":
        instance = cls()
        instance.model = joblib.load(str(filepath))
        return instance


class XGBoostYieldModel:
    """Y-03 Extreme Gradient Boosting (XGBoost) model with early stopping on validation."""

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
        early_stopping_rounds: Optional[int] = 20,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.reg_alpha = reg_alpha
        self.reg_lambda = reg_lambda
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.early_stopping_rounds = early_stopping_rounds

        self.model = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            reg_alpha=self.reg_alpha,
            reg_lambda=self.reg_lambda,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            objective="reg:squarederror",
            eval_metric="rmse",
            # xgboost >= 2.0 moved early stopping to the constructor
            early_stopping_rounds=self.early_stopping_rounds,
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        eval_set: Optional[List[Tuple[pd.DataFrame, pd.Series]]] = None,
        early_stopping_rounds: Optional[int] = None,  # noqa: ARG002 — constructor-configured
    ) -> "XGBoostYieldModel":
        if eval_set:
            self.model.fit(
                X,
                y,
                eval_set=eval_set,
                verbose=False,
            )
        else:
            self.model.fit(X, y, verbose=False)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = self.model.predict(X)
        return np.clip(preds, 0.2, 12.0)

    def get_feature_importances(self, feature_names: List[str]) -> Dict[str, float]:
        """Return normalized feature importance dictionary sorted descending."""
        scores = self.model.feature_importances_
        res = {name: float(scores[i]) for i, name in enumerate(feature_names)}
        return dict(sorted(res.items(), key=lambda item: item[1], reverse=True))

    def save(self, filepath: Union[str, Path]) -> None:
        path = Path(filepath)
        if path.suffix == ".json":
            self.model.save_model(str(path))
        else:
            joblib.dump(self.model, str(path))

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "XGBoostYieldModel":
        instance = cls()
        path = Path(filepath)
        if path.suffix == ".json":
            instance.model.load_model(str(path))
        else:
            instance.model = joblib.load(str(path))
        return instance


class QuantileYieldEnsemble:
    """Y-06 Uncertainty estimation providing 80% prediction intervals [p10, p90] and median p50.

    Intervals can optionally be recalibrated via **split conformal prediction**
    (Vovk et al. 2005; Papadopoulos et al. 2002): nonconformity scores
    ``s_i = max(p10_i - y_i, y_i - p90_i)`` are computed on a held-out
    calibration split, and the (1-alpha) finite-sample quantile of those
    scores is stored as ``conformal_offset_tha``. At inference the raw
    quantile interval is symmetrically widened by that offset, which
    guarantees >= target coverage under exchangeability.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.conformal_offset_tha: float = 0.0
        self.calibration_applied: bool = False

        # Train 3 models: lower bound (alpha=0.10), median (alpha=0.50), upper bound (alpha=0.90)
        self.model_p10 = GradientBoostingRegressor(
            loss="quantile",
            alpha=0.10,
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
        )
        self.model_p50 = GradientBoostingRegressor(
            loss="quantile",
            alpha=0.50,
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
        )
        self.model_p90 = GradientBoostingRegressor(
            loss="quantile",
            alpha=0.90,
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "QuantileYieldEnsemble":
        self.model_p10.fit(X, y)
        self.model_p50.fit(X, y)
        self.model_p90.fit(X, y)
        return self

    def calibrate_conformal(
        self,
        X_cal: pd.DataFrame,
        y_cal: pd.Series,
        target_coverage: float = 0.80,
    ) -> Dict[str, Any]:
        """Fit the split-conformal offset on a calibration split (never used for training).

        Returns a summary dict with the pre/post calibration coverage on the
        calibration split itself, for reporting in run records.
        """
        raw_p10, _, raw_p90 = self._predict_interval_raw(X_cal)
        y_np = np.asarray(y_cal, dtype=float)

        # Signed nonconformity: positive when y falls outside the raw interval
        scores = np.maximum(raw_p10 - y_np, y_np - raw_p90)

        n = len(scores)
        alpha = 1.0 - target_coverage
        # Finite-sample correction (Vovk): ceil((n+1)(1-alpha))/n quantile
        q_level = min(1.0, float(np.ceil((n + 1) * (1.0 - alpha)) / n))
        offset = float(np.quantile(scores, q_level, method="higher"))

        pre_cov = float(np.mean((y_np >= raw_p10) & (y_np <= raw_p90)) * 100.0)
        post_p10, _, post_p90 = raw_p10 - offset, raw_p10, raw_p90 + offset
        post_cov = float(np.mean((y_np >= post_p10) & (y_np <= post_p90)) * 100.0)

        self.conformal_offset_tha = round(offset, 4)
        self.calibration_applied = True
        return {
            "method": "split_conformal",
            "target_coverage_pct": round(target_coverage * 100.0, 1),
            "n_calibration_samples": n,
            "conformal_offset_tha": self.conformal_offset_tha,
            "calibration_coverage_before_pct": round(pre_cov, 2),
            "calibration_coverage_after_pct": round(post_cov, 2),
        }

    def _predict_interval_raw(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Raw (uncalibrated) quantile outputs with monotonicity enforcement."""
        p10 = np.clip(self.model_p10.predict(X), 0.2, 12.0)
        p50 = np.clip(self.model_p50.predict(X), 0.2, 12.0)
        p90 = np.clip(self.model_p90.predict(X), 0.2, 12.0)

        # Ensure monotonicity: p10 <= p50 <= p90
        p50 = np.maximum(p10, p50)
        p90 = np.maximum(p50, p90)
        return p10, p50, p90

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return median (p50) point prediction."""
        preds = self.model_p50.predict(X)
        return np.clip(preds, 0.2, 12.0)

    def predict_interval(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (p10_lower, p50_median, p90_upper) prediction intervals.

        When the ensemble has been conformally calibrated, the interval is
        widened symmetrically by ``conformal_offset_tha``.
        """
        p10, p50, p90 = self._predict_interval_raw(X)

        if self.calibration_applied and self.conformal_offset_tha > 0.0:
            off = self.conformal_offset_tha
            p10 = p10 - off
            p90 = p90 + off
            # Keep the median inside the widened interval
            p50 = np.clip(p50, p10, p90)
        return p10, p50, p90

    def save(self, filepath: Union[str, Path]) -> None:
        bundle = {
            "p10": self.model_p10,
            "p50": self.model_p50,
            "p90": self.model_p90,
            "conformal_offset_tha": self.conformal_offset_tha,
            "calibration_applied": self.calibration_applied,
        }
        joblib.dump(bundle, str(filepath))

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> "QuantileYieldEnsemble":
        bundle = joblib.load(str(filepath))
        instance = cls()
        instance.model_p10 = bundle["p10"]
        instance.model_p50 = bundle["p50"]
        instance.model_p90 = bundle["p90"]
        instance.conformal_offset_tha = float(bundle.get("conformal_offset_tha", 0.0))
        instance.calibration_applied = bool(bundle.get("calibration_applied", False))
        return instance


def build_yield_model(config: Dict[str, Any]) -> Any:
    """Model factory building yield model from config."""
    name = config.get("model_name", "xgboost").lower()

    if name == "random_forest":
        return RandomForestYieldModel(
            n_estimators=config.get("n_estimators", 200),
            max_depth=config.get("max_depth", 8),
            random_state=config.get("random_state", 42),
        )
    elif name == "xgboost":
        return XGBoostYieldModel(
            n_estimators=config.get("n_estimators", 300),
            max_depth=config.get("max_depth", 4),
            learning_rate=config.get("learning_rate", 0.05),
            subsample=config.get("subsample", 0.8),
            colsample_bytree=config.get("colsample_bytree", 0.8),
            reg_alpha=config.get("reg_alpha", 0.1),
            reg_lambda=config.get("reg_lambda", 1.0),
            random_state=config.get("random_state", 42),
        )
    elif name in ("quantile_ensemble", "quantile_xgboost"):
        return QuantileYieldEnsemble(
            n_estimators=config.get("n_estimators", 200),
            max_depth=config.get("max_depth", 4),
            learning_rate=config.get("learning_rate", 0.05),
            random_state=config.get("random_state", 42),
        )
    else:
        raise ValueError(f"Unknown yield model name: '{name}'")
