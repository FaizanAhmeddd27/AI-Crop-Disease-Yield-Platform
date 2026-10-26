"""Crop yield prediction service (ARCH §6.2, DEV_PLAN Task 5.7).

Orchestrates:
1. Weather aggregation via Open-Meteo
2. Feature matrix assembly (v1.1.0 schema)
3. XGBoost point prediction
4. Quantile interval (80% PI)
5. Risk engine evaluation
6. SHAP feature attribution
7. DB persistence
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import UnsupportedCropError
from app.db.models import PredictionYield
from app.ml.loader import production_bundle
from app.services.weather_service import WeatherAggregate, fetch_weather

logger = logging.getLogger(__name__)

# ── District metadata for Punjab, Pakistan ──────────────────────────
# Pre-computed centroid coordinates for the 36 consolidated districts used
# in training. `zone` strings are the *exact* training categories from
# ml/src/crop_yield/punjab_districts.py — they must match the one-hot
# column names of the exported XGBoost booster (train/serve parity).

DISTRICTS: dict[str, dict[str, Any]] = {
    "Attock": {"lat": 33.77, "lon": 72.36, "zone": "Northern Barani (Rainfed)", "is_barani": True},
    "Bahawalnagar": {"lat": 29.99, "lon": 73.25, "zone": "Southern Irrigated", "is_barani": False},
    "Bahawalpur": {"lat": 29.39, "lon": 71.68, "zone": "Southern Irrigated", "is_barani": False},
    "Bhakkar": {"lat": 31.63, "lon": 71.07, "zone": "Thal Desert / Irrigated", "is_barani": False},
    "Chakwal": {"lat": 32.93, "lon": 72.86, "zone": "Northern Barani (Rainfed)", "is_barani": True},
    "Chiniot": {
        "lat": 31.72,
        "lon": 72.98,
        "zone": "Central Irrigated (Merged with Jhang 2007-09)",
        "is_barani": False,
    },
    "DG Khan": {
        "lat": 30.05,
        "lon": 70.64,
        "zone": "South-Western Mixed (Includes Taunsa)",
        "is_barani": False,
    },
    "Faisalabad": {
        "lat": 31.42,
        "lon": 73.08,
        "zone": "Central Mixed Irrigated",
        "is_barani": False,
    },
    "Gujranwala": {
        "lat": 32.16,
        "lon": 74.19,
        "zone": "Rice-Wheat Belt (Includes Wazirabad)",
        "is_barani": False,
    },
    "Gujrat": {"lat": 32.57, "lon": 74.08, "zone": "Northern Mixed", "is_barani": False},
    "Hafizabad": {"lat": 32.07, "lon": 73.69, "zone": "Rice-Wheat Belt", "is_barani": False},
    "Jhang": {
        "lat": 31.27,
        "lon": 72.32,
        "zone": "Central Irrigated (Includes Chiniot 2007-09)",
        "is_barani": False,
    },
    "Jhelum": {"lat": 32.94, "lon": 73.73, "zone": "Northern Barani (Rainfed)", "is_barani": True},
    "Kasur": {"lat": 31.12, "lon": 74.45, "zone": "Central Mixed Irrigated", "is_barani": False},
    "Khanewal": {"lat": 30.30, "lon": 71.93, "zone": "Cotton-Wheat Belt", "is_barani": False},
    "Khushab": {"lat": 32.30, "lon": 72.35, "zone": "Thal Mixed", "is_barani": False},
    "Lahore": {"lat": 31.55, "lon": 74.35, "zone": "Central Mixed Irrigated", "is_barani": False},
    "Layyah": {"lat": 30.97, "lon": 70.94, "zone": "Thal Mixed", "is_barani": False},
    "Lodhran": {"lat": 29.54, "lon": 71.63, "zone": "Cotton-Wheat Belt", "is_barani": False},
    "Mandi Bahauddin": {"lat": 32.59, "lon": 73.49, "zone": "Rice-Wheat Belt", "is_barani": False},
    "Mianwali": {"lat": 32.58, "lon": 71.54, "zone": "Thal Mixed", "is_barani": True},
    "Multan": {"lat": 30.20, "lon": 71.45, "zone": "Cotton-Wheat Belt", "is_barani": False},
    "Muzaffargarh": {
        "lat": 30.07,
        "lon": 71.19,
        "zone": "South-Western Mixed (Includes Kot Addu)",
        "is_barani": False,
    },
    "Nankana Sahib": {
        "lat": 31.45,
        "lon": 73.71,
        "zone": "Central Mixed Irrigated",
        "is_barani": False,
    },
    "Narowal": {"lat": 32.10, "lon": 74.88, "zone": "Rice-Wheat Belt", "is_barani": False},
    "Okara": {"lat": 30.81, "lon": 73.45, "zone": "Central Mixed Irrigated", "is_barani": False},
    "Pakpattan": {
        "lat": 30.34,
        "lon": 73.39,
        "zone": "Central Mixed Irrigated",
        "is_barani": False,
    },
    "Rahim Yar Khan": {"lat": 28.42, "lon": 70.30, "zone": "Cotton-Wheat Belt", "is_barani": False},
    "Rajanpur": {"lat": 29.10, "lon": 70.33, "zone": "South-Western Mixed", "is_barani": False},
    "Rawalpindi": {
        "lat": 33.60,
        "lon": 73.05,
        "zone": "Northern Barani (Includes Murree)",
        "is_barani": True,
    },
    "Sahiwal": {"lat": 30.66, "lon": 73.11, "zone": "Central Mixed Irrigated", "is_barani": False},
    "Sargodha": {"lat": 32.08, "lon": 72.67, "zone": "Central Mixed Irrigated", "is_barani": False},
    "Sheikhupura": {"lat": 31.71, "lon": 73.99, "zone": "Rice-Wheat Belt", "is_barani": False},
    "Sialkot": {"lat": 32.50, "lon": 74.53, "zone": "Rice-Wheat Belt", "is_barani": False},
    "TT Singh": {"lat": 30.97, "lon": 72.48, "zone": "Central Mixed Irrigated", "is_barani": False},
    "Vehari": {"lat": 30.04, "lon": 72.35, "zone": "Cotton-Wheat Belt", "is_barani": False},
}

# Default crop seasons (Pakistan agricultural calendar)
CROP_SEASONS = {
    "wheat": {"sowing": "11-01", "harvest": "04-30"},
    "maize": {"sowing": "07-01", "harvest": "11-15"},
}


def _resolve_district(lat: float, lon: float, district_name: str | None = None) -> str:
    """Resolve the nearest Punjab district by name or coordinates."""
    if district_name:
        # Exact or fuzzy match
        for d in DISTRICTS:
            if d.lower() == district_name.lower():
                return d
        # Substring match
        for d in DISTRICTS:
            if district_name.lower() in d.lower() or d.lower() in district_name.lower():
                return d

    # Nearest-neighbor by Euclidean distance
    best_dist = float("inf")
    best_name = "Lahore"
    for name, info in DISTRICTS.items():
        dist = (lat - info["lat"]) ** 2 + (lon - info["lon"]) ** 2
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def _get_season_dates(
    crop: str, year: int, sowing: str | None = None, harvest: str | None = None
) -> tuple:
    """Return (start_date, end_date) ISO strings for the crop season."""
    season = CROP_SEASONS.get(crop.lower(), CROP_SEASONS["wheat"])
    sow_mmdd = sowing or season["sowing"]
    har_mmdd = harvest or season["harvest"]

    start_year = year if crop.lower() == "maize" else year - 1
    start_date = f"{start_year}-{sow_mmdd}"
    end_date = f"{year}-{har_mmdd}"
    return start_date, end_date


# ── Leakage-free history features from the exported training panels ──

_GROUPED_CROP_FALLBACK = {"wheat": 2.8, "maize": 4.2}


def _get_history_features(crop: str, district: str, season_year: int) -> tuple[float, float, float]:
    """(lag1, roll3, trend) from the exported history tables (train-panel data).

    The tables (history_tables.json, generated by
    ml/src/crop_yield/export_history_tables.py) carry per-district yields
    per training-panel season and a per-district OLS trend. For seasons
    outside the panel the values are extrapolated with that trend; when no
    data exists at all, the crop-mean fallback is used.
    """
    tables = production_bundle.history_tables or {}
    crop_key = crop.lower()
    crop_history = tables.get("crops", {}).get(crop_key, {})
    trend_table = tables.get("trend_tha_per_year", {}).get(crop_key, {})

    district_series = crop_history.get(district, {})
    fallback = _GROUPED_CROP_FALLBACK.get(crop_key, 2.8)
    if not district_series:
        return (fallback, fallback, 0.02)

    trend = float(trend_table.get(district, 0.0))

    def value_at(year: int) -> float | None:
        raw = district_series.get(str(year))
        return float(raw["yield_tha"]) if raw else None

    def extrapolated(year: int) -> float:
        known_years = [int(y) for y in district_series if int(y) <= year]
        if not known_years:
            return fallback
        nearest = max(known_years)
        return float(district_series[str(nearest)]["yield_tha"]) + (year - nearest) * trend

    # lag1 = previous season
    lag1 = value_at(season_year - 1)
    if lag1 is None:
        lag1 = extrapolated(season_year - 1)

    # roll3 = mean of the three seasons before the target season
    roll_vals = [value_at(season_year - i) for i in (1, 2, 3)]
    known = [float(v) for v in roll_vals if v is not None]
    roll3 = sum(known) / len(known) if known else extrapolated(season_year - 2)
    return (round(max(0.05, lag1), 4), round(max(0.05, roll3), 4), round(trend, 5))


def _build_feature_row(
    crop: str,
    district: str,
    season_year: int,
    area_ha: float,
    weather: WeatherAggregate,
    schema: dict[str, Any],
    soil_override: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Assemble a single-row feature DataFrame matching the XGBoost model's training schema."""
    info = DISTRICTS.get(district, {"zone": "Central Mixed Irrigated", "is_barani": False})

    # Default soil values (Punjab averages)
    soil = {
        "soil_ph": 7.8,
        "soil_soc_g_kg": 4.5,
        "soil_nitrogen_g_kg": 0.7,
        "soil_clay_pct": 28.0,
        "soil_sand_pct": 42.0,
        "soil_silt_pct": 30.0,
        "soil_cec_cmol_kg": 12.0,
        "soil_bulk_density_g_cm3": 1.45,
        "soil_wv10_pct": 8.0,
        "soil_wv33_pct": 22.0,
        "soil_wv1500_pct": 10.0,
        "soil_awc_pct": 12.0,
    }
    if soil_override:
        if soil_override.get("ph") is not None:
            soil["soil_ph"] = soil_override["ph"]
        if soil_override.get("organic_carbon") is not None:
            soil["soil_soc_g_kg"] = soil_override["organic_carbon"]

    # Leakage-free history features + calendar context exactly as trained
    lag1, roll3, trend_tha = _get_history_features(crop, district, season_year)

    row: dict[str, Any] = {
        "crop": crop.lower(),
        "district": district,
        "district_zone": info["zone"],
        "season_year": season_year,
        "area_000ha": area_ha / 1000.0,
        "season_index": max(0, int(season_year) - 2008),  # ingest.py convention
        "is_barani": 1.0 if info.get("is_barani", False) else 0.0,
        **soil,
        "w_rain_total_mm": weather.w_rain_total_mm,
        "w_rainy_days": weather.w_rainy_days,
        "w_heavy_rain_days": weather.w_heavy_rain_days,
        "w_dry_days": weather.w_dry_days,
        "w_temp_mean_c": weather.w_temp_mean_c,
        "w_temp_max_c": weather.w_temp_max_c,
        "w_temp_min_c": weather.w_temp_min_c,
        "w_gdd_c": weather.w_gdd_c,
        "w_heat_stress_days": weather.w_heat_stress_days,
        "w_grain_rain_mm": weather.w_grain_rain_mm,
        "w_grain_gdd_c": weather.w_grain_gdd_c,
        "w_water_balance_mm": weather.w_water_balance_mm,
        "w_humidity_mean_pct": weather.w_humidity_mean_pct,
        "w_solar_mj_m2": weather.w_solar_mj_m2,
        "w_wind_max_kmh": weather.w_wind_max_kmh,
        "w_days_observed": weather.w_days_observed,
        "w_completeness": weather.w_completeness,
        "yield_lag1_tha": lag1,
        "yield_roll3_tha": roll3,
        "yield_trend_tha_per_year": trend_tha,
    }

    df = pd.DataFrame([row])

    # One-hot encode categorical columns to match training schema
    # The model was trained with one-hot encoded categoricals;
    # expected feature names come directly from the booster below.
    booster = production_bundle.yield_booster
    if booster is not None:
        expected_features = booster.feature_names
        if expected_features:
            # Build one-hot features
            final_row: dict[str, float] = {}
            for feat in expected_features:
                if feat.startswith("crop_"):
                    val_name = feat.replace("crop_", "")
                    final_row[feat] = 1.0 if crop.lower() == val_name.lower() else 0.0
                elif feat.startswith("district_"):
                    val_name = feat.replace("district_", "")
                    final_row[feat] = 1.0 if district == val_name else 0.0
                elif feat.startswith("district_zone_"):
                    val_name = feat.replace("district_zone_", "")
                    final_row[feat] = 1.0 if info["zone"] == val_name else 0.0
                elif feat in row:
                    final_row[feat] = float(row[feat])
                else:
                    final_row[feat] = 0.0

            return pd.DataFrame([final_row])[expected_features]

    return df


