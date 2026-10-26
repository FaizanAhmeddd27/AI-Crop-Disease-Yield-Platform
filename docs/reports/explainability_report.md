# Phase 4 Explainability & Severity Assessment Report

**AgriSense AI — Milestone M4**  
*Document Version:* 1.0.0  
*Date:* 25 October 2026  
*Status:* Complete (Reviewed against FR-X-001, FR-X-002, FR-X-005, FR-X-010, FR-D-013, AC-9)

---

## 1. Executive Summary

Phase 4 bridges the critical gap between raw model predictions and trusted agricultural decision support. For smallholder farmers and extension officers, an opaque prediction ("Tomato Late Blight: 94%" or "Yield: 2.1 t/ha") is insufficient to justify costly agrochemical spraying or water allocation changes.

We developed, validated, and benchmarked three explainability and diagnostic modules:
1. **Grad-CAM Visual Saliency (`ml/src/disease/gradcam.py`):** Generates spatial heatmaps showing the specific leaf lesions influencing the convolutional vision model.
2. **Automated Foliar Severity Estimator (`ml/src/disease/severity.py`):** Uses dual-space (HSV + Lab) adaptive color segmentation and morphological filtering to calculate the exact percentage of damaged leaf surface and assign standardized agronomic severity bands (**Low**, **Medium**, **High**).
3. **SHAP Yield Feature Attribution (`ml/src/crop_yield/shap_explainer.py`):** Uses `shap.TreeExplainer` on the production XGBoost model to decompose district yield forecasts into additive contributions (e.g., negative drag from terminal heat days vs. positive gain from favorable thermal degree days).

All modules are designed for **stateless, sub-100 ms execution on single-thread CPU containers**, ready for direct integration into the FastAPI backend (Phase 5).

---

## 2. Visual Explainability via Grad-CAM (Tasks 4.1, 4.2, 4.3)

### 2.1 Target Layer Architecture
Grad-CAM computes the gradient of the target class score $y^c$ with respect to the feature activation maps $A$ of the final convolutional layer:
$$\alpha_k^c = \frac{1}{Z} \sum_{i} \sum_{j} \frac{\partial y^c}{\partial A_{i, j}^k}$$
$$L_{\text{Grad-CAM}}^c = \text{ReLU}\left(\sum_k \alpha_k^c A^k\right)$$

- **EfficientNet-B0 (Production Model):** Target layer is `model.features[-1]` (the final 1x1 pointwise convolutional block outputting shape $[1, 1280, 7, 7]$). This layer contains the highest-level semantic disease patterns prior to global average pooling.
- **ResNet-50:** Target layer is `model.layer4[-1]`.
- **Baseline CNN:** Target layer is `model.features[6]`.

### 2.2 Saliency Heatmap & Overlay Rendering
- The raw activation map is normalized to $[0.0, 1.0]$ and bilinearly interpolated back to the original photo dimensions.
- Color mapping utilizes `cv2.COLORMAP_JET` (or Turbo) with a default alpha blend factor of $\alpha = 0.45$:
  $$I_{\text{blended}} = (1 - \alpha) \cdot I_{\text{RGB}} + \alpha \cdot I_{\text{heatmap}}$$
- The module outputs raw normalized numpy arrays, rendered RGB arrays, and compressed PNG bytes for immediate API response streaming.

### 2.3 Saliency Sanity Review & Failure Mode Analysis (AC-9)
A saliency quality gate is implemented end-to-end:

- `GradCAMService.leaf_focus_fraction` (backend) and `GradCAM.sanity_check_leaf_focus` (ml) measure the proportion of activation mass inside the leaf region (central 70% bounding mask when no explicit leaf mask is available; the ml module accepts a real `leaf_mask`).
- The serving pipeline (`backend/app/services/disease_service.py`) emits a **`low_saliency_quality`** entry in `explanation.quality_warnings` when $< 50\%$ of activation mass resides on foliage, instructing the user to retake the photo without fingers or soil in frame. Asserted by `backend/tests/test_explainability.py`.

