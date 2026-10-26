# ADR-0013: Crops and Geography for Yield Prediction (Punjab, Pakistan: Wheat & Autumn Maize)

- **Status:** Accepted, pending data-availability check
- **Date:** 25 Oct 2026
- **Deciders:** project owner
- **Affects:** PRD §15 (Q1), ARCH §5.1, §6.3, SRS §3.4 (FR-Y), DEV_PLAN Phase 1 (Task 1.7, Deliverables), Phase 3 (Yield Modelling), and `ml/src/crop_yield/`

---

## 1. Context

PRD Decision Q1 requires fixing the **crops and geography** for the crop yield prediction pipeline. The choice dictates:
1. Historical agricultural production statistics (yield per unit area over time).
2. Geographic coordinates for pulling historical weather time-series via the Open-Meteo Historical Archive API.
3. The degree of overlap between the disease detection pipeline (PlantVillage classes) and the yield pipeline in the final unified dashboard.

PlantVillage includes `Corn_(maize)` as one of its primary supported crops, and wheat is the central staple crop modeled throughout the PRD and SRS wireframes.

---

## 2. Decision

We select **Punjab, Pakistan** as the geographic region, and **Wheat** and **Autumn (Kharif) Maize** as the target crops, spanning **18 crop seasons: 2007–08 through 2024–25**.

### Key Scope Specifications:

1. **Geography & Spatial Granularity:**
   - Province: **Punjab, Pakistan** (~36 administrative districts).
   - Spatial unit: **District-level** aggregation.
   - **Boundary Consolidation & Historical Consistency:**
     - In 2022, several new districts were carved out of older parent districts: **Murree** (from Rawalpindi), **Talagang** (from Chakwal), **Taunsa** (from Dera Ghazi Khan), **Kot Addu** (from Muzaffargarh), and **Wazirabad** (from Gujranwala). These are consolidated back into their respective parent districts.
     - **Chiniot** was created as a separate district in February 2009 (split from Jhang). For the 2007–08 and 2008–09 seasons, Chiniot was reported as a tehsil under Jhang. During data cleaning, Jhang and Chiniot are merged for those two seasons (or disaggregated if tehsil breakdown is present) to preserve a continuous 18-season timeline.

2. **Crops & Growing Cycles:**
   - **Wheat (Gandum):** Rabi crop (sowing: October–December; harvest: April–May). Pakistan's primary food staple.
   - **Maize (Makki):** We prioritize **Autumn (Kharif) Maize** (sowing: July–August; harvest: October–November) because it has the longer, more complete historical record across Punjab districts. If Spring Maize records are also sufficiently complete, it may be evaluated as a separate crop-season; otherwise Autumn Maize is the primary series. Maize directly overlaps the PlantVillage `Corn_(maize)` disease classes.

3. **Irrigation Disaggregation:**
   - For **Wheat**, official reports demonstrate that canal-fed land accounts for ~89% of area (e.g., 2020–21 wheat report: ~6,000 thousand acres irrigated vs ~750 thousand un-irrigated). Northern districts (**Attock, Chakwal, Jhelum, Rawalpindi**) are predominantly rainfed (**Barani**), where precipitation has a strong positive correlation with yield.
   - For **Maize**, the irrigation breakdown will be extracted directly from official maize tables rather than assumed.
   - The model feature will be continuous `irrigated_pct` derived directly from CRS area columns (irrigated area / total area), rather than an ad-hoc categorical label.

4. **Unit Harmonization:**
   - Official Pakistani government tables report yield in **maund per acre** (1 maund = 40 kg; 1 acre = 0.404686 hectares).
   - Conversion formulas:
     - maund/acre * 98.842 = kg/ha
     - maund/acre * 0.098842 = t/ha
   - Standard internal and API unit: Metric tonnes per hectare (**t/ha**).

5. **Target Definition & Temporal Splits:**
   - **Target Variable:** `yield_tha` (yield in metric tonnes per hectare per district per crop season).
   - **Splits (per ADR-0010):** Random shuffling is forbidden due to temporal leakage. We enforce strict time-based splits:
     - Train: Seasons 2007–08 to 2020–21 (14 seasons, ~500 rows per crop).
     - Validation: Season 2021–22 (1 season, ~36 rows per crop).
     - Test: Seasons 2022–23 and 2023–24 (2 seasons, ~72 rows per crop).

6. **Weather Retrieval:**
   - Daily weather series are pulled from the **Open-Meteo Historical Weather API** using district reference coordinates.

---

## 3. Data Sources & Provenance

1. **Official Agricultural Statistics:**
   - Directorate of Agriculture, Crop Reporting Service (CRS), Government of Punjab (e.g., annual *Crop Statistics of Punjab* publications).
   - Open Data Pakistan (`opendata.com.pk`).
   - Nature of data: Official survey-based estimates conducted at village/crop-cutting levels.
2. **Weather Series:**
   - Open-Meteo Historical Archive API (ERA5 / ECMWF reanalysis and station observations, 1940–present).

---

## 4. Fallback Policy (Pending Data Availability Check)

If parsing and verifying the historical maize PDF tables results in excessive missing district-years:
1. **Fallback 1:** Restrict the yield MVP strictly to **Wheat** (which has clean, multi-decade digital tables).
2. **Fallback 2:** Substitute Maize with **Rice (Basmati/IRRI)** or **Cotton**, both of which possess complete, digitized CRS datasets across Punjab.

