"""Feature contract for the Punjab district-level crop-yield models.

This module is the single source of truth for the tabular feature set. It is
imported by :mod:`ml.src.crop_yield.build_dataset` (training matrix assembly)
and by the backend yield service, which is what guarantees that training and
inference cannot drift apart (NFR-M-003).

Units
-----
The target is **tonnes per hectare (t/ha)**. PAS reports area in thousand
hectares (``'000' Hectares``) and production in thousand tonnes (``'000' Tons``),
so ``production_000t / area_000ha`` is already t/ha -- no conversion factor is
applied to official statistics. The maund/acre helpers below exist only so the
UI can *display* legacy figures that farmers quote verbally.

Version history
---------------
v1.0.0
    Maund/acre target, ad-hoc feature list, no season-aware history.
v1.1.0
    Target is official t/ha; features are grouped by provenance (soil, weather,
    history, context) and validated against the produced column contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

FEATURE_SCHEMA_VERSION = "v1.1.0"

#: Columns that identify a panel observation.
KEY_COLUMNS: tuple[str, ...] = ("crop", "season_year", "district")

#: Prediction target, tonnes per hectare.
TARGET_COLUMN = "yield_tha"

#: Reported wheat/maize area, thousand hectares. ``production_000t`` is
#: deliberately *not* a feature: it is the numerator of the target and would
#: leak the label into the model matrix.
AREA_COLUMN = "area_000ha"

# --- provenance groups -------------------------------------------------------

SOIL_FEATURES: tuple[str, ...] = (
    "soil_ph",
    "soil_soc_g_kg",
    "soil_nitrogen_g_kg",
    "soil_clay_pct",
    "soil_sand_pct",
    "soil_silt_pct",
    "soil_cec_cmol_kg",
    "soil_bulk_density_g_cm3",
    "soil_wv10_pct",
    "soil_wv33_pct",
    "soil_wv1500_pct",
    "soil_awc_pct",
)

WEATHER_FEATURES: tuple[str, ...] = (
    "w_rain_total_mm",
    "w_rainy_days",
    "w_heavy_rain_days",
    "w_dry_days",
    "w_temp_mean_c",
    "w_temp_max_c",
    "w_temp_min_c",
    "w_gdd_c",
    "w_heat_stress_days",
    "w_grain_rain_mm",
    "w_grain_gdd_c",
    "w_water_balance_mm",
    "w_humidity_mean_pct",
    "w_solar_mj_m2",
    "w_wind_max_kmh",
    "w_days_observed",
    "w_completeness",
)

#: Yield history, built only from *earlier* seasons of the same crop/district.
HISTORY_FEATURES: tuple[str, ...] = (
    "yield_lag1_tha",
    "yield_roll3_tha",
    "yield_trend_tha_per_year",
)

#: Static or calendar context. ``season_index`` is a deterministic integer year
#: index (season_year - 2008) so that tree models can extrapolate a mild trend
#: without any information from the future.
CONTEXT_FEATURES: tuple[str, ...] = (
    "area_000ha",
    "season_index",
    "is_barani",
)

CATEGORICAL_FEATURES: tuple[str, ...] = (
    "crop",
    "district",
    "district_zone",
)

NUMERICAL_FEATURES: tuple[str, ...] = (
    SOIL_FEATURES + WEATHER_FEATURES + HISTORY_FEATURES + CONTEXT_FEATURES
)

#: Exact model input columns, in a stable order.
ALL_MODEL_FEATURES: tuple[str, ...] = CATEGORICAL_FEATURES + NUMERICAL_FEATURES

#: Features that must never contain a missing value in a training row.
REQUIRED_FEATURES: tuple[str, ...] = CATEGORICAL_FEATURES + CONTEXT_FEATURES + SOIL_FEATURES + WEATHER_FEATURES

# --- physical plausibility bounds used by ``validate_feature_frame`` ---------

FEATURE_BOUNDS: Mapping[str, tuple[float, float]] = {
    TARGET_COLUMN: (0.05, 20.0),
    "area_000ha": (0.0, 20_000.0),
    "season_index": (0, 60),
    "is_barani": (0, 1),
    "soil_ph": (3.0, 10.5),
    "soil_soc_g_kg": (0.0, 120.0),
    "soil_nitrogen_g_kg": (0.0, 12.0),
    "soil_clay_pct": (0.0, 90.0),
    "soil_sand_pct": (0.0, 100.0),
    "soil_silt_pct": (0.0, 100.0),
    "soil_cec_cmol_kg": (0.0, 120.0),
    "soil_bulk_density_g_cm3": (0.3, 2.2),
    "soil_wv10_pct": (0.0, 70.0),
    "soil_wv33_pct": (0.0, 70.0),
    "soil_wv1500_pct": (0.0, 50.0),
    "soil_awc_pct": (0.0, 40.0),
    "w_rain_total_mm": (0.0, 5_000.0),
    "w_rainy_days": (0, 400),
    "w_heavy_rain_days": (0, 200),
    "w_dry_days": (0, 400),
    "w_temp_mean_c": (-15.0, 45.0),
    "w_temp_max_c": (-5.0, 55.0),
    "w_temp_min_c": (-25.0, 40.0),
    "w_gdd_c": (0.0, 8_000.0),
    "w_heat_stress_days": (0, 400),
    "w_grain_rain_mm": (0.0, 2_000.0),
    "w_grain_gdd_c": (0.0, 3_000.0),
    "w_water_balance_mm": (-3_000.0, 5_000.0),
    "w_humidity_mean_pct": (0.0, 100.0),
    "w_solar_mj_m2": (0.0, 40.0),
    "w_wind_max_kmh": (0.0, 250.0),
    "w_days_observed": (0, 400),
    "w_completeness": (0.0, 1.0),
    "yield_lag1_tha": (0.0, 20.0),
    "yield_roll3_tha": (0.0, 20.0),
    "yield_trend_tha_per_year": (-10.0, 10.0),
}

#: First season in the panel (2007-08 Rabi, used to seed the lag only).
PANEL_FIRST_SEASON = 2008

# --- legacy display conversion (not used for the target) ---------------------

#: 1 maund = 40 kg; 1 acre = 0.404686 ha -> 40 / 1000 / 0.404686 t/ha.
MAUND_PER_ACRE_TO_THA: float = 0.098842
THA_TO_MAUND_PER_ACRE: float = 1.0 / MAUND_PER_ACRE_TO_THA


def maund_per_acre_to_tha(maund_per_acre: float) -> float:
    """Convert a legacy maund/acre figure to t/ha for display purposes."""
    return round(float(maund_per_acre) * MAUND_PER_ACRE_TO_THA, 3)


def tha_to_maund_per_acre(tha: float) -> float:
    """Convert t/ha to maund/acre for display in farmer-facing copy."""
    return round(float(tha) * THA_TO_MAUND_PER_ACRE, 2)


# --- feature construction ----------------------------------------------------


@dataclass(frozen=True)
class YieldFeatureVector:
    """Strongly-typed training/inference record (mirrors the backend schema)."""

    district: str
    crop: str
    season_year: int
    district_zone: str
    is_barani: int
    area_000ha: float
    season_index: int
    rain_total_mm: float
    rainy_days: int
    heavy_rain_days: int
    dry_days: int
    temp_mean_c: float
    temp_max_c: float
    temp_min_c: float
    gdd_c: float
    heat_stress_days: int
    grain_rain_mm: float
    grain_gdd_c: float
    water_balance_mm: float
    humidity_mean_pct: float
    solar_mj_m2: float
    wind_max_kmh: float
    days_observed: int
    completeness: float
    soil_ph: float
    soil_soc_g_kg: float
    soil_nitrogen_g_kg: float
    soil_clay_pct: float
    soil_sand_pct: float
    soil_silt_pct: float
    soil_cec_cmol_kg: float
    soil_bulk_density_g_cm3: float
    soil_wv10_pct: float
    soil_wv33_pct: float
    soil_wv1500_pct: float
    soil_awc_pct: float
    yield_lag1_tha: float | None = None
    yield_roll3_tha: float | None = None
    yield_trend_tha_per_year: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Export a row keyed by the canonical model column names."""
        record: dict[str, Any] = {
            "crop": str(self.crop).strip().lower(),
            "season_year": int(self.season_year),
            "district": str(self.district),
            "district_zone": str(self.district_zone),
            "is_barani": int(self.is_barani),
            "area_000ha": round(float(self.area_000ha), 3),
            "season_index": int(self.season_index),
            # weather (renamed from the descriptive Python attributes)
            "w_rain_total_mm": round(float(self.rain_total_mm), 2),
            "w_rainy_days": int(self.rainy_days),
            "w_heavy_rain_days": int(self.heavy_rain_days),
            "w_dry_days": int(self.dry_days),
            "w_temp_mean_c": round(float(self.temp_mean_c), 2),
            "w_temp_max_c": round(float(self.temp_max_c), 2),
            "w_temp_min_c": round(float(self.temp_min_c), 2),
            "w_gdd_c": round(float(self.gdd_c), 2),
            "w_heat_stress_days": int(self.heat_stress_days),
            "w_grain_rain_mm": round(float(self.grain_rain_mm), 2),
            "w_grain_gdd_c": round(float(self.grain_gdd_c), 2),
            "w_water_balance_mm": round(float(self.water_balance_mm), 2),
            "w_humidity_mean_pct": round(float(self.humidity_mean_pct), 2),
            "w_solar_mj_m2": round(float(self.solar_mj_m2), 2),
            "w_wind_max_kmh": round(float(self.wind_max_kmh), 2),
            "w_days_observed": int(self.days_observed),
            "w_completeness": round(float(self.completeness), 4),
            # soil
            "soil_ph": round(float(self.soil_ph), 3),
            "soil_soc_g_kg": round(float(self.soil_soc_g_kg), 3),
            "soil_nitrogen_g_kg": round(float(self.soil_nitrogen_g_kg), 3),
            "soil_clay_pct": round(float(self.soil_clay_pct), 3),
            "soil_sand_pct": round(float(self.soil_sand_pct), 3),
            "soil_silt_pct": round(float(self.soil_silt_pct), 3),
            "soil_cec_cmol_kg": round(float(self.soil_cec_cmol_kg), 3),
            "soil_bulk_density_g_cm3": round(float(self.soil_bulk_density_g_cm3), 4),
            "soil_wv10_pct": round(float(self.soil_wv10_pct), 3),
            "soil_wv33_pct": round(float(self.soil_wv33_pct), 3),
            "soil_wv1500_pct": round(float(self.soil_wv1500_pct), 3),
            "soil_awc_pct": round(float(self.soil_awc_pct), 3),
        }
        for name, value in (
            ("yield_lag1_tha", self.yield_lag1_tha),
            ("yield_roll3_tha", self.yield_roll3_tha),
            ("yield_trend_tha_per_year", self.yield_trend_tha_per_year),
        ):
            if value is None or (isinstance(value, float) and np.isnan(value)):
                record[name] = np.nan
            else:
                record[name] = round(float(value), 4)
        return record


