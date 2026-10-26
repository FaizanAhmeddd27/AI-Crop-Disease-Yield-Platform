# Model Card: AgriSense AI Crop Yield Predictor & Risk Engine

| Field | Value |
|---|---|
| Model Name | XGBoost Yield Predictor & Quantile Ensemble |
| Version | `v1.0.0` |
| Pipeline | Crop Yield Prediction & Risk Assessment (Tabular ML) |
| Architecture | Extreme Gradient Boosting (XGBoost) + Quantile Gradient Boosting Ensemble |
| Date | 25 Oct 2026 |
| Maintainers | AgriSense AI ML Engineering Team |
| License | MIT / Academic Open Source |

---

## 1. Model Details
- **Primary Model:** `xgboost.XGBRegressor` (300 trees, `max_depth = 4`, `learning_rate = 0.04`, `subsample = 0.8`, `colsample_bytree = 0.8`, `reg_alpha = 0.1`, `reg_lambda = 1.0`).
- **Uncertainty Model:** `QuantileYieldEnsemble` with 3 quantile regressors ($\alpha = 0.10, 0.50, 0.90$) generating calibrated 80% prediction intervals $[\hat{y}_{10}, \hat{y}_{90}]$.
- **Artifact Formats:**
  - `xgb_yield_model.json` (502 KB)
  - `quantile_yield_ensemble.joblib` (1.06 MB)
  - `feature_schema.json` (version `v1.1.0`)
  - `risk_config.json`
- **Serving Runtime:** CPU-only via Python / NumPy / XGBoost C++ runtime.

---

## 2. Intended Use
- **Primary Use Cases:**
  - District-level seasonal crop yield forecasting ($t/ha$) for **Wheat** (Rabi staple) and **Autumn Maize** (Kharif staple) in Punjab, Pakistan.
  - Multi-horizon pre-harvest yield risk assessment for smallholder farmers, agricultural extension workers, and regional food security planners.
  - Yield deficit warning and early agronomic advisory generation based on weather anomalies (terminal heat stress, water balance, drought).
  - Feature attribution and explanation via SHAP TreeExplainer.
- **Out-of-Scope / Prohibited Uses:**
  - Not designed for single-field precision agriculture without localized micro-climate / soil sensor calibration.
  - Not valid for non-Punjab geographical zones without localized retraining.
  - Not a replacement for official government crop estimation surveys or statutory crop reporting.

---

## 3. Data & Splits
- **Geography & Scope:** 36 consolidated administrative districts of Punjab, Pakistan across 18 crop seasons (2007–08 to 2024–25).
- **Target Variable:** Crop Yield in Metric Tonnes per Hectare ($t/ha$), converted from official Pakistani Maund/Acre ($1\text{ maund/acre} = 0.098842\text{ t/ha}$).
- **Feature Set (40 variables, Schema `v1.1.0`):**
  - Weather aggregates: Seasonal rainfall, rainy days, heavy rain days, dry days, mean/max/min temperature, GDD ($T_{base}=5^\circ\text{C}$ wheat, $10^\circ\text{C}$ maize), terminal heat stress days ($T_{max} \ge 35^\circ\text{C}$), grain filling rainfall, water balance, solar radiation, humidity, wind.
  - Soil attributes: pH, organic carbon (SOC), nitrogen, clay %, sand %, silt %, CEC, bulk density, available water capacity (AWC).
  - Spatial & Historical: Agro-climatic zone, barani status indicator, cultivated area, 1-year lag yield, 3-year rolling mean yield, yield trend.
- **Leakage-Free Temporal Splits (ADR-0010):**
  - Train: Harvest seasons $\le 2021$ (2008 to 2021, 14 seasons, 1,008 observations).
  - Validation: Harvest season 2022 (calibration and early stopping, 72 observations).
  - Test: Harvest seasons 2023–2024 (unseen future evaluations, 144 observations).

---

## 4. Performance Metrics

| Evaluation Set | Metric | Target | Result | Status |
|---|---|---|---|---|
| **Test Set (2023–24)** | Mean Absolute Error (MAE) | $\le 0.35\text{ t/ha}$ | **0.163 t/ha** | Exceeded |
| **Test Set (2023–24)** | Root Mean Squared Error (RMSE) | $\le 0.45\text{ t/ha}$ | **0.258 t/ha** | Exceeded |
| **Test Set (2023–24)** | Coefficient of Determination ($R^2$) | $\ge 0.850$ | **0.971** | Exceeded |
| **Uncertainty (Y-06)** | 80% Prediction Interval Coverage | $80\% \pm 10\%$ | **82.6% (calibrated)** | Met |
| **Inference Latency** | Single-District Prediction (CPU) | $\le 50\text{ ms}$ | **2.1 ms** | Exceeded |
| **Model Size** | Total Export Artifacts | $\le 50\text{ MB}$ | **1.56 MB** | Exceeded |

---

## 5. Risk Engine Architecture

Yield risk is evaluated through a composite formula comparing the forecast $\hat{y}$ and lower confidence bound $\hat{y}_{10}$ against the district's 3-year historical baseline ($y_{\text{base}}$):
$$R_{\text{eff}} = 0.75 \times \left(\frac{\hat{y}}{y_{\text{base}}}\right) + 0.25 \times \left(\frac{\hat{y}_{10}}{y_{\text{base}}}\right)$$

- **LOW RISK (Green):** $R_{\text{eff}} \ge 0.95$ (Yield expected to meet or exceed normal historical levels).
- **MEDIUM RISK (Yellow):** $0.80 \le R_{\text{eff}} < 0.95$ (Moderate yield loss 5%–20%; triggers moisture optimization and pest scouting advisories).
- **HIGH RISK (Red):** $R_{\text{eff}} < 0.80$ (Severe yield drop $>20\%$; triggers emergency afternoon cooling irrigation, foliar sprays, and crop insurance alerts).

---

## 6. Limitations & Ethical Considerations
- **Barani Zone Sensitivity:** Rainfed northern districts (Attock, Chakwal, Jhelum, Rawalpindi) exhibit higher variance due to unpredictable winter rainfall timing.
- **Reporting Discontinuities:** 2022 newly split districts (Murree, Talagang, Taunsa, Kot Addu, Wazirabad) are consolidated back to parent district boundaries to prevent historical panel fragmentation.
- **Decision Support Only:** Yield predictions provide seasonal planning indicators and must be evaluated alongside on-ground extension officer surveys.
