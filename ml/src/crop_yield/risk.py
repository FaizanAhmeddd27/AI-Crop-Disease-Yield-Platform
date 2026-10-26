"""Yield Risk Assessment Engine and Agronomic Advisory Generator.

Fulfills DEV_PLAN Task 3.11 (FR-Y-009).
Evaluates predicted crop yields against historical district baselines, incorporating
prediction interval bounds [p10, p90] to assign Low / Medium / High yield risk categories.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class RiskAssessment:
    """Strongly-typed output of the risk assessment engine."""

    district: str
    crop: str
    predicted_yield_tha: float
    baseline_yield_tha: float
    yield_ratio: float
    risk_level: RiskLevel
    interval_p10_tha: float
    interval_p90_tha: float
    interval_width_tha: float
    summary_message: str
    advisory_recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "district": self.district,
            "crop": self.crop,
            "predicted_yield_tha": round(self.predicted_yield_tha, 3),
            "baseline_yield_tha": round(self.baseline_yield_tha, 3),
            "yield_ratio": round(self.yield_ratio, 4),
            "risk_level": self.risk_level.value,
            "interval_p10_tha": round(self.interval_p10_tha, 3),
            "interval_p90_tha": round(self.interval_p90_tha, 3),
            "interval_width_tha": round(self.interval_width_tha, 3),
            "summary_message": self.summary_message,
            "advisory_recommendations": self.advisory_recommendations,
        }


class YieldRiskEngine:
    """Evaluates crop yield risks and generates actionable farm-level advisories."""

    def __init__(
        self,
        low_risk_ratio_threshold: float = 0.95,
        medium_risk_ratio_threshold: float = 0.80,
        lower_bound_pessimism_weight: float = 0.25,
    ):
        self.low_threshold = low_risk_ratio_threshold
        self.medium_threshold = medium_risk_ratio_threshold
        self.pessimism_weight = lower_bound_pessimism_weight

    def evaluate_risk(
        self,
        predicted_yield: float,
        baseline_yield: float,
        interval_p10: Optional[float] = None,
        interval_p90: Optional[float] = None,
        district: str = "Unknown",
        crop: str = "wheat",
        weather_context: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """Compute yield risk score, risk level, and agronomic guidance."""
        pred = max(0.1, float(predicted_yield))
        base = max(0.1, float(baseline_yield))

        p10 = float(interval_p10) if interval_p10 is not None else round(pred * 0.88, 3)
        p90 = float(interval_p90) if interval_p90 is not None else round(pred * 1.12, 3)
        width = max(0.0, p90 - p10)

        # Base point ratio
        ratio = pred / base

        # Conservative composite ratio incorporating lower bound risk
        effective_ratio = (1.0 - self.pessimism_weight) * ratio + self.pessimism_weight * (p10 / base)

        if effective_ratio >= self.low_threshold:
            level = RiskLevel.LOW
            msg = f"Yield forecast for {crop} in {district} is favorable ({pred:.2f} t/ha vs normal {base:.2f} t/ha)."
        elif effective_ratio >= self.medium_threshold:
            level = RiskLevel.MEDIUM
            msg = f"Moderate yield reduction risk identified for {crop} in {district} (~{((1 - ratio) * 100):.1f}% below baseline)."
        else:
            level = RiskLevel.HIGH
            msg = f"High yield deficit risk detected for {crop} in {district} (~{((1 - ratio) * 100):.1f}% below baseline)."

        advisories = self._generate_advisories(crop, level, weather_context)

        return RiskAssessment(
            district=district,
            crop=crop,
            predicted_yield_tha=pred,
            baseline_yield_tha=base,
            yield_ratio=ratio,
            risk_level=level,
            interval_p10_tha=p10,
            interval_p90_tha=p90,
            interval_width_tha=width,
            summary_message=msg,
            advisory_recommendations=advisories,
        )

    def _generate_advisories(
        self,
        crop: str,
        risk_level: RiskLevel,
        weather_context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Generate tailored agronomic recommendations."""
        recommendations: List[str] = []
        crop_lower = crop.lower()
        ctx = weather_context or {}

        heat_days = ctx.get("w_heat_stress_days", 0)
        water_bal = ctx.get("w_water_balance_mm", 0.0)

        if risk_level == RiskLevel.HIGH:
            if "wheat" in crop_lower:
                recommendations.append("Apply light sprinkler or canal irrigation during afternoon to cool canopy temperature.")
                recommendations.append("Ensure zinc and potassium foliar spray to strengthen heat tolerance during grain filling.")
                recommendations.append("Evaluate crop credit insurance coverage against extreme terminal heat loss.")
            else:  # Maize
                recommendations.append("Prioritize furrow irrigation during critical silking and grain-fill stages.")
                recommendations.append("Monitor field drainage immediately to avoid waterlogging and root rot if heavy rain occurs.")
        elif risk_level == RiskLevel.MEDIUM:
            if "wheat" in crop_lower:
                recommendations.append("Optimize final irrigation 10-14 days before harvest; avoid lodging risks from late high winds.")
                recommendations.append("Apply balanced top-dressing urea before the boot stage to support grain weight.")
            else:
                recommendations.append("Maintain consistent soil moisture throughout tasseling stage.")
                recommendations.append("Scout field weekly for Fall Armyworm and stem borer foliar infestation.")
        else:  # LOW risk
            recommendations.append("Conditions are optimal. Maintain standard nutrient and irrigation schedule.")
            recommendations.append("Plan timely harvesting and post-harvest grain storage to preserve test weight.")

        return recommendations

    def backtest_historical_shocks(
        self,
        df: pd.DataFrame,
        predictions: np.ndarray,
        p10: Optional[np.ndarray] = None,
        p90: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Backtest risk identification sensitivity on known crisis seasons (2010 floods, 2018 drought, 2022 heatwave)."""
        df_eval = df.copy()
        df_eval["pred"] = predictions
        df_eval["p10"] = p10 if p10 is not None else predictions * 0.88
        df_eval["p90"] = p90 if p90 is not None else predictions * 1.12

        # Use roll3 or train mean as baseline
        df_eval["baseline"] = df_eval["yield_roll3_tha"].fillna(df_eval["yield_tha"])

        results = {}
        for year in [2010, 2018, 2022]:
            sub = df_eval[df_eval["season_year"] == year]
            if len(sub) == 0:
                continue

            high_risk_count = 0
            med_risk_count = 0
            low_risk_count = 0

            for _, row in sub.iterrows():
                assessment = self.evaluate_risk(
                    predicted_yield=row["pred"],
                    baseline_yield=row["baseline"],
                    interval_p10=row["p10"],
                    interval_p90=row["p90"],
                    district=row["district"],
                    crop=row["crop"],
                )
                if assessment.risk_level == RiskLevel.HIGH:
                    high_risk_count += 1
                elif assessment.risk_level == RiskLevel.MEDIUM:
                    med_risk_count += 1
                else:
                    low_risk_count += 1

            total = len(sub)
            results[str(year)] = {
                "total_districts_evaluated": total,
                "high_risk_pct": round(high_risk_count / total * 100, 1),
                "medium_risk_pct": round(med_risk_count / total * 100, 1),
                "low_risk_pct": round(low_risk_count / total * 100, 1),
            }

        return results