# ── Risk assessment (single source: exported risk_config.json, with
#    the same thresholds as ml/src/crop_yield/risk.py) ─────────────────


def _evaluate_risk(
    crop: str,
    predicted_yield: float,
    p10: float,
    p90: float,
    baseline: float,
    district: str,
    risk_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute risk level using the composite effective ratio formula.

    Thresholds and per-crop advisories come from the exported
    `risk_config.json` (ml/artifacts/models/yield/...) so serving stays in
    lockstep with the training-side risk engine.
    """
    cfg = risk_config or {}
    low_threshold = float(cfg.get("low_risk_ratio_threshold", 0.95))
    medium_threshold = float(cfg.get("medium_risk_ratio_threshold", 0.80))
    pessimism_weight = float(cfg.get("lower_bound_pessimism_weight", 0.25))
    advisory_rules: dict[str, dict[str, str]] = cfg.get("advisory_rules", {}) or {}
    crop_rules = advisory_rules.get(crop.lower(), {})

    pred = max(0.1, predicted_yield)
    base = max(0.1, baseline)
    ratio = pred / base
    effective_ratio = (1.0 - pessimism_weight) * ratio + pessimism_weight * (p10 / base)

    if effective_ratio >= low_threshold:
        level = "low"
        msg = f"Yield forecast favorable ({pred:.2f} t/ha vs baseline {base:.2f} t/ha)."
        advisories = [
            crop_rules.get(
                "low_risk",
                "Conditions are optimal. Maintain standard nutrient and irrigation schedule.",
            ),
            "Plan timely harvesting and post-harvest grain storage.",
        ]
    elif effective_ratio >= medium_threshold:
        level = "medium"
        msg = f"Moderate yield reduction risk (~{((1 - ratio) * 100):.1f}% below baseline)."
        advisories = [
            crop_rules.get("medium_risk", "Optimize final irrigation 10-14 days before harvest."),
            "Apply balanced top-dressing urea before boot stage.",
        ]
    else:
        level = "high"
        msg = f"High yield deficit risk (~{((1 - ratio) * 100):.1f}% below baseline)."
        advisories = [
            crop_rules.get(
                "high_risk",
                "Apply irrigation during afternoon to cool canopy temperature.",
            ),
            "Evaluate crop credit insurance coverage.",
        ]

    return {
        "level": level,
        "baseline_yield": round(base, 3),
        "ratio_to_baseline": round(ratio, 4),
        "rationale": msg,
        "advisories": advisories,
    }


# ── SHAP explanation ──────────────────────────────────────────────────


def _compute_shap(
    booster: xgb.Booster, feature_row: pd.DataFrame, top_k: int = 5
) -> dict[str, Any]:
    """Compute SHAP feature attributions using TreeExplainer."""
    try:
        import shap

        explainer = shap.TreeExplainer(booster)
        shap_values = explainer.shap_values(feature_row)[0]
        exp_val = explainer.expected_value
        base_value = float(np.ravel(exp_val)[0]) if hasattr(exp_val, "__iter__") else float(exp_val)

        cols = feature_row.columns.tolist()
        contributions = []
        for name, phi, val in zip(cols, shap_values, feature_row.iloc[0].values, strict=True):
            direction = "increase" if phi > 0.005 else ("decrease" if phi < -0.005 else "neutral")
            label = "boosted" if phi > 0 else "reduced"
            contributions.append(
                {
                    "feature": name,
                    "value": round(float(val), 4),
                    "shap": round(float(phi), 4),
                    "direction": direction,
                    "text": f"{name} ({float(val):.2f}) {label} yield by {float(phi):+.3f} t/ha",
                }
            )
        contributions.sort(key=lambda x: abs(x["shap"]), reverse=True)

        return {
            "method": "shap",
            "base_value": round(base_value, 4),
            "contributions": contributions[:top_k],
        }
    except Exception as e:
        logger.warning(f"SHAP computation failed: {e}")
        return {"method": "shap", "base_value": 0.0, "contributions": []}


# ── Main prediction pipeline ──────────────────────────────────────────


async def predict_yield(
    request_data: dict[str, Any],
    db: Session,
    user_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run full yield prediction pipeline.

    Parameters
    ----------
    request_data : dict
        Validated request body matching YieldPredictRequest schema.
    """
    settings = settings or get_settings()
    t0 = time.perf_counter()
    prediction_id = uuid.uuid4().hex

    bundle = production_bundle
    if not bundle.yield_ready or bundle.yield_booster is None:
        raise RuntimeError("Yield model is not loaded. Check model artifacts.")

    crop = request_data["crop"].lower()
    supported_crops = {"wheat", "maize"}
    if crop not in supported_crops:
        raise UnsupportedCropError(
            f"Unsupported crop '{crop}'.",
            details={"supported_crops": sorted(supported_crops)},
        )
    lat = request_data["location"]["lat"]
    lon = request_data["location"]["lon"]
    year = request_data["season"]["year"]
    area_ha = request_data["area_ha"]
    district_hint = request_data["location"].get("district")
    soil_data = request_data.get("soil")

    district = _resolve_district(lat, lon, district_hint)
    sowing = request_data["season"].get("sowing_date")
    harvest = request_data["season"].get("harvest_date")
    start_date, end_date = _get_season_dates(crop, year, sowing, harvest)

    # 1. Weather
    weather_override = request_data.get("weather_override")
    if weather_override:
        weather = WeatherAggregate(**weather_override)
    else:
        weather = await fetch_weather(lat, lon, start_date, end_date, crop=crop, settings=settings)

    # 2. Feature assembly
    feature_row = _build_feature_row(
        crop=crop,
        district=district,
        season_year=year,
        area_ha=area_ha,
        weather=weather,
        schema=bundle.yield_schema,
        soil_override=(
            {"ph": soil_data.get("ph"), "organic_carbon": soil_data.get("organic_carbon")}
            if soil_data
            else None
        ),
    )

    # 3. XGBoost point prediction
    dmatrix = xgb.DMatrix(feature_row)
    predicted_yield = float(bundle.yield_booster.predict(dmatrix)[0])

    # 4. Quantile interval (split-conformal recalibrated on validation split
    #    during training — see ml/artifacts/models/yield/v0.1.0/calibration.json).
    q_ens = bundle.quantile_ensemble
    conformal_offset = 0.0
    if q_ens and isinstance(q_ens, dict):
        m10 = q_ens.get("p10") or q_ens.get("q10")
        m90 = q_ens.get("p90") or q_ens.get("q90")
        p10 = float(m10.predict(feature_row)[0]) if m10 is not None else predicted_yield * 0.85
        p90 = float(m90.predict(feature_row)[0]) if m90 is not None else predicted_yield * 1.15
        conformal_offset = float(q_ens.get("conformal_offset_tha", 0.0) or 0.0)
    elif q_ens and hasattr(q_ens, "predict_interval"):
        p10_arr, _, p90_arr = q_ens.predict_interval(feature_row)
        p10 = float(p10_arr[0])
        p90 = float(p90_arr[0])
    else:
        p10 = predicted_yield * 0.85
        p90 = predicted_yield * 1.15

    # Symmetric split-conformal widening (guarantees >= 80% coverage)
    if conformal_offset > 0.0:
        p10 = max(0.05, p10 - conformal_offset)
        p90 = p90 + conformal_offset

    # 5. Risk assessment (thresholds/advisories from the exported risk_config)
    baseline_yield = 2.8 if crop == "wheat" else 4.2
    risk = _evaluate_risk(
        crop,
        predicted_yield,
        p10,
        p90,
        baseline_yield,
        district,
        risk_config=bundle.risk_config,
    )

    # 6. SHAP explanation
    explanation = _compute_shap(bundle.yield_booster, feature_row, top_k=5)

    # 7. Status
    district_info = DISTRICTS.get(district)
    if district_info is None:
        status = "out_of_bounds"
    elif weather.w_completeness < 0.5:
        status = "degraded"
    else:
        status = "ok"

    # 8. DB persistence
    try:
        record = PredictionYield(
            id=prediction_id,
            user_id=user_id,
            crop=crop,
            district=district,
            season_year=year,
            area_ha=area_ha,
            predicted_yield_tha=round(predicted_yield, 3),
            interval_lower=round(p10, 3),
            interval_upper=round(p90, 3),
            risk_level=risk["level"],
        )
        db.add(record)
        db.commit()
    except Exception as e:
        logger.warning(f"DB persistence failed: {e}")
        db.rollback()

    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "prediction_id": prediction_id,
        "status": status,
        "prediction": {
            "yield_value": round(predicted_yield, 3),
            "unit": "t/ha",
            "interval": {"lower": round(p10, 3), "upper": round(p90, 3), "level": 0.8},
        },
        "risk": risk,
        "explanation": explanation,
        "weather_summary": weather.to_api_summary(),
        "model": {
            "name": bundle.yield_card.get("primary_model", "XGBoost Yield Predictor"),
            "version": bundle.yield_card.get("version", "v0.1.0"),
        },
        "latency_ms": latency_ms,
    }


def get_yield_options() -> dict[str, Any]:
    """Return the list of supported districts, crops, and defaults."""
    districts = []
    for name, info in sorted(DISTRICTS.items()):
        districts.append(
            {
                "name": name,
                "lat": info["lat"],
                "lon": info["lon"],
                "zone": info["zone"],
                "is_barani": info["is_barani"],
                "supported_crops": ["wheat", "maize"],
            }
        )
    return {
        "districts": districts,
        "supported_crops": ["wheat", "maize"],
        "default_year": 2024,
        "target_unit": "t/ha",
    }
