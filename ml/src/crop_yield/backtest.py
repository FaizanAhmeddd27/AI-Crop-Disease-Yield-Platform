"""Out-of-sample backtesting of the yield risk engine on climate-shock seasons.

Fulfills DEV_PLAN Tasks 3.9 (residual analysis) and 3.11 (risk backtest, FR-Y-009).

Method — leave-one-season-out (LOSO):
For every climate-shock harvest season (2010 floods, 2018 drought, 2022 heatwave)
an XGBoost champion with the exact Y-03 hyperparameters is retrained on the whole
panel *excluding that season*, then used to predict the excluded season. The
quantile ensemble is retrained the same way and widened with the conformal
offset exported in `ml/artifacts/models/yield/v0.1.0/calibration.json`, so the
risk engine consumes genuinely out-of-sample point predictions and
<= 80%-coverage intervals. This is honest: shock-season rows never appear in
the LOSO training matrix.

Residual analysis (Task 3.9) evaluates the production champion's test-split
residuals per district, crop, season and irrigation regime, and saves the top
mis-predictions for the experiment report.

Run:  python -m src.crop_yield.backtest   (from the ml/ directory)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import joblib

from src.common.paths import resolve_artifact_root
from src.common.tracking import start_run
from src.crop_yield.dataset import (
    YieldFeaturePreprocessor,
    load_yield_dataset,
)
from src.crop_yield.models import QuantileYieldEnsemble, XGBoostYieldModel
from src.crop_yield.risk import YieldRiskEngine

SHOCK_YEARS = (2010, 2018, 2022)

CHAMPION_PARAMS = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.04,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "early_stopping_rounds": None,
}


def _align_columns(X: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    return X.reindex(columns=columns, fill_value=0.0)


def _loso_predict(year: int, df: pd.DataFrame) -> pd.DataFrame:
    """Retrain champion models excluding `year` and predict that season out-of-sample."""
    train_df = df[df["season_year"] != year].copy()
    eval_df = df[df["season_year"] == year].copy()
    if len(eval_df) == 0:
        return pd.DataFrame()

    pre = YieldFeaturePreprocessor()
    pre.fit(train_df)
    X_train = pre.transform(train_df)
    X_eval = pre.transform(eval_df)
    all_cols = sorted(set(X_train.columns) | set(X_eval.columns))
    X_train = _align_columns(X_train, all_cols)
    X_eval = _align_columns(X_eval, all_cols)

    y_train = train_df["yield_tha"]

    point_model = XGBoostYieldModel(**CHAMPION_PARAMS)
    point_model.fit(X_train, y_train)
    preds = point_model.predict(X_eval)

    quantile_model = QuantileYieldEnsemble(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    quantile_model.fit(X_train, y_train)
    p10, _, p90 = quantile_model.predict_interval(X_eval)

    # Widen with the production conformal offset (honest >=80% interval)
    offset = load_exported_conformal_offset()
    p10 = p10 - offset
    p90 = p90 + offset

    out = eval_df[["district", "crop", "season_year", "yield_tha", "yield_roll3_tha"]].copy()
    out["pred"] = preds
    out["p10"] = p10
    out["p90"] = p90
    return out


def load_exported_conformal_offset() -> float:
    """Read the production quantile bundle's split-conformal offset."""
    bundle_path = resolve_artifact_root() / "models" / "yield" / "v0.1.0" / "quantile_yield_ensemble.joblib"
    if not bundle_path.exists():
        return 0.0
    bundle = joblib.load(str(bundle_path))
    return float(bundle.get("conformal_offset_tha", 0.0) or 0.0)


def run_risk_backtest(df: pd.DataFrame) -> Dict[str, Any]:
    """LOSO backtest of the risk engine on climate-shock seasons."""
    engine = YieldRiskEngine()
    frames = []
    for year in SHOCK_YEARS:
        loso = _loso_predict(year, df)
        if len(loso):
            frames.append(loso)
    if not frames:
        return {"error": "no shock-year rows in panel"}

    loso_df = pd.concat(frames, ignore_index=True)
    predictions = loso_df["pred"].values
    p10 = loso_df["p10"].values
    p90 = loso_df["p90"].values
    backtest = engine.backtest_historical_shocks(df=loso_df, predictions=predictions, p10=p10, p90=p90)

    # Additional truth check: did the observed yield actually sit inside the LOSO interval?
    coverage = float(
        np.mean((loso_df["yield_tha"] >= loso_df["p10"]) & (loso_df["yield_tha"] <= loso_df["p90"])) * 100.0
    )
    return {
        "method": "leave-one-season-out (LOSO) retraining",
        "shock_years": list(SHOCK_YEARS),
        "risk_levels_by_year": backtest,
        "shock_year_interval_coverage_pct": round(coverage, 2),
        "n_shock_rows": int(len(loso_df)),
        "rows": loso_df.round(4).to_dict(orient="records"),
    }


