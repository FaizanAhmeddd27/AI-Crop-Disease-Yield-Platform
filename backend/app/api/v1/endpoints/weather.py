"""Weather data API endpoint (ARCH §7.2, DEV_PLAN Task 5.6).

- GET /weather – Fetch aggregated weather data for a location and date range
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request

from app.schemas.weather import WeatherQueryResponse
from app.services.weather_service import fetch_weather

logger = logging.getLogger(__name__)

router = APIRouter(tags=["weather"])


@router.get(
    "/weather",
    response_model=WeatherQueryResponse,
    summary="Fetch aggregated weather data for a location and date range",
)
async def get_weather(
    request: Request,
    lat: float = Query(ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(ge=-180.0, le=180.0, description="Longitude"),
    start_date: str = Query(description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(description="End date (YYYY-MM-DD)"),
    crop: str = Query(default="wheat", description="Crop type for GDD calculation"),
) -> WeatherQueryResponse:
    """Fetch daily weather from Open-Meteo and return season-level aggregates."""
    settings = request.app.state.settings
    weather = await fetch_weather(lat, lon, start_date, end_date, crop=crop, settings=settings)

    return WeatherQueryResponse(
        provider=weather.source,
        lat=lat,
        lon=lon,
        start_date=start_date,
        end_date=end_date,
        total_rain_mm=weather.w_rain_total_mm,
        rainy_days_count=weather.w_rainy_days,
        mean_temp_c=weather.w_temp_mean_c,
        max_temp_c=weather.w_temp_max_c,
        min_temp_c=weather.w_temp_min_c,
        gdd_c=weather.w_gdd_c,
        heat_stress_days=weather.w_heat_stress_days,
        water_balance_mm=weather.w_water_balance_mm,
        daily_records_count=weather.w_days_observed,
    )
