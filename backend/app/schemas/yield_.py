"""Pydantic schemas for Crop Yield Prediction endpoints (ARCH §7.2, SRS §3.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LocationInput(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    district: str | None = None
    region: str | None = None


class SeasonInput(BaseModel):
    year: int = Field(ge=2000, le=2050)
    sowing_date: str | None = None
    harvest_date: str | None = None


class SoilInput(BaseModel):
    ph: float | None = Field(default=None, ge=3.0, le=11.0)
    organic_carbon: float | None = Field(default=None, ge=0.0, le=10.0)
    texture: str | None = None


class YieldPredictRequest(BaseModel):
    crop: str = Field(description="'wheat' or 'maize'")
    location: LocationInput
    season: SeasonInput
    area_ha: float = Field(gt=0.0, description="Farm or district area in hectares")
    soil: SoilInput | None = None
    weather_override: dict[str, Any] | None = None


class PredictionInterval(BaseModel):
    lower: float
    upper: float
    level: float = 0.8


class YieldPredictionDetails(BaseModel):
    yield_value: float
    unit: str = "t/ha"
    interval: PredictionInterval


class RiskDetails(BaseModel):
    level: Literal["low", "medium", "high"]
    baseline_yield: float
    ratio_to_baseline: float
    rationale: str
    advisories: list[str] = Field(default_factory=list)


class SHAPContribution(BaseModel):
    feature: str
    value: float
    shap: float
    direction: Literal["increase", "decrease", "neutral"]
    text: str


class SHAPExplanationDetails(BaseModel):
    method: Literal["shap"] = "shap"
    base_value: float
    contributions: list[SHAPContribution] = Field(default_factory=list)


class WeatherSummaryDetails(BaseModel):
    source: str = "open-meteo"
    temp_mean: float
    rain_total: float
    heat_stress_days: int = 0
    water_balance: float = 0.0


class ModelMetaInfo(BaseModel):
    name: str
    version: str


class YieldPredictResponse(BaseModel):
    prediction_id: str
    status: Literal["ok", "degraded", "out_of_bounds"]
    prediction: YieldPredictionDetails
    risk: RiskDetails
    explanation: SHAPExplanationDetails
    weather_summary: WeatherSummaryDetails
    model: ModelMetaInfo
    latency_ms: float


class DistrictOption(BaseModel):
    name: str
    lat: float
    lon: float
    zone: str
    is_barani: bool
    supported_crops: list[str]


class YieldOptionsResponse(BaseModel):
    districts: list[DistrictOption]
    supported_crops: list[str]
    default_year: int
    target_unit: str = "t/ha"