def run_residual_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """Task 3.9: production-champion residual analysis on the untouched test split (2023+)."""
    from src.crop_yield.dataset import create_temporal_splits

    split_data, pre = create_temporal_splits()
    X_train_full = split_data.X_train
    y_train_full = split_data.y_train

    model = XGBoostYieldModel(**CHAMPION_PARAMS)
    model.fit(X_train_full, y_train_full)
    test_preds = model.predict(split_data.X_test)

    y_test = split_data.y_test.values
    residuals = y_test - test_preds  # positive = under-prediction

    df_test = df[df["season_year"] >= 2023].copy()
    df_test["residual_tha"] = residuals
    df_test["pred_yield_tha"] = test_preds
    df_test["abs_residual_tha"] = np.abs(residuals)

    by_district = (
        df_test.groupby("district")["residual_tha"]
        .agg(["mean", "std", "count"])
        .round(4)
        .sort_values("mean")
    )
    worst_under = by_district.head(6).reset_index().to_dict(orient="records")
    worst_over = by_district.tail(6).iloc[::-1].reset_index().to_dict(orient="records")

    by_crop = df_test.groupby("crop")["residual_tha"].agg(["mean", "std", "count"]).round(4)
    by_year = df_test.groupby("season_year")["residual_tha"].agg(["mean", "std", "count"]).round(4)
    by_irrigation = df_test.groupby("is_barani")["residual_tha"].agg(["mean", "std", "count"]).round(4)

    df_test["pred_yield_tha"] = test_preds
    worst_rows = df_test.nlargest(8, "abs_residual_tha")[
        ["district", "crop", "season_year", "yield_tha", "pred_yield_tha", "residual_tha"]
    ]

    return {
        "split": "test (2023-2024 seasons), production champion fit on train (<= 2021)",
        "overall": {
            "mean_residual_tha": round(float(np.mean(residuals)), 4),
            "std_residual_tha": round(float(np.std(residuals)), 4),
            "mae_tha": round(float(np.mean(np.abs(residuals))), 4),
            "n": int(len(residuals)),
        },
        "bias_read": "positive residual = model under-predicts observed yield",
        "by_crop": by_crop.reset_index().to_dict(orient="records"),
        "by_season": by_year.reset_index().to_dict(orient="records"),
        "by_irrigation": by_irrigation.reset_index().assign(
            irrigation=["irrigated_plains", "barani_rainfed"][: len(by_irrigation)]
        ).to_dict(orient="records"),
        "most_under_predicted_districts": worst_under,
        "most_over_predicted_districts": worst_over,
        "worst_absolute_errors": worst_rows.round(4).to_dict(orient="records"),
    }


def main() -> None:
    df = load_yield_dataset()
    with start_run(
        name="Y-07-risk-backtest-loso",
        params={
            "task": "3.11 + 3.9",
            "method": "LOSO retraining for shock years",
            "champion_params": CHAMPION_PARAMS,
            "conformal_offset_tha": load_exported_conformal_offset(),
        },
    ) as run:
        backtest = run_risk_backtest(df)
        residuals = run_residual_analysis(df)

        bt_path = run.run_dir / "risk_backtest.json"
        bt_path.write_text(json.dumps(backtest, indent=2, default=str), encoding="utf-8")
        run.log_artifact(bt_path)

        res_path = run.run_dir / "residual_analysis.json"
        res_path.write_text(json.dumps(residuals, indent=2, default=str), encoding="utf-8")
        run.log_artifact(res_path)

        for year, stats in backtest.get("risk_levels_by_year", {}).items():
            run.log_metrics(
                **{
                    f"loso_{year}_high_risk_pct": stats.get("high_risk_pct", 0.0),
                    f"loso_{year}_coverage_pct": backtest.get("shock_year_interval_coverage_pct", 0.0),
                }
            )
        run.log_metrics(
            residual_mean_tha=residuals["overall"]["mean_residual_tha"],
            residual_mae_tha=residuals["overall"]["mae_tha"],
        )
        print("Risk backtest (LOSO) complete:", json.dumps(backtest["risk_levels_by_year"], indent=2))
        print("Residual analysis:", json.dumps(residuals["overall"], indent=2))


if __name__ == "__main__":
    main()
