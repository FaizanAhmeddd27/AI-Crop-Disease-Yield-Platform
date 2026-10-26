"""Pydantic schemas for Weather endpoints (ARCH §7.2, SRS §3.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeatherQueryParams(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    start_date: str
    end_date: str
    crop: str | None = "wheat"


class DailyWeatherMetric(BaseModel):
    date: str
    tmax: float
    tmin: float
    tmean: float
    precip_mm: float


class WeatherQueryResponse(BaseModel):
    provider: str
    lat: float
    lon: float
    start_date: str
    end_date: str
    total_rain_mm: float
    rainy_days_count: int
    mean_temp_c: float
    max_temp_c: float
    min_temp_c: float
    gdd_c: float
    heat_stress_days: int
    water_balance_mm: float
    daily_records_count: int
