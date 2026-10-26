# Data Report — AgriSense AI Datasets, Audits & Split Specifications

| Field | Value |
|---|---|
| Document | Phase 1 Data Report & EDA Audit |
| Version | 1.0 |
| Date | 25 Oct 2026 |
| Phase | Phase 1 (Data Acquisition & EDA) |
| Related Docs | `PRD.md`, `ARCH.md`, `SRS.md`, `DEV_PLAN.md`, `ADR-0013` |

---

## 1. Executive Summary

This report formalizes the datasets, exploratory data analyses (EDA), leakage controls, and split strategies for both AI pipelines of the AgriSense AI platform:
1. **Crop Disease Detection Pipeline:** PlantVillage labeled laboratory imagery (~54,303 images, 38 classes) with external real-world benchmarking on PlantDoc (~2,598 images).
2. **Crop Yield Prediction Pipeline:** Punjab, Pakistan district-level historical agricultural statistics (Wheat & Maize, 2007–08 to 2024–25) coupled with Open-Meteo historical daily agro-climate series.

---

## 2. Crop Disease Dataset (PlantVillage)

### 2.1 Inventory & Composition
- **Total Valid Images:** ~54,303 images across 38 crop-condition classes.
- **Crops Represented (14 crops):** Apple, Blueberry, Cherry, Corn (Maize), Grape, Orange, Peach, Bell Pepper, Potato, Raspberry, Soybean, Squash, Strawberry, Tomato.
- **Healthy vs. Diseased Balance:**
  - Healthy Leaves: ~12 classes, ~22.6% of images.
  - Diseased Leaves: ~26 classes, ~77.4% of images.
- **Resolution & Color Space:**
  - Standardized RGB color mode.
  - Modal resolution: $256 \times 256$ pixels.

### 2.2 Imbalance & Leakage Audit
- **Class Imbalance:**
  - Most represented class: `Orange___Haunglongbing_(Citrus_greening)` (~5,507 images).
  - Least represented class: `Potato___healthy` (~152 images).
  - Imbalance Ratio: $\approx 36.2\times$.
  - *Mitigation for Phase 2:* Class weighting, label smoothing, and focal loss during fine-tuning (D-05/D-06).
- **Near-Duplicate Audit (dHash):**
  - Perceptual difference hashing (`dHash`) revealed identical and near-duplicate burst photo sequences.
  - *Leakage Control:* Stratified splitting groups identical/burst photos together into the same split to avoid test leakage.

### 2.3 Split Strategy
- **Stratification:** Stratified by `class_id` with fixed `SEED = 42`.
- **Ratios:**
  - **Train Split (70%):** ~38,015 images.
  - **Validation Split (15%):** ~8,145 images.
  - **Held-Out Test Split (15%):** ~8,143 images.
- **Verification:** All 38 classes are preserved with non-zero counts across all three partitions.

### 2.4 External Field Evaluation Set (PlantDoc)
- To honor requirement `NFR-ML-002`, the **PlantDoc** dataset (~2,598 images captured in real fields with background clutter, varying sunlight, and shadows) will serve as a strictly external evaluation set to measure and report the domain gap honestly.

---

## 3. Crop Yield Dataset (Punjab, Pakistan)

### 3.1 Geographic & Crop Scope (ADR-0013)
- **Region:** **Punjab, Pakistan** (~36 districts).
- **Target Crops:**
  - **Wheat (Gandum):** Rabi season (Nov–April). Pakistan's primary staple.
  - **Autumn Maize (Makki):** Kharif season (July–Nov). Prioritized for complete historical coverage; matches PlantVillage `Corn_(maize)` class.
- **Period:** 2007–08 through 2024–25 (18 crop seasons).
- **Dataset Size:** ~36 districts * 18 seasons ≈ 650 records per crop.
- **Boundary Consolidations:** Murree (-> Rawalpindi), Talagang (-> Chakwal), Taunsa (-> DG Khan), Kot Addu (-> Muzaffargarh), Wazirabad (-> Gujranwala) mapped to parent districts. Chiniot merged with Jhang for 2007-08 and 2008-09.

### 3.2 Unit Conversion Standard
Official Pakistani agricultural records report in **maund per acre** (1 maund = 40 kg; 1 acre = 0.404686 ha).
Conversion: maund/acre * 0.098842 = t/ha (or * 98.842 = kg/ha).
All internal representations, API payloads, and frontend charts strictly use **metric tonnes per hectare (t/ha)**.

### 3.3 Disaggregation: Irrigated vs. Barani (Rainfed)
- For **wheat**, official reports show ~89% of area is canal-irrigated (2020-21 report: ~6,000 thousand acres irrigated vs ~750 thousand un-irrigated).
- The northern districts (**Attock, Chakwal, Jhelum, Rawalpindi**) are predominantly **Barani** (rainfed), where precipitation has a strong positive correlation with yield.
- For **maize**, the irrigation breakdown will be extracted directly from official maize tables during ingestion.
- The model will use the continuous `irrigated_pct` derived directly from CRS area columns (irrigated area / total area).

### 3.4 Open-Meteo Weather Feature Schema
Historical weather is fetched using district reference coordinates (headquarters):
1. `rain_total_mm`: Cumulative precipitation during growth cycle.
2. `rainy_days`: Days with precipitation >= 1.0 mm.
3. `temp_mean_c`, `temp_max_c`, `temp_min_c`: Mean, maximum, and minimum temperatures.
4. `gdd_c`: Growing Degree Days (Tbase = 5°C for wheat, 10°C for maize).
5. `terminal_heat_days`: Count of days with Tmax >= 35°C during March–April (terminal heat stress during wheat grain filling).

### 3.5 Temporal Split Policy (Leakage-Free)
Per ADR-0010, standard random splitting causes temporal look-ahead leakage.
- **Training Set:** Seasons 2007-08 to 2020-21 (14 seasons, ~500 rows per crop).
- **Validation Set:** Season 2021-22 (1 season, ~36 rows per crop, model tuning & risk threshold calibration).
- **Test Set:** Seasons 2022-23 and 2023-24 (2 seasons, ~72 rows per crop, final honest out-of-sample evaluation).

---

## 4. Phase 1 Exit Criteria Checklist

- [x] PlantVillage EDA complete with class distributions and duplicate audits (`01_plantvillage_eda.ipynb`).
- [x] Stratified 70/15/15 splits generated and committed with `data_manifest.json`.
- [x] Scope Decision Q1 locked in `docs/adr/0013-crops-and-geography-for-yield.md` (Punjab, Pakistan: Wheat & Maize).
- [x] District centroids, agro-climatic zones, and alias mapping created (`ml/src/crop_yield/punjab_districts.py`).
- [x] Automated Open-Meteo weather pulling pipeline implemented (`ml/src/crop_yield/weather_pull.py`).
- [x] Yield EDA and temporal split policy structured (`03_yield_eda.ipynb`).
- [x] Phase 1 Data Report finalized (`docs/reports/data_report.md`).