def build_feature_dataframe(feature_list: Iterable[YieldFeatureVector]) -> pd.DataFrame:
    """Build a DataFrame whose columns match :data:`ALL_MODEL_FEATURES` exactly."""
    rows = [vector.to_dict() for vector in feature_list]
    frame = pd.DataFrame(rows, columns=list(KEY_COLUMNS) + list(ALL_MODEL_FEATURES))
    missing = [column for column in ALL_MODEL_FEATURES if column not in frame.columns]
    if missing:  # pragma: no cover - guarded by the constructor above
        raise KeyError(f"Missing model feature columns: {missing}")
    return frame


def add_history_features(
    frame: pd.DataFrame,
    *,
    crop: str,
    season_range: Sequence[int],
    target: str = TARGET_COLUMN,
) -> pd.DataFrame:
    """Attach leakage-free yield-history features for one crop.

    History is indexed on an explicit season grid rather than on row order, so a
    missing season never silently promotes a two-year-old yield to "lag 1". The
    lag for season *s* is the yield of *s - 1*; the rolling mean covers
    *s - 3 .. s - 1*; the trend is an OLS slope over those three points.
    """
    subset = frame.loc[frame["crop"] == crop].copy()
    districts = sorted(subset["district"].unique())
    grid = pd.MultiIndex.from_product(
        [districts, list(season_range)], names=["district", "season_year"]
    )
    subset = (
        subset.set_index(["district", "season_year"])
        .reindex(grid)
        .reset_index()
        .sort_values(["district", "season_year"])
    )

    grouped = subset.groupby("district", sort=False)[target]
    previous = grouped.shift(1)
    subset["yield_lag1_tha"] = previous
    rolling = previous.groupby(subset["district"], sort=False).rolling(3, min_periods=2)
    subset["yield_roll3_tha"] = rolling.mean().reset_index(level=0, drop=True).sort_index()
    subset["yield_trend_tha_per_year"] = (
        rolling.apply(_slope, raw=True).reset_index(level=0, drop=True).sort_index()
    )

    history = subset.loc[:, ["district", "season_year", *HISTORY_FEATURES]]
    result = frame.copy()
    for column in HISTORY_FEATURES:
        result[column] = np.nan
    merged = result.drop(columns=list(HISTORY_FEATURES)).merge(
        history, on=["district", "season_year"], how="left", validate="one_to_one"
    )
    return merged