The qualitative per-disease-group table below summarizes the Kaggle audit across 50 test images; as disclosed in `docs/reports/disease_experiments.md` §7a, the per-run evidence trail for these image-level audits is not committed, so treat the percentages as reported observations rather than auditable artifacts:

| Diagnostic Case | Observed Activation Behavior | Saliency Alignment |
|---|---|---|
| **Early Blight (Concentric spots)** | High intensity focused strictly on target-shaped necrotic rings and surrounding chlorotic yellow halos. | ~94% on leaf tissue (reported) |
| **Common Rust (Pustules)** | Multiple localized peaks matching small raised fungal pustules across the maize blade. | ~92% on leaf tissue (reported) |
| **Bacterial Spot (Pepper/Peach)** | Small angular dark lesions accurately highlighted without bleed onto healthy green lamina. | ~89% on leaf tissue (reported) |
| **Healthy Leaf (Control)** | Diffuse, low-magnitude activation distributed across primary leaf veins; no localized hotspot. | Expected baseline |

#### Documented Failure Modes & Mitigations:
- **Hand / Finger Distraction:** When farmers hold leaves with bare fingers, earlier layers occasionally activate on high-contrast skin boundaries.
  - *Mitigation:* the `low_saliency_quality` warning (verified above).

---

## 3. Automated Foliar Lesion Severity Module (Tasks 4.4, 4.5)

To prescribe appropriate fungicide volumes, agronomists require an objective estimate of lesion burden. Manual visual estimation exhibits high inter-observer variability ($> 25\%$).

### 3.1 Segmentation Methodology
1. **Leaf Surface Segmentation ($M_{\text{leaf}}$):**
   - Combines HSV foliage filters ($H \in [20, 95]$, $S \in [30, 255]$) and olive-brown dried lamina filters ($H \in [10, 25]$).
   - Applies elliptical morphological opening ($5\times 5$) and closing ($11\times 11$) to fill interior leaf fenestrations.
2. **Diseased Lesion Segmentation ($M_{\text{lesion}}$):**
   - Inside $M_{\text{leaf}}$, segments dark necrotic spots ($V < 85$ or $H < 18, S > 60$), chlorotic halos ($H \in [15, 34], S > 90$), and fungal rust pustules ($a^* > 138$ in CIELAB).
   - Eliminates single-pixel noise specks via morphological opening ($3\times 3$).
3. **Severity Ratio:**
   $$\text{Severity Ratio (\%)} = \min\left(100.0, \frac{\text{Pixels}(M_{\text{lesion}})}{\text{Pixels}(M_{\text{leaf}})} \times 100\right)$$

### 3.2 Standardized Agronomic Severity Bands
Per PRD §7.3, severity is categorized into three standardized treatment tiers:

| Severity Band | Damage Ratio | Agronomic Interpretation | Prescribed Management Strategy |
|---|---|---|---|
| **LOW** | $< 10.0\%$ | Early localized infection | Cultural sanitation, selective pruning, protective contact bio-fungicides. |
| **MEDIUM** | $10.0\% - 30.0\%$ | Established moderate spread | Targeted systemic fungicide spray; isolate affected rows. |
| **HIGH** | $\ge 30.0\%$ | Severe necrosis / defoliation danger | Emergency broad-spectrum fungicide treatment; inspect adjacent canopy. |

### 3.3 Agreement & Benchmarking
- Band agreement with expert agricultural annotations was reported at **91.4%** on the (Kaggle-side) annotation set; like the D-run records, that benchmark's per-image evidence is not committed to the repo — treat as reported, not auditable (see `docs/reports/disease_experiments.md` §7a).
- **Local latency verification (26 Oct 2026, backend venv, 224×224, 20 iterations):** p50 = **2.4 ms**, p95 = **4.3 ms** — comfortably inside the "sub-100 ms stateless" budget in §1. The heuristic's reliability caveat (risk item P5 in the dev plan: luminance/hue thresholds) keeps it labelled as a coarse estimate in the API response.

---

## 4. SHAP Feature Attribution for Crop Yield (Task 4.6)

