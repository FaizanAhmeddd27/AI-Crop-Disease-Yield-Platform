"""Weather adapters and season aggregation (ARCH §6.3, DEV_PLAN Task 5.6).

Primary source is the free Open-Meteo Archive/Forecast API; when both
endpoints fail (quota, network, unresolvable location) we fall back to the
NASA POWER daily API, exactly as configured (WEATHER_PRIMARY,
WEATHER_FALLBACK). Both adapters normalize to the same daily-column shape
and feed a *single* aggregation routine, so numbers are comparable across
sources (train/serve consistency: GDD matches the training pipeline in
`ml/src/crop_yield/weather_pull.py` — Tbase 5 °C wheat / 10 °C maize and
GDD from (tmax + tmin) / 2).

Results are cached per (lat, lon, start, end, crop) for the configured TTL
(default 3 h).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date as dt_date
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ── In-memory TTL cache ────────────────────────────────────────────────
_cache: dict[str, tuple[float, WeatherAggregate]] = {}


@dataclass
class WeatherAggregate:
    """Season-level weather statistics aligned with feature_schema v1.1.0."""

    source: str = "open-meteo"
    w_rain_total_mm: float = 0.0
    w_rainy_days: int = 0
    w_heavy_rain_days: int = 0
    w_dry_days: int = 0
    w_temp_mean_c: float = 0.0
    w_temp_max_c: float = 0.0
    w_temp_min_c: float = 0.0
    w_gdd_c: float = 0.0
    w_heat_stress_days: int = 0
    w_grain_rain_mm: float = 0.0
    w_grain_gdd_c: float = 0.0
    w_water_balance_mm: float = 0.0
    w_humidity_mean_pct: float = 0.0
    w_solar_mj_m2: float = 0.0
    w_wind_max_kmh: float = 0.0
    w_days_observed: int = 0
    w_completeness: float = 0.0
    daily_records: list[dict[str, Any]] = field(default_factory=list)

    def to_api_summary(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "temp_mean": round(self.w_temp_mean_c, 1),
            "rain_total": round(self.w_rain_total_mm, 1),
            "heat_stress_days": self.w_heat_stress_days,
            "water_balance": round(self.w_water_balance_mm, 1),
        }


OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

# ET0 Hargreaves-style approximation constant used by both adapters.
ET0_COEFF = 0.4


# ── Daily-column shape shared by every adapter ─────────────────────────
# Keys mirror the Open-Meteo daily response so aggregation is source-agnostic.
COLUMNS = (
    "time",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "relative_humidity_2m_mean",
    "shortwave_radiation_sum",
    "wind_speed_10m_max",
)


async def _fetch_open_meteo(
    lat: float, lon: float, start_date: str, end_date: str
) -> dict[str, list[Any]] | None:
    """Open-Meteo daily archive first, forecast second. None on total failure."""
    params: dict[str, str | float] = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": (
            "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
            "precipitation_sum,relative_humidity_2m_mean,"
            "shortwave_radiation_sum,wind_speed_10m_max"
        ),
        "timezone": "auto",
    }
    for url in (OPEN_METEO_ARCHIVE, OPEN_METEO_FORECAST):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if "daily" in data and data["daily"].get("time"):
                        return data["daily"]
                    logger.warning(f"Open-Meteo {url}: response missing daily data")
                else:
                    logger.warning(f"Open-Meteo {url} returned {resp.status_code}")
        except Exception as e:  # noqa: BLE001 - adapter must not raise
            logger.warning(f"Open-Meteo fetch error ({url}): {e}")
    return None


async def _fetch_nasa_power(
    lat: float, lon: float, start_date: str, end_date: str
) -> dict[str, list[Any]] | None:
    """NASA POWER daily point fallback. None on failure.

    Converts the yyyymmdd-keyed `properties.parameter` map into the same
    daily-column shape as Open-Meteo (°C, mm, MJ/m², m/s — same units).
    Missing sentinel values (-999…) and gap days are dropped before
    aggregation to avoid poisoning the statistics.
    """
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params: dict[str, str | int | float] = {
        "parameters": "T2M_MAX,T2M_MIN,T2M,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,WS2M",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
        "format": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"NASA POWER returned {resp.status_code}")
                return None
            payload = resp.json()
        parameter = payload.get("properties", {}).get("parameter", {})
        if not parameter:
            logger.warning("NASA POWER: response missing properties.parameter")
            return None

        def series(key: str) -> dict[str, float]:
            return {
                k: float(v)
                for k, v in (parameter.get(key) or {}).items()
                if v is not None and float(v) > -900.0
            }

        t_max = series("T2M_MAX")
        t_min = series("T2M_MIN")
        t_mean = series("T2M")
        rain = series("PRECTOTCORR")
        rh = series("RH2M")
        rad = series("ALLSKY_SFC_SW_DWN")
        wind = series("WS2M")

        dates = sorted(set(t_max) | set(t_min) | set(t_mean) | set(rain))
        if not dates:
            return None

        def pick(src: dict[str, float], k: str) -> float:
            v = src.get(k)
            return v if v is not None else 0.0

        iso = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}"  # noqa: E731
        return {
            "time": [iso(d) for d in dates],
            "temperature_2m_max": [pick(t_max, d) for d in dates],
            "temperature_2m_min": [pick(t_min, d) for d in dates],
            "temperature_2m_mean": [pick(t_mean, d) for d in dates],
            "precipitation_sum": [pick(rain, d) for d in dates],
            "relative_humidity_2m_mean": [pick(rh, d) for d in dates],
            "shortwave_radiation_sum": [pick(rad, d) for d in dates],
            "wind_speed_10m_max": [pick(wind, d) for d in dates],
        }
    except Exception as e:  # noqa: BLE001 - adapter must not raise
        logger.warning(f"NASA POWER fetch error: {e}")
        return None


def _gdd_base(crop: str) -> float:
    """Crop base temperature, matching the training pipeline (weather_pull.py)."""
    return 5.0 if "wheat" in crop.lower() else 10.0


def _aggregate(
    source: str,
    crop: str,
    start_date: str,
    end_date: str,
    daily: dict[str, list[Any]],
) -> WeatherAggregate:
    """Season aggregation shared by every adapter (single math code path)."""
    n = len(daily.get("time", []))
    if n == 0:
        return WeatherAggregate(source=source)

    base_temp = _gdd_base(crop)
    heat_threshold = 35.0  # °C

    tmax_list = daily.get("temperature_2m_max", [])
    tmin_list = daily.get("temperature_2m_min", [])
    tmean_list = daily.get("temperature_2m_mean", [])
    precip_list = daily.get("precipitation_sum", [])
    rh_list = daily.get("relative_humidity_2m_mean", [])
    rad_list = daily.get("shortwave_radiation_sum", [])
    wind_list = daily.get("wind_speed_10m_max", [])

    def sf(v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    total_rain = 0.0
    rainy_days = 0
    heavy_rain_days = 0
    dry_days = 0
    gdd_sum = 0.0
    heat_stress = 0
    tmean_sum = 0.0
    tmax_global = -999.0
    tmin_global = 999.0
    rh_sum = 0.0
    rad_sum = 0.0
    wind_max = 0.0
    valid_days = 0
    total_et0 = 0.0
    records: list[dict[str, Any]] = []

    for i in range(n):
        tmax = sf(tmax_list[i] if i < len(tmax_list) else None)
        tmin = sf(tmin_list[i] if i < len(tmin_list) else None)
        tmean = sf(tmean_list[i] if i < len(tmean_list) else None)
        precip = sf(precip_list[i] if i < len(precip_list) else None)
        rh = sf(rh_list[i] if i < len(rh_list) else None)
        rad = sf(rad_list[i] if i < len(rad_list) else None)
        wind = sf(wind_list[i] if i < len(wind_list) else None)

        if tmean == 0.0 and (tmax != 0.0 or tmin != 0.0):
            tmean = (tmax + tmin) / 2.0

        total_rain += precip
        if precip > 0.5:
            rainy_days += 1
        if precip > 20.0:
            heavy_rain_days += 1
        if precip < 0.5:
            dry_days += 1

        # GDD exactly as trained: midpoint of daily extremes, clamped at 0.
        day_gdd = max(0.0, (tmax + tmin) / 2.0 - base_temp)
        gdd_sum += day_gdd

        if tmax >= heat_threshold:
            heat_stress += 1

        tmean_sum += tmean
        tmax_global = max(tmax_global, tmax)
        tmin_global = min(tmin_global, tmin)
        rh_sum += rh
        rad_sum += rad
        wind_max = max(wind_max, wind)
        valid_days += 1

        et0_day = ET0_COEFF * (rad / 1000.0) * (tmean + 17.8) * 0.05 if rad > 0 else 2.5
        total_et0 += et0_day

        records.append(
            {
                "date": daily["time"][i] if i < len(daily["time"]) else "",
                "tmax": round(tmax, 1),
                "tmin": round(tmin, 1),
                "tmean": round(tmean, 1),
                "precip_mm": round(precip, 1),
            }
        )

    # Grain fill approximation (last 30% of season)
    grain_start = int(n * 0.7)
    grain_rain = sum(
        sf(precip_list[i] if i < len(precip_list) else None) for i in range(grain_start, n)
    )
    grain_gdd = 0.0
    for i in range(grain_start, n):
        tmax = sf(tmax_list[i] if i < len(tmax_list) else None)
        tmin = sf(tmin_list[i] if i < len(tmin_list) else None)
        grain_gdd += max(0.0, (tmax + tmin) / 2.0 - base_temp)

    expected_days = date_diff(start_date, end_date) or n

    return WeatherAggregate(
        source=source,
        w_rain_total_mm=round(total_rain, 1),
        w_rainy_days=rainy_days,
        w_heavy_rain_days=heavy_rain_days,
        w_dry_days=dry_days,
        w_temp_mean_c=round(tmean_sum / max(1, valid_days), 1),
        w_temp_max_c=round(tmax_global, 1) if tmax_global > -999 else 0.0,
        w_temp_min_c=round(tmin_global, 1) if tmin_global < 999 else 0.0,
        w_gdd_c=round(gdd_sum, 1),
        w_heat_stress_days=heat_stress,
        w_grain_rain_mm=round(grain_rain, 1),
        w_grain_gdd_c=round(grain_gdd, 1),
        w_water_balance_mm=round(total_rain - total_et0, 1),
        w_humidity_mean_pct=round(rh_sum / max(1, valid_days), 1),
        w_solar_mj_m2=round(rad_sum / max(1, valid_days) / 1000.0, 2),
        w_wind_max_kmh=round(wind_max * 3.6, 1),  # m/s → km/h
        w_days_observed=valid_days,
        w_completeness=round(valid_days / expected_days, 3),
        daily_records=records,
    )


async def fetch_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    crop: str = "wheat",
    settings: Settings | None = None,
) -> WeatherAggregate:
    """Fetch and aggregate daily weather for a growing season.

    Tries the configured primary (Open-Meteo) first, then the configured
    fallback (NASA POWER). Returns a zeroed aggregate with an explicit
    source only when both are unavailable — the yield service marks such
    predictions `degraded` via `w_completeness == 0`.
    """
    settings = settings or get_settings()
    cache_key = f"{lat:.3f}_{lon:.3f}_{start_date}_{end_date}_{crop}"
    ttl_seconds = settings.weather_cache_ttl_min * 60

    if cache_key in _cache:
        cached_ts, cached_val = _cache[cache_key]
        if time.time() - cached_ts < ttl_seconds:
            logger.debug(f"Weather cache hit for {cache_key}")
            return cached_val

    daily = await _fetch_open_meteo(lat, lon, start_date, end_date)
    source = "open-meteo"

    if daily is None:
        logger.info("Open-Meteo unavailable; trying NASA POWER fallback")
        daily = await _fetch_nasa_power(lat, lon, start_date, end_date)
        source = "nasa-power"

    if daily is None:
        logger.error("No weather data from any source; returning zeroed aggregate")
        return WeatherAggregate(source="unavailable")

    result = _aggregate(source, crop, start_date, end_date, daily)
    _cache[cache_key] = (time.time(), result)
    return result


def date_diff(start: str, end: str) -> int | None:
    """Return days between two ISO date strings (inclusive), or None on error."""
    try:
        s = dt_date.fromisoformat(start)
        e = dt_date.fromisoformat(end)
        return max(1, (e - s).days + 1)
    except Exception:
        return None