---

## 5. Alternatives Considered

| Alternative | Rationale for Rejection |
|---|---|
| **Option A: India District-Level Yields** | Extensive data, but rejected to maintain direct local agronomic relevance to the target users and national context. |
| **Option B: US Midwest County-Level (USDA NASS)** | Gold standard in academic literature, but rejected because massive, capital-intensive, mechanized commodity farming does not reflect smallholder agronomic practices in South Asia. |
| **Option C: FAOSTAT National-Level** | Rejected because country-level aggregation is far too coarse for district- or farm-level decision support. |

---

## 6. Consequences

### Positive:
- **Direct Multi-Pipeline Cohesion:** A farmer diagnosing maize leaf blight or rust in the Disease tool can switch to the Yield tool to forecast expected maize harvest for their district.
- **Realistic Smallholder Context:** Demonstrates AI applied to an agro-ecosystem where climate anomalies (terminal heat stress in March–April during wheat grain-filling, drought in rainfed Barani zones) directly drive yield risk.

### Negative & Mitigations:
- **Small Dataset Volume:** ~36 districts * 18 seasons ≈ 650 rows per crop.
  - *Mitigation:* Follows **ADR-0005** (Tabular models first: Random Forest and XGBoost with shallow trees, depth 3–5). Deep sequence models (LSTM / Transformer) will likely be documented as data-limited, which is an honest and acceptable academic finding.
- **PDF Extraction for Maize:** Older maize tables require PDF table extraction.
  - *Mitigation:* Use `pdfplumber` / `camelot-py` and verify all row sums against published provincial totals before finalizing the processed dataset.

---

## 7. District Headquarters / Reference Coordinates

For Open-Meteo weather integration. Note: Coordinates represent district administrative headquarters; before final model training, coordinates should be cross-verified against cropland centroids (e.g., via GADM / geoBoundaries) for geographically expansive districts such as Dera Ghazi Khan, Rahim Yar Khan, and Bahawalpur.

| District | Latitude | Longitude | Agricultural Region Context |
|---|---|---|---|
| Attock | 33.7660 | 72.3609 | Northern Barani (Rainfed) |
| Bahawalnagar | 29.9987 | 73.2536 | Southern Irrigated |
| Bahawalpur | 29.3956 | 71.6836 | Southern Irrigated |
| Bhakkar | 31.6253 | 71.0657 | Thal Desert / Irrigated |
| Chakwal | 32.9328 | 72.8630 | Northern Barani (Rainfed) |
| Chiniot | 31.7200 | 72.9789 | Central Irrigated (Merged with Jhang for 2007-09) |
| Dera Ghazi Khan | 30.0489 | 70.6455 | South-Western Mixed (Includes Taunsa) |
| Faisalabad | 31.4504 | 73.1350 | Central Mixed Irrigated |
| Gujranwala | 32.1877 | 74.1945 | Rice-Wheat Belt (Includes Wazirabad) |
| Gujrat | 32.5742 | 74.0754 | Northern Mixed |
| Hafizabad | 32.0679 | 73.6854 | Rice-Wheat Belt |
| Jhang | 31.2781 | 72.3317 | Central Irrigated (Includes Chiniot for 2007-09) |
| Jhelum | 32.9425 | 73.7257 | Northern Barani (Rainfed) |
| Kasur | 31.1179 | 74.4461 | Central Mixed Irrigated |
| Khanewal | 30.3017 | 71.9321 | Cotton-Wheat Belt |
| Khushab | 32.2955 | 72.3502 | Thal Mixed |
| Lahore | 31.5204 | 74.3587 | Central Mixed Irrigated |
| Layyah | 30.9613 | 70.9416 | Thal Mixed |
| Lodhran | 29.5405 | 71.6336 | Cotton-Wheat Belt |
| Mandi Bahauddin | 32.5870 | 73.4912 | Rice-Wheat Belt |
| Mianwali | 32.5839 | 71.5370 | Thal Mixed |
| Multan | 30.1575 | 71.5249 | Cotton-Wheat Belt |
| Muzaffargarh | 30.0744 | 71.1847 | South-Western Mixed (Includes Kot Addu) |
| Nankana Sahib | 31.4492 | 73.7124 | Central Mixed Irrigated |
| Narowal | 32.1000 | 74.8730 | Rice-Wheat Belt |
| Okara | 30.8081 | 73.4458 | Central Mixed Irrigated |
| Pakpattan | 30.3410 | 73.3866 | Central Mixed Irrigated |
| Rahim Yar Khan | 28.4212 | 70.2989 | Cotton-Wheat Belt |
| Rajanpur | 29.1035 | 70.3250 | South-Western Mixed |
| Rawalpindi | 33.5651 | 73.0169 | Northern Barani (Includes Murree) |
| Sahiwal | 30.6682 | 73.1114 | Central Mixed Irrigated |
| Sargodha | 32.0836 | 72.6711 | Central Mixed Irrigated |
| Sheikhupura | 31.7131 | 73.9783 | Rice-Wheat Belt |
| Sialkot | 32.4945 | 74.5229 | Rice-Wheat Belt |
| Toba Tek Singh | 30.9743 | 72.4827 | Central Mixed Irrigated |
| Vehari | 30.0419 | 72.3489 | Cotton-Wheat Belt |