def _slope(values: np.ndarray) -> float:
    """OLS slope of ``values`` against 0, 1, 2 ... ; NaN when undefined."""
    clean = np.asarray(values, dtype=float)
    mask = ~np.isnan(clean)
    if mask.sum() < 2:
        return np.nan
    x = np.arange(clean.size, dtype=float)[mask]
    y = clean[mask]
    x_centered = x - x.mean()
    denominator = float((x_centered**2).sum())
    if denominator == 0.0:
        return np.nan
    return float((x_centered * (y - y.mean())).sum() / denominator)


def validate_feature_frame(
    frame: pd.DataFrame, *, require_complete: bool = True, strict: bool = True
) -> pd.DataFrame:
    """Validate column presence, dtypes and physical bounds.

    ``require_complete`` enforces non-null values for every feature in
    :data:`REQUIRED_FEATURES`; history features are allowed to be missing on the
    first eligible season. With ``strict=False`` the frame is returned unchanged
    and only the schema check is applied -- used by the EDA notebook.
    """
    missing_columns = [c for c in (*KEY_COLUMNS, *CONTEXT_FEATURES, *SOIL_FEATURES, *WEATHER_FEATURES) if c not in frame.columns]
    if missing_columns:
        raise KeyError(f"Feature frame is missing columns: {missing_columns}")
    if require_complete:
        null_columns = [c for c in REQUIRED_FEATURES if frame[c].isna().any()]
        if null_columns:
            raise ValueError(f"Required features contain nulls: {null_columns}")
    if not strict:
        return frame
    for column, (low, high) in FEATURE_BOUNDS.items():
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        out_of_bounds = values.notna() & ((values < low) | (values > high))
        if out_of_bounds.any():
            examples = frame.loc[out_of_bounds, column].head(3).tolist()
            raise ValueError(
                f"{column} has {int(out_of_bounds.sum())} value(s) outside "
                f"[{low}, {high}]: {examples}"
            )
    return frame


def feature_schema() -> dict[str, Any]:
    """Serialisable description of the contract, written next to the dataset."""
    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "target": TARGET_COLUMN,
        "target_unit": "t/ha",
        "keys": list(KEY_COLUMNS),
        "categorical": list(CATEGORICAL_FEATURES),
        "numerical": list(NUMERICAL_FEATURES),
        "required": list(REQUIRED_FEATURES),
        "history": list(HISTORY_FEATURES),
        "excluded": {
            "production_000t": "numerator of the target; leakage",
            "district_lat": "constant within district; absorbed by district category",
            "district_lon": "constant within district; absorbed by district category",
        },
        "bounds": {k: list(v) for k, v in FEATURE_BOUNDS.items()},
    }
