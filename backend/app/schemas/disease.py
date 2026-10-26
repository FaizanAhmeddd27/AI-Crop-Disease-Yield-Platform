"""Pydantic schemas for Disease Detection endpoints (ARCH §7.2, SRS §3.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TopKPrediction(BaseModel):
    class_id: str
    confidence: float


class PredictionDetails(BaseModel):
    class_id: str
    crop: str
    disease: str
    is_healthy: bool
    confidence: float
    top_k: list[TopKPrediction] = Field(default_factory=list)


class SeverityDetails(BaseModel):
    level: Literal["low", "moderate", "severe", "unknown"]
    ratio: float
    method: str = "lesion_area_ratio"
    note: str = "Estimated"


class ExplanationDetails(BaseModel):
    method: Literal["grad-cam"] = "grad-cam"
    overlay_url: str
    original_url: str
    # Saliency sanity (AC-9): empty unless activation mass is mostly off-leaf.
    quality_warnings: list[str] = Field(default_factory=list)
    leaf_focus_fraction: float | None = None


class RecommendationAction(BaseModel):
    type: Literal["cultural", "chemical", "biological", "prevention"]
    text: str


class SourceReference(BaseModel):
    title: str
    url: str


class RecommendationsDetails(BaseModel):
    summary: str
    actions: list[RecommendationAction] = Field(default_factory=list)
    prevention: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    disclaimer: str = "Decision support only. Consult a local agronomist."


class ModelVersionInfo(BaseModel):
    name: str
    version: str


class DiseasePredictResponse(BaseModel):
    prediction_id: str
    status: Literal["ok", "uncertain", "not_a_leaf"]
    prediction: PredictionDetails
    severity: SeverityDetails
    explanation: ExplanationDetails
    recommendations: RecommendationsDetails
    model: ModelVersionInfo
    latency_ms: float


class DiseaseClassItem(BaseModel):
    class_id: str
    crop: str
    disease_name: str
    is_healthy: bool


class DiseaseClassesResponse(BaseModel):
    total_classes: int
    classes: list[DiseaseClassItem]
