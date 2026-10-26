"""Dataset loading, temporal train/val/test splitting, and feature preparation for crop yield models.

Fulfills DEV_PLAN Tasks 1.11, 3.1 (ADR-0010, ADR-0013).
Implements strict time-based leave-future-years-out splits:
- Train: seasons <= 2021 (2008 to 2021, ~14 harvest seasons)
- Val: season 2022 (calibration and hyperparameter tuning)
- Test: seasons 2023 to 2024 (unseen final evaluation)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from .features import (
        ALL_MODEL_FEATURES,
        CATEGORICAL_FEATURES,
        NUMERICAL_FEATURES,
        TARGET_COLUMN,
    )
except ImportError:
    from src.crop_yield.features import (
        ALL_MODEL_FEATURES,
        CATEGORICAL_FEATURES,
        NUMERICAL_FEATURES,
        TARGET_COLUMN,
    )

try:
    from src.common.paths import resolve_data_root
except ImportError:
    def resolve_data_root() -> Path:
        return Path(__file__).resolve().parents[2] / "data"


@dataclass
class YieldSplitData:
    """Container for temporally split feature matrices and targets."""

    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    feature_names: List[str]
    df_raw: pd.DataFrame


class YieldFeaturePreprocessor:
    """Prepares and encodes features for tabular models, handling categorical encoding and missing history."""

    def __init__(self, scale_numerical: bool = False):
        self.scale_numerical = scale_numerical
        self.scaler: Optional[StandardScaler] = None
        self.district_encoder: Optional[OneHotEncoder] = None
        self.encoded_feature_names: List[str] = []
        self.district_lag_defaults: Dict[Tuple[str, str], float] = {}

    def fit(self, df_train: pd.DataFrame) -> "YieldFeaturePreprocessor":
        """Learn encodings, means, and default historical lags from the training split only."""
        # Compute baseline yields per district & crop on train split
        grouped = df_train.groupby(["district", "crop"])["yield_tha"].mean()
        self.district_lag_defaults = grouped.to_dict()

        if self.scale_numerical:
            self.scaler = StandardScaler()
            num_clean = self._impute_numerical(df_train[list(NUMERICAL_FEATURES)].copy())
            self.scaler.fit(num_clean)

        return self

    def _impute_numerical(self, df_num: pd.DataFrame, df_raw: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Impute missing history features (early seasons) using train-fit district defaults."""
        df_imputed = df_num.copy()
        for col in ["yield_lag1_tha", "yield_roll3_tha", "yield_trend_tha_per_year"]:
            if col in df_imputed.columns and df_imputed[col].isna().any():
                if col == "yield_trend_tha_per_year":
                    df_imputed[col] = df_imputed[col].fillna(0.0)
                else:
                    # Fill with crop/district historical default or provincial median
                    if df_raw is not None:
                        for idx, row in df_raw.iterrows():
                            if pd.isna(df_imputed.at[idx, col]):
                                key = (row["district"], row["crop"])
                                def_val = self.district_lag_defaults.get(key, 3.0)
                                df_imputed.at[idx, col] = def_val
                    else:
                        df_imputed[col] = df_imputed[col].fillna(df_imputed[col].median())
        return df_imputed

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw feature dataframe into model-ready matrix."""
        df_transformed = df.copy()

        # 1. Impute missing history values
        num_part = self._impute_numerical(df_transformed[list(NUMERICAL_FEATURES)], df_transformed)

        if self.scale_numerical and self.scaler is not None:
            scaled_vals = self.scaler.transform(num_part)
            num_part = pd.DataFrame(scaled_vals, columns=num_part.columns, index=df.index)

        # 2. Categorical dummy encoding for district, crop, zone
        cat_part = pd.get_dummies(
            df_transformed[list(CATEGORICAL_FEATURES)],
            columns=list(CATEGORICAL_FEATURES),
            drop_first=False,
            dtype=float,
        )

        final_df = pd.concat([cat_part, num_part], axis=1)
        self.encoded_feature_names = final_df.columns.tolist()
        return final_df


def load_yield_dataset(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the processed Punjab crop yield panel CSV."""
    path = csv_path or (resolve_data_root() / "processed" / "yield_dataset_punjab.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"Processed yield dataset not found at {path}. Run `python -m src.crop_yield.ingest` first."
        )
    return pd.read_csv(path)


def create_temporal_splits(
    df: Optional[pd.DataFrame] = None,
    train_end_year: int = 2021,
    val_year: int = 2022,
    test_start_year: int = 2023,
    scale_numerical: bool = False,
) -> Tuple[YieldSplitData, YieldFeaturePreprocessor]:
    """Create leakage-free temporal splits and return aligned feature matrices."""
    if df is None:
        df = load_yield_dataset()

    train_mask = df["season_year"] <= train_end_year
    val_mask = df["season_year"] == val_year
    test_mask = df["season_year"] >= test_start_year

    df_train = df.loc[train_mask].copy()
    df_val = df.loc[val_mask].copy()
    df_test = df.loc[test_mask].copy()

    preprocessor = YieldFeaturePreprocessor(scale_numerical=scale_numerical)
    preprocessor.fit(df_train)

    X_train = preprocessor.transform(df_train)
    X_val = preprocessor.transform(df_val)
    X_test = preprocessor.transform(df_test)

    # Align column sets across splits in case any category wasn't present
    all_cols = sorted(list(set(X_train.columns) | set(X_val.columns) | set(X_test.columns)))
    X_train = X_train.reindex(columns=all_cols, fill_value=0.0)
    X_val = X_val.reindex(columns=all_cols, fill_value=0.0)
    X_test = X_test.reindex(columns=all_cols, fill_value=0.0)

    y_train = df_train[TARGET_COLUMN].copy()
    y_val = df_val[TARGET_COLUMN].copy()
    y_test = df_test[TARGET_COLUMN].copy()

    split_data = YieldSplitData(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        feature_names=all_cols,
        df_raw=df,
    )

    return split_data, preprocessor


if __name__ == "__main__":
    split_data, preprocessor = create_temporal_splits()
    print("Temporal splits created successfully:")
    print(f"Train shape: {split_data.X_train.shape}, y: {split_data.y_train.shape}")
    print(f"Val shape:   {split_data.X_val.shape}, y: {split_data.y_val.shape}")
    print(f"Test shape:  {split_data.X_test.shape}, y: {split_data.y_test.shape}")
    print(f"Total features: {len(split_data.feature_names)}")
