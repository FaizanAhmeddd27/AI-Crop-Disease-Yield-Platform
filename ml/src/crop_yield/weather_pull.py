"""Historical weather retrieval and seasonal aggregation for Punjab districts via Open-Meteo.

Features:
- Queries the Open-Meteo Historical Archive API (ERA5 reanalysis, 1940-present).
- Automatically caches raw daily JSON files under `ml/data/raw/weather/` (or paths.resolve_data_root()).
- Computes agronomically verified seasonal aggregates (per ADR-0013 and DEV_PLAN Task 1.8):
  - Total cumulative precipitation (mm) and count of rainy days (>= 1.0mm).
  - Growing Degree Days (GDD) with crop-specific base temperatures:
    - Wheat: 5.0°C base temperature.
    - Maize: 10.0°C base temperature.
  - Terminal Heat Stress: Days with Tmax >= 35°C during March-April grain filling (for Wheat).
  - Temperature extremes (mean, max, min) and average humidity.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd
import requests

try:
    from .punjab_districts import PUNJAB_DISTRICTS, get_district_info, normalize_district_name
except ImportError:
    from src.crop_yield.punjab_districts import (
        PUNJAB_DISTRICTS,
        get_district_info,
        normalize_district_name,
    )

try:
    from src.common.paths import resolve_data_root
except ImportError:
    def resolve_data_root() -> Path:
        return Path(__file__).resolve().parents[2] / "data"

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def get_weather_cache_dir() -> Path:
    """Resolve cache directory for raw weather JSON payloads."""
    cache_dir = resolve_data_root() / "raw" / "weather"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def fetch_daily_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    cache_file: Optional[Path] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Fetch daily historical weather from Open-Meteo Archive API with bounded retries."""
    if cache_file and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "daily" in data and "time" in data["daily"]:
                    return data
        except Exception:
            pass  # Re-fetch if cache file is invalid or corrupted

    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start_date,
        "end_date": end_date,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "rain_sum",
            "relative_humidity_2m_mean",
            "shortwave_radiation_sum",
            "wind_speed_10m_max",
        ],
        "timezone": "Asia/Karachi",
    }

    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if cache_file:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            return payload
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))

    raise RuntimeError(
        f"Failed to fetch Open-Meteo weather for ({lat}, {lon}) from {start_date} to {end_date}: {last_error}"
    )


def calculate_seasonal_weather_features(
    district_name: str,
    crop: str,
    season_year: int,
    custom_dates: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    """Calculate aggregated seasonal weather features for a district and harvest year.

    Growth Season Windows (ADR-0013):
    - Wheat (Rabi):
        Sowing ~ Nov 1 (prior year) to Harvest ~ Apr 30 (harvest year).
        Tbase = 5.0°C.
        Grain filling / terminal heat window: Mar 1 to Apr 30.
    - Autumn Maize (Kharif):
        Sowing ~ Jul 15 to Harvest ~ Nov 15.
        Tbase = 10.0°C.
        Grain filling window: Sep 15 to Oct 31.
    """
    dist_info = get_district_info(district_name)
    crop_lower = crop.lower().strip()

    if custom_dates:
        start_date, end_date = custom_dates
        t_base = 5.0 if "wheat" in crop_lower else 10.0
        grain_fill_start = start_date
    elif "wheat" in crop_lower:
        start_date = f"{season_year - 1}-11-01"
        end_date = f"{season_year}-04-30"
        t_base = 5.0
        grain_fill_start = f"{season_year}-03-01"
    elif "maize" in crop_lower or "corn" in crop_lower:
        # Autumn (Kharif) Maize per ADR-0013
        start_date = f"{season_year}-07-15"
        end_date = f"{season_year}-11-15"
        t_base = 10.0
        grain_fill_start = f"{season_year}-09-15"
    else:
        raise ValueError(f"Unsupported crop for weather features: '{crop}'. Expected 'wheat' or 'maize'.")

    cache_dir = get_weather_cache_dir()
    slug_dist = dist_info.name.lower().replace(" ", "_").replace(".", "")
    cache_file = cache_dir / f"{slug_dist}_{crop_lower}_{season_year}.json"

    raw_payload = fetch_daily_weather(
        lat=dist_info.lat,
        lon=dist_info.lon,
        start_date=start_date,
        end_date=end_date,
        cache_file=cache_file,
    )

    daily = raw_payload.get("daily", {})
    if not daily or "time" not in daily:
        raise ValueError(f"Empty or invalid weather response received for {dist_info.name} ({season_year})")

    df = pd.DataFrame(daily)
    df["time"] = pd.to_datetime(df["time"])

    # Extract series with safe fallbacks
    t_mean = df["temperature_2m_mean"].dropna()
    t_max = df["temperature_2m_max"].dropna()
    t_min = df["temperature_2m_min"].dropna()
    precip = df["precipitation_sum"].fillna(0.0)
    humidity = df.get("relative_humidity_2m_mean", pd.Series(dtype=float)).dropna()
    radiation = df.get("shortwave_radiation_sum", pd.Series(dtype=float)).dropna()

    # Growing Degree Days (GDD)
    daily_gdd = np.maximum(0.0, ((t_max + t_min) / 2.0) - t_base)
    total_gdd = float(daily_gdd.sum())

    # Terminal Heat Stress during grain filling window
    grain_fill_mask = df["time"] >= grain_fill_start
    heat_threshold = 35.0 if "wheat" in crop_lower else 38.0
    terminal_heat_days = int((df.loc[grain_fill_mask, "temperature_2m_max"] >= heat_threshold).sum())

    return {
        "district": dist_info.name,
        "crop": crop_lower,
        "season_year": season_year,
        "start_date": start_date,
        "end_date": end_date,
        "rain_total_mm": round(float(precip.sum()), 2),
        "rainy_days_count": int((precip >= 1.0).sum()),
        "temp_mean_c": round(float(t_mean.mean()), 2),
        "temp_max_c": round(float(t_max.max()), 2),
        "temp_min_c": round(float(t_min.min()), 2),
        "gdd_c": round(total_gdd, 2),
        "heat_stress_days_grain_fill": terminal_heat_days,
        "radiation_sum_mj": round(float(radiation.sum()), 2) if not radiation.empty else None,
        "humidity_mean_pct": round(float(humidity.mean()), 2) if not humidity.empty else None,
        "is_barani": dist_info.is_primarily_barani,
    }


if __name__ == "__main__":
    print("Testing Open-Meteo historical fetch for Faisalabad (Wheat 2023)...")
    result = calculate_seasonal_weather_features("Faisalabad", "wheat", 2023)
    print(json.dumps(result, indent=2))
    print("Weather pull test completed successfully.")