### 4.1 Methodological Protocol
For the production XGBoost model (`xgb_yield_model.json`), we use `shap.TreeExplainer`. TreeExplainer computes exact Shapley values in polynomial time by leveraging the internal tree split structure, ensuring strict efficiency and symmetry axioms:
$$\hat{y} = E[y] + \sum_{j=1}^{M} \phi_j$$

### 4.2 Numerical Additivity Verification
**Re-verified locally on the full untouched test split (144 observations), 26 Oct 2026:**
$$\left|E[y] + \sum_{j} \phi_j - \hat{y}\right|_{\max} = 0.0035\text{ t/ha} \quad (< 0.005\text{ t/ha tolerance})$$
- Maximum additivity error: **0.00349 t/ha** (mean 0.00349 t/ha) — Tree SHAP is exact for the booster; the residual gap is float32 accumulation inside XGBoost's predict.
- Asserted per-row in `backend/tests/test_explainability.py::TestShapAdditivity` (FR-X-009).
- Latency (backend venv, CPU): full split (144 rows) in ≈ 41 ms; single-row `_compute_shap` well under the 3 s interaction budget.

### 4.3 Global Feature Importance Ranking
Real Tree SHAP mean-$|\phi|$ ranking over the 144-row test split (re-computed 26 Oct 2026; replaces earlier unverified values):

| Rank | Feature | Mean $|\phi|$ ($t/ha$) | Impact Nature |
|---|---|---|---|
| **1** | `yield_roll3_tha` (3-year rolling mean) | 0.406 | Primary anchor; establishes district baseline. |
| **2** | `yield_lag1_tha` (prior-year yield) | 0.379 | Autocorrelation dominates history-driven variation. |
| **3** | `area_000ha` (cultivated scale) | 0.121 | Scale factor for district production concentration. |
| **4** | `w_temp_max_c` (season max temperature) | 0.064 | Heat proxy; negative at grain-filling extremes. |
| **5** | `w_dry_days` | 0.061 | Moisture-stress proxy. |
| **6** | `w_gdd_c` (growing degree days) | 0.032 | Thermal accumulation toward optimum. |
| **7** | `yield_trend_tha_per_year` | 0.025 | Slow-per-district yield trend. |
| **8** | `crop_maize` (one-hot) | 0.024 | Crop-level intercept shift. |
| **9** | `is_barani` (rainfed flag) | 0.021 | Separates northern barani from canal plains. |
| **10** | `w_temp_mean_c` | 0.019 | Season-mean temperature. |

*Caveat:* on the synthesized panel, history features dominate global importances (≈0.79 of the top-2); with the conformal-offset finding and the naive-baseline result, the feature-importance picture must be re-audited on real data (Phase 7).

### 4.4 Localized Farmer-Friendly Narratives
Rather than presenting raw mathematical Shapley numbers ($\phi = -0.412$), the explainer generates intuitive natural language bullet points:
- *"Terminal heat stress (18 days $\ge 35^\circ\text{C}$ during grain filling) reduced expected yield by -0.41 t/ha."*
- *"Favorable seasonal soil water balance (+42 mm) boosted expected yield by +0.22 t/ha."*
- *"District 3-year historical baseline yield (3.42 t/ha) anchored the base forecast."*

---

## 5. Milestone M4 Sign-Off

All requirements for Milestone M4 are verified and functional:
- [x] Grad-CAM engine implemented with per-architecture hooks (`ml/src/disease/gradcam.py`).
- [x] Visual heatmap overlay rendering, colormapping, and PNG byte export verified.
- [x] Saliency sanity checks and leaf-focus verification implemented.
- [x] Foliar lesion severity segmentation pipeline implemented (`ml/src/disease/severity.py`).
- [x] Agronomic severity bands (Low, Medium, High) mapped and tested.
- [x] SHAP TreeExplainer integrated for XGBoost yield forecasts (`ml/src/crop_yield/shap_explainer.py`).
- [x] Additivity verified ($<0.01\text{ t/ha}$) and farmer narrative generation tested.
- [x] Milestone M4 report documented in `docs/reports/explainability_report.md`.
