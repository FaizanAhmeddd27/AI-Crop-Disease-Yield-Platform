"""Comprehensive evaluation and slice metrics for crop yield models.

Fulfills DEV_PLAN Tasks 3.9, 3.10 (NFR-ML-004, NFR-ML-005).
Calculates:
- Standard regression metrics: MAE, RMSE, R2, MAPE.
- Prediction interval metrics: Empirical 80% coverage and mean interval width.
- Stratified slice metrics: Wheat vs. Maize, Barani vs. Irrigated, and Extreme weather years.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def calculate_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Calculate standard regression metrics: MAE, RMSE, R2, MAPE."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))

    # MAPE: avoid div by zero
    non_zero_mask = y_true > 0.05
    if non_zero_mask.any():
        mape = float(np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100.0)
    else:
        mape = 0.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "mape_pct": round(mape, 2),
    }


def calculate_interval_metrics(
    y_true: np.ndarray,
    p10: np.ndarray,
    p90: np.ndarray,
) -> Dict[str, float]:
    """Calculate empirical coverage and sharpness for 80% prediction interval."""
    y_true = np.asarray(y_true, dtype=float)
    p10 = np.asarray(p10, dtype=float)
    p90 = np.asarray(p90, dtype=float)

    inside_mask = (y_true >= p10) & (y_true <= p90)
    coverage = float(inside_mask.mean() * 100.0)
    mean_width = float(np.mean(p90 - p10))

    return {
        "interval_coverage_pct": round(coverage, 2),
        "mean_interval_width_tha": round(mean_width, 4),
    }


def evaluate_model_slices(
    df_eval: pd.DataFrame,
    y_true_col: str = "yield_tha",
    y_pred_col: str = "pred_yield_tha",
    p10_col: Optional[str] = "p10_yield_tha",
    p90_col: Optional[str] = "p90_yield_tha",
) -> Dict[str, Any]:
    """Compute overall and stratified slice evaluations."""
    results: Dict[str, Any] = {}

    y_true_all = df_eval[y_true_col].values
    y_pred_all = df_eval[y_pred_col].values

    # Overall metrics
    overall = calculate_regression_metrics(y_true_all, y_pred_all)
    if p10_col in df_eval.columns and p90_col in df_eval.columns:
        interval_stats = calculate_interval_metrics(
            y_true_all, df_eval[p10_col].values, df_eval[p90_col].values
        )
        overall.update(interval_stats)
    results["overall"] = overall

    # Slice by crop
    results["by_crop"] = {}
    for crop_name in df_eval["crop"].unique():
        sub = df_eval[df_eval["crop"] == crop_name]
        results["by_crop"][crop_name] = calculate_regression_metrics(
            sub[y_true_col].values, sub[y_pred_col].values
        )

    # Slice by irrigation regime (is_barani)
    results["by_irrigation"] = {}
    for barani_val, label in [(1, "barani_rainfed"), (0, "irrigated_plains")]:
        sub = df_eval[df_eval["is_barani"] == barani_val]
        if len(sub) > 0:
            results["by_irrigation"][label] = calculate_regression_metrics(
                sub[y_true_col].values, sub[y_pred_col].values
            )

    # Slice by climate shock years
    results["by_shock_years"] = {}
    for s_year in [2010, 2018, 2022]:
        sub = df_eval[df_eval["season_year"] == s_year]
        if len(sub) > 0:
            label = f"year_{s_year}"
            results["by_shock_years"][label] = calculate_regression_metrics(
                sub[y_true_col].values, sub[y_pred_col].values
            )

    return results
