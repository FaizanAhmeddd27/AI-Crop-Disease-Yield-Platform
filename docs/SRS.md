# SRS — Software Requirements Specification

| Field | Value |
|---|---|
| Document | Software Requirements Specification (IEEE 830 / ISO 29148-inspired) |
| Project | AI-Powered Crop Disease & Yield Prediction Platform ("AgriSense AI") |
| Version | 1.0 (Draft) |
| Date | 24 Oct 2026 |
| Related | `PRD.md` (what & why), `ARCH.md` (how), `DEV_PLAN.md` (when) |

**Requirement keywords:** *shall* = mandatory, *should* = recommended, *may* = optional.
**Priority:** M = Must (MVP), S = Should, C = Could (stretch).
**Verification:** T = Test (automated), D = Demonstration, I = Inspection/Review, A = Analysis/Experiment.

---

## 1. Introduction

### 1.1 Purpose
This SRS specifies the functional, non-functional, data, interface, and quality requirements for an AI-powered web platform that (a) detects crop diseases from leaf images and (b) predicts crop yield from agricultural and environmental data, with explainability for both.

### 1.2 Scope
The system comprises:
1. A **web frontend** (Next.js/React/TypeScript/Tailwind/Recharts).
2. A **backend API** (FastAPI) serving ML models and business logic.
3. **Two ML pipelines**: disease classification (CNN/ViT) and yield prediction (ML/time-series).
4. **Explainability modules**: Grad-CAM and SHAP.
5. **Data layer**: Supabase PostgreSQL and Supabase Storage.
6. **MLOps tooling**: file-based run records, Git/GitHub, Docker, CI/CD; training on Kaggle Notebooks (GPU).

**Out of scope (initial version):** native mobile apps, IoT/drone/satellite ingestion, payments, free-text LLM advice, RAG assistant, agent orchestration, irrigation/fertilizer/crop recommendation, push alerts (all listed as future extensions).

### 1.3 Definitions, Acronyms
| Term | Definition |
|---|---|
| Grad-CAM | Gradient-weighted Class Activation Mapping |
| SHAP | SHapley Additive exPlanations |
| KB | Knowledge Base of curated disease management information |
| Confidence | Calibrated max softmax probability for the predicted class |
| Uncertain | Prediction state when confidence < configured threshold |
| Severity (estimated) | Heuristic band derived from lesion-area ratio |
| Risk level | Low/Medium/High classification of the yield outlook relative to a historical baseline |
| Object storage | Supabase Storage (private buckets, S3-compatible API) |
| RLS | PostgreSQL Row Level Security |

### 1.4 References
- Source project brief: *AI-Powered Crop Disease & Yield Prediction Platform* (PDF, updated tech stack).
- PlantVillage dataset documentation; Open-Meteo and NASA POWER API docs; PyTorch, timm, SHAP, FastAPI, Next.js, Supabase (Postgres, Storage, Auth) documentation.

### 1.5 Document Overview
§2 describes the product context; §3 lists functional requirements; §4 external interfaces; §5 non-functional requirements; §6 data requirements; §7 ML/MLOps requirements; §8 constraints; §9 use cases; §10 acceptance criteria; §11 traceability; §12 appendices.

---

## 2. Overall Description

### 2.1 Product Perspective
A new, self-contained web platform integrating third-party data APIs (Open-Meteo, NASA POWER) and managed services (Supabase). Training occurs offline on Kaggle Notebooks; inference runs online on CPU.

```
User ⇄ Next.js ⇄ FastAPI ⇄ {Disease Model, Yield Model, Grad-CAM, SHAP, KB, Weather} ⇄ {PostgreSQL, Storage}
                                         ▲
                       versioned model artifacts from Kaggle training
```

### 2.2 Product Functions (summary)
| ID | Function |
|---|---|
| PF-1 | Leaf image upload & disease classification with confidence and estimated severity |
| PF-2 | Grad-CAM visual explanation |
| PF-3 | Disease-specific recommended actions from a curated KB |
| PF-4 | Yield prediction from crop/location/farm/weather/soil/history |
| PF-5 | Risk-level determination and SHAP explanation |
| PF-6 | Weather retrieval with provider fallback and caching |
| PF-7 | Combined results dashboard |
| PF-8 | Experiment tracking & model versioning (run records) |
| PF-9 | Optional auth and prediction history |
| PF-10 | Model transparency (model card/about) page |

### 2.3 User Classes
| Class | Description | Privileges |
|---|---|---|
| Anonymous Farmer | Uses disease/yield tools without login | Predict, view own current results |
| Registered Farmer (C) | Logged-in user | + history, saved farms, delete own data |
| Agronomist/Evaluator | Reviews explanations and model info | Same as farmer; uses About/Model pages |
| Developer/ML Engineer | Trains, tracks, promotes models | Access to the training environment, CI/CD, secrets |
| Admin (service role) | Manages KB content and model pointers | Server-side/DB-level only |

### 2.4 Operating Environment
| Component | Environment |
|---|---|
| Client | Modern browsers (latest 2 versions of Chrome, Edge, Firefox, Safari; Android Chrome; iOS Safari); viewport ≥ 360 px |
| Frontend host | Vercel |
| Backend host | Docker container on Render / Hugging Face Spaces / cloud VM (CPU) |
| DB | Supabase PostgreSQL |
| Object storage | Supabase Storage |
| Training | Kaggle Notebooks (GPU) |

### 2.5 Design & Implementation Constraints
- C-1: Languages: Python (ML, backend), TypeScript (frontend).
- C-2: Disease models implemented in PyTorch/Torchvision/timm; yield in Scikit-learn/XGBoost and PyTorch (LSTM/Transformer).
- C-3: Backend shall be FastAPI exposing REST/JSON.
- C-4: Every experiment shall produce a durable, comparable run record (ADR-0012).
- C-5: Must run on CPU-only hosting with limited RAM (target ≤ 2 GB resident memory, goal ≤ 1 GB if free-tier).
- C-6: Public datasets only; respect licences and cite sources.
- C-7: Treatment recommendations shall originate from curated sources, not model generation.

### 2.6 Assumptions & Dependencies
- A-1: PlantVillage (or mirror) remains available; crops/diseases are limited to its classes in MVP.
- A-2: Yield modelling is limited to selected crop(s) and geography determined by data availability (decision Q1 in PRD).
- A-3: Open-Meteo/NASA POWER remain accessible without paid plans for expected volume.
- A-4: Users have internet access and a camera-capable device or image files.
- A-5: Free/low-cost tiers of Vercel, Render/HF and Supabase (Postgres + Storage) are sufficient for demo-scale traffic.

---

## 3. Functional Requirements

### 3.1 Disease Detection (FR-D)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-D-001 | The system shall allow a user to select and upload a single leaf image via file picker. | M | T/D |
| FR-D-002 | The system shall allow image capture directly from a mobile camera where the browser supports it. | S | D |
| FR-D-003 | The frontend shall validate file type (JPEG, PNG, WebP) and size (≤ 10 MB) before upload and show an inline error otherwise. | M | T |
| FR-D-004 | The frontend should compress/resize images client-side (e.g., longest side ≤ 1280 px) before upload. | S | T |
| FR-D-005 | The backend shall re-validate file type (magic bytes), size, and decodability, and reject invalid files with HTTP 415/413/400 and a standard error body. | M | T |
| FR-D-006 | The backend shall strip EXIF/GPS metadata from stored images. | M | T |
| FR-D-007 | The backend shall preprocess images identically to the training pipeline (resize, normalization) using the config shipped with the model artifact. | M | T/I |
| FR-D-008 | The system shall classify the image into one of the supported classes (healthy or a supported disease per crop) using the production disease model. | M | T/A |
| FR-D-009 | The system shall return the predicted class, crop, disease name, `is_healthy` flag, and a confidence score in [0,1]. | M | T |
| FR-D-010 | The system should return the top-3 class probabilities. | S | T |
| FR-D-011 | If confidence < `CONFIDENCE_THRESHOLD` (default 0.60), the system shall return `status="uncertain"` and the UI shall display a "not sure — retake photo" message instead of a definitive diagnosis. | M | T/D |
| FR-D-012 | The system should detect obviously non-leaf images (e.g., via low confidence + entropy heuristic or an optional background/OOD class) and return `status="not_a_leaf"`. | S | T/A |
| FR-D-013 | The system shall return an **estimated severity** level (`none` for healthy; `low`, `moderate`, `severe` otherwise) with the numeric lesion ratio and method label. | M | T/A |
| FR-D-014 | Severity bands shall be configurable without code changes (config file/env). | S | I |
| FR-D-015 | The UI shall label severity as "Estimated" and provide an explanatory tooltip of the method and limitations. | M | I |
| FR-D-016 | The system shall generate a Grad-CAM heatmap for the predicted class and return an overlay image URL (see FR-X). | M | T/D |
| FR-D-017 | The system shall return disease-specific recommended actions from the KB for the predicted class (see FR-K). | M | T |
| FR-D-018 | The system shall persist a prediction record (class, confidence, severity, model version, image keys, timestamps) unless the user opts out or persistence fails (degrade gracefully). | S | T |
| FR-D-019 | The system shall expose the list of supported crops/diseases via `GET /disease/classes`. | M | T |
| FR-D-020 | The system shall include the model name and version in every disease prediction response. | M | T |
| FR-D-021 | An optional `crop_hint` input, if provided and inconsistent with the predicted crop, shall trigger a UI warning (not an override). | C | T |
| FR-D-022 | Disease prediction shall complete in ≤ 3 s p95 server-side on warm CPU (see NFR-P-001). | M | A/T |

### 3.2 Explainability (FR-X)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-X-001 | The system shall compute Grad-CAM for the predicted class using the architecture-appropriate target layer (CNN last conv block; ViT last block with reshape transform). | M | T/I |
| FR-X-002 | The Grad-CAM overlay shall be rendered on the (resized) original image with a colour map and returned as a PNG via a time-limited signed URL. | M | T |
| FR-X-003 | The UI shall display original and overlay side by side (stacked on small screens) with a caption explaining the heatmap. | M | D |
| FR-X-004 | The UI shall state that heatmaps indicate *model attention* and not proof of disease location. | M | I |
| FR-X-005 | The system shall compute SHAP values for every yield prediction using an explainer appropriate to the model type (Tree/Linear/Gradient/Kernel). | M | T/I |
| FR-X-006 | The system shall return the top-N (default 8) features with value, signed SHAP contribution, direction, and a plain-language sentence. | M | T |
| FR-X-007 | The system shall return the SHAP base value so the UI can show baseline → prediction decomposition. | S | T |
| FR-X-008 | The UI shall render SHAP contributions as a horizontal bar/waterfall chart with positive/negative colouring **plus** text/icons (not colour alone). | M | D |
| FR-X-009 | Explanation generation failure shall not block the prediction response; the API shall return the prediction with `explanation.status="unavailable"`. | M | T |
| FR-X-010 | Explainability sanity checks (Grad-CAM on ≥ 50 sample images; SHAP plausibility review) shall be performed and documented offline. | M | A/I |

### 3.3 Knowledge Base & Recommendations (FR-K)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-K-001 | The system shall maintain a `disease_knowledge` store keyed by `class_id` with symptoms, cause, management actions (cultural/biological/chemical), prevention, and sources. | M | I |
| FR-K-002 | Each KB entry shall cite at least one trusted source (publisher + title + URL/identifier) and a review date. | M | I |
| FR-K-003 | The disease prediction response shall include the entry's actions, prevention, sources, and a standard disclaimer. | M | T |
| FR-K-004 | The system shall provide a distinct "healthy plant care" entry for healthy classes. | M | T |
| FR-K-005 | The system shall not generate treatment text using the classifier or any generative model in MVP. | M | I |
| FR-K-006 | KB coverage shall be complete for every class the classifier can output (automated check in CI). | M | T |
| FR-K-007 | The system shall expose `GET /knowledge/{disease_id}`. | S | T |
| FR-K-008 | KB content shall be editable by admins via seed script/JSON without redeploying the frontend. | S | D |
| FR-K-009 | Chemical recommendations shall be phrased generically (active-ingredient class, not brand pushing) and include "follow local regulations and label directions." | S | I |

### 3.4 Yield Prediction (FR-Y)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-Y-001 | The system shall provide a form capturing: crop, location (lat/lon or region selection), season/year, optional sowing & harvest dates, optional farm area, optional soil properties. | M | D |
| FR-Y-002 | The system shall expose supported crops/regions/seasons via `GET /yield/options`. | M | T |
| FR-Y-003 | The system shall validate inputs (type, range, supported crop/region) and return 400/422 with field-level errors. | M | T |
| FR-Y-004 | The system shall automatically retrieve weather for the location and growth window (see FR-W) and let the user view and optionally override values. | M | T/D |
| FR-Y-005 | The system shall populate soil properties from a reference dataset where available, or accept manual entry; missing values shall be imputed using documented strategies. | S | T |
| FR-Y-006 | The system shall construct model features with the **same code path** as training (shared feature definition/versioned schema). | M | T/I |
| FR-Y-007 | The system shall predict yield using the production yield model and return value with unit (e.g., t/ha). | M | T |
| FR-Y-008 | The system should return a prediction interval (e.g., 80%) using quantile regression, conformal prediction, or ensemble spread. | S | T/A |
| FR-Y-009 | The system shall compute a risk level (`low`, `medium`, `high`) per the documented risk engine (ratio to historical baseline, optionally interval width). | M | T/A |
| FR-Y-010 | The system shall return baseline yield, ratio to baseline, and a short rationale for the risk level. | M | T |
| FR-Y-011 | The system shall return the SHAP explanation per FR-X-005…008. | M | T |
| FR-Y-012 | The system shall warn when inputs fall outside the training distribution (e.g., out-of-range temperature, unsupported region) and either widen the interval or refuse with a clear message. | S | T |
| FR-Y-013 | The system shall include model name, version, and weather source in every yield response. | M | T |
| FR-Y-014 | The system shall persist yield prediction records (inputs, outputs, SHAP, model version) with graceful degradation. | S | T |
| FR-Y-015 | The UI shall show predicted yield vs. historical/regional average in a chart. | S | D |
| FR-Y-016 | Yield prediction shall complete in ≤ 2 s p95 server-side with cached weather, ≤ 5 s with a live weather call (NFR-P-002). | M | A/T |
| FR-Y-017 | The system shall support at minimum a tabular model (XGBoost/Random Forest); LSTM/Transformer models shall be integrated only if experiments demonstrate benefit and data suffices. | M | A |

### 3.5 Weather Service (FR-W)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-W-001 | The system shall fetch weather via Open-Meteo as the primary provider and NASA POWER as fallback (or vice versa if configured). | M | T |
| FR-W-002 | The service shall retrieve at least temperature (min/max/mean), precipitation, relative humidity, and—where available—solar radiation and wind. | M | T |
| FR-W-003 | The service shall aggregate raw series into features matching the yield model (e.g., monthly/growth-stage totals/means). | M | T |
| FR-W-004 | The service shall cache responses with a TTL (default 180 min) keyed by location (rounded), window, and provider. | S | T |
| FR-W-005 | On provider failure, the system shall retry (bounded), fall back to the secondary provider, then to cache, then to a user-facing prompt for manual weather entry. | M | T |
| FR-W-006 | The system shall expose `GET /weather` for the frontend's preview panel. | S | T |
| FR-W-007 | The API shall record the provider used and fetch timestamp in the response. | S | T |

### 3.6 Dashboard & UI (FR-UI)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-UI-001 | The application shall provide pages: Home, Disease Detection, Yield Prediction, Dashboard, About/Model Info; plus History and Login if FR-A is implemented. | M | D |
| FR-UI-002 | The Dashboard shall present the latest crop-health result and the yield outlook together as summary cards linking to details. | M | D |
| FR-UI-003 | The UI shall be responsive from 360 px to desktop widths. | M | T/D |
| FR-UI-004 | The UI shall show loading/skeleton states and a "server waking up" message when response time exceeds 5 s. | S | D |
| FR-UI-005 | The UI shall show clear, actionable error messages mapped from API error codes. | M | T |
| FR-UI-006 | Every result page shall show a disclaimer: "Decision support only; confirm with a local agronomist before taking action." | M | I |
| FR-UI-007 | Severity and risk shall be communicated using text + icon + colour. | M | I |
| FR-UI-008 | Charts (Recharts) shall include accessible labels/titles and data tables or tooltips. | S | I |
| FR-UI-009 | The About page shall list datasets, model names/versions, headline metrics, supported crops/diseases, and known limitations (from `GET /models` and static content). | S | D |
| FR-UI-010 | The UI strings shall be centralized to enable future localization. | C | I |
| FR-UI-011 | Previously computed results in the current session shall persist across page navigation (client state). | S | T |

### 3.7 Accounts & History (FR-A) — Stretch

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-A-001 | The system may support sign-up/sign-in via Supabase Auth (email/magic link). | C | D |
| FR-A-002 | Authenticated users may view a chronological history of their predictions. | C | T |
| FR-A-003 | Authenticated users may delete individual predictions, which shall also delete associated stored images and overlays. | C | T |
| FR-A-004 | RLS shall prevent any user from reading or modifying another user's records. | C | T |
| FR-A-005 | Anonymous predictions shall remain usable without login; anonymous data shall be auto-purged after the retention period (default 30 days). | S | T |
| FR-A-006 | Users may save farm profiles (name, location, default crop, area) to prefill the yield form. | C | D |

### 3.8 Platform / Admin / MLOps (FR-M)

| ID | Requirement | Pri | Ver |
|---|---|---|---|
| FR-M-001 | Every training run shall log parameters, metrics, artifacts, git SHA, data-manifest hash, and random seed to a run record under `artifacts/runs/` (ADR-0012). | M | I |
| FR-M-002 | Disease experiments D-01…D-07 and yield experiments Y-00…Y-06 (see ARCH) shall be executed (or Y-04/Y-05 explicitly documented as data-limited) and comparable from their run records. | M | A |
| FR-M-003 | The system shall load models listed in a production pointer (`production.json`) at startup and expose their metadata via `GET /models`. | M | T |
| FR-M-004 | Promoting or rolling back a model shall require only a pointer change and service restart (no code change). | S | D |
| FR-M-005 | The backend shall expose `/health` (liveness) and `/health/ready` (models, DB, object storage status). | M | T |
| FR-M-006 | The repository shall include CI pipelines running lint, type-check, and tests for backend, frontend, and ML code. | M | I |
| FR-M-007 | The backend shall be containerized via Docker and runnable locally with a single command. | M | D |
| FR-M-008 | The project shall provide model cards for each production model (data, metrics, limitations, intended use). | M | I |
| FR-M-009 | OpenAPI documentation shall be auto-generated and exported to `docs/api/openapi.json`. | S | I |

---

## 4. External Interface Requirements

### 4.1 User Interface
See PRD §8.4 wireframes and FR-UI. Tailwind-based design system; consistent components (Card, Badge, Alert, Skeleton, Button); light mode required, dark mode optional.

### 4.2 Software Interfaces
| Interface | Protocol | Purpose | Notes |
|---|---|---|---|
| Frontend ↔ Backend | HTTPS REST/JSON, multipart for upload | All predictions & data | Versioned `/api/v1`; CORS allow-list |
| Backend ↔ PostgreSQL (Supabase) | PostgreSQL wire (pooler) | Persistence | SQLAlchemy/asyncpg; migrations via Alembic |
| Backend ↔ Supabase Storage | HTTPS (REST API; S3-compatible endpoint for training) | Images/models | Service-role key server-side only; presigned URLs for clients |
| Backend ↔ Open-Meteo | HTTPS/JSON | Weather | No API key; rate-limit aware |
| Backend ↔ NASA POWER | HTTPS/JSON | Weather/agro-climate | Fallback/historical |
| Frontend ↔ Supabase Auth | HTTPS | Login (stretch) | anon key only |
| Training ↔ Supabase Storage | S3-compatible API | Run records + artifacts | `artifacts/runs/` pushed before the session closes |
| CI/CD ↔ GitHub | GitHub Actions | Build/test/deploy | Secrets in GitHub |

### 4.3 Hardware Interfaces
User device camera (via browser `<input type="file" capture>`/MediaDevices). No other hardware interfaces.

### 4.4 Communication Interfaces
HTTPS (TLS 1.2+), JSON (UTF-8), multipart/form-data. Request/response size limit 10 MB (image) / 1 MB (JSON).

### 4.5 API Contract
Defined in `ARCH.md` §7.2; the exported OpenAPI file is the normative contract. Breaking changes require a new version path (`/api/v2`).

---

## 5. Non-Functional Requirements

### 5.1 Performance (NFR-P)
| ID | Requirement | Measure |
|---|---|---|
| NFR-P-001 | Disease inference + Grad-CAM + severity (server-side, warm, CPU) | p95 ≤ 3 s; p50 ≤ 1.5 s |
| NFR-P-002 | Yield inference + SHAP (server-side, cached weather) | p95 ≤ 2 s; with live weather ≤ 5 s |
| NFR-P-003 | End-to-end disease flow (upload to render) on typical broadband | ≤ 6 s |
| NFR-P-004 | Frontend Lighthouse performance (mobile) on landing page | ≥ 80 |
| NFR-P-005 | Backend memory with all production models loaded | ≤ 2 GB (goal ≤ 1 GB) |
| NFR-P-006 | Concurrency (demo-scale) | ≥ 5 simultaneous predictions without errors |
| NFR-P-007 | Cold-start model load time | ≤ 60 s (documented/mitigated in UI) |

### 5.2 Security (NFR-S)
| ID | Requirement |
|---|---|
| NFR-S-001 | All traffic shall use HTTPS. |
| NFR-S-002 | Secrets shall never be committed; they shall be provided via environment/secret managers. |
| NFR-S-003 | The Supabase service-role key shall be used server-side only. |
| NFR-S-004 | Uploaded files shall be validated, re-encoded, size-limited, and never executed. |
| NFR-S-005 | Storage buckets shall be private; access via short-lived signed URLs (≤ 15 min). |
| NFR-S-006 | CORS shall be restricted to approved origins. |
| NFR-S-007 | Predict endpoints shall be rate-limited per client. |
| NFR-S-008 | RLS shall be enabled on all user-owned tables (when auth is implemented). |
| NFR-S-009 | Dependencies shall be scanned (Dependabot, `pip-audit`, `npm audit`) in CI. |
| NFR-S-010 | Logs shall not contain image bytes, tokens, or precise personal location. |
| NFR-S-011 | Input shall be validated server-side with Pydantic schemas; SQL access shall use parameterized queries/ORM. |

### 5.3 Privacy (NFR-PR)
| ID | Requirement |
|---|---|
| NFR-PR-001 | The app shall display a concise privacy notice describing stored data (images, approximate location, predictions) and retention. |
| NFR-PR-002 | Stored coordinates shall be rounded (≈ 2 decimals) unless the user saves a farm profile. |
| NFR-PR-003 | Users shall be able to delete their stored data (authenticated) and anonymous data shall expire automatically. |
| NFR-PR-004 | No third-party analytics shall receive uploaded images. |

### 5.4 Reliability & Availability (NFR-R)
| ID | Requirement |
|---|---|
| NFR-R-001 | Target availability for demo period ≥ 95% (free-tier caveats documented). |
| NFR-R-002 | The API shall degrade gracefully (weather fallback, persistence failure, explanation failure) without crashing. |
| NFR-R-003 | Unhandled exceptions shall return a standard 500 error body with a request ID and be logged. |
| NFR-R-004 | Readiness probe shall fail if production models are not loaded. |

### 5.5 Usability & Accessibility (NFR-U)
| ID | Requirement |
|---|---|
| NFR-U-001 | A first-time user shall be able to obtain a disease result in ≤ 3 interactions after opening the Disease page. |
| NFR-U-002 | Plain-language copy (target reading level ≈ grade 8) for all farmer-facing text. |
| NFR-U-003 | WCAG 2.1 AA targets: colour contrast, alt text, focus order, keyboard operability. |
| NFR-U-004 | Touch targets ≥ 44×44 px on mobile. |
| NFR-U-005 | Usability test with ≥ 5 participants documented (SUS or task-success rate). |

### 5.6 Maintainability & Quality (NFR-M)
| ID | Requirement |
|---|---|
| NFR-M-001 | Backend automated test coverage ≥ 70% on services; critical paths (validation, thresholding, risk, feature building) ≥ 90%. |
| NFR-M-002 | Code shall pass `ruff`, `mypy` (backend/ML src) and `eslint`, `tsc --noEmit` (frontend) in CI. |
| NFR-M-003 | Modules shall follow the layered structure in ARCH §7.1; ML-specific code isolated in `app/ml`. |
| NFR-M-004 | Public functions shall have docstrings/type hints; ADRs recorded for major decisions. |
| NFR-M-005 | Training code shall be reproducible from config + seed (deterministic where feasible). |
| NFR-M-006 | Conventional commits and PR reviews on `main`. |

### 5.7 Portability & Scalability (NFR-PO)
| ID | Requirement |
|---|---|
| NFR-PO-001 | Backend shall run identically via Docker on Render, Hugging Face Spaces, or a generic cloud VM. |
| NFR-PO-002 | Storage and DB access shall be abstracted so alternative S3-compatible/PostgreSQL providers can be swapped via config. |
| NFR-PO-003 | Backend shall be stateless (model cache aside) to permit horizontal scaling. |

### 5.8 ML Quality Requirements (NFR-ML)
| ID | Requirement | Verification |
|---|---|---|
| NFR-ML-001 | Disease model shall achieve macro-F1 ≥ 0.94 / accuracy ≥ 95% on the held-out PlantVillage test split (target; report if not met with analysis). | A |
| NFR-ML-002 | Disease model shall be evaluated on a separate field-image set; macro-F1 and the domain-gap shall be reported (stretch target ≥ 0.70). | A |
| NFR-ML-003 | Confidence shall be calibrated (temperature scaling); ECE reported. | A |
| NFR-ML-004 | Yield model shall outperform the naïve baseline and Linear Regression on MAE/RMSE on the held-out time/region split; R² target ≥ 0.70 where data permits. | A |
| NFR-ML-005 | Yield results shall be reported overall and sliced by crop, region, and unusual-weather years. | A |
| NFR-ML-006 | Data leakage controls (group-aware/time-based splits) shall be documented and verified. | I |
| NFR-ML-007 | Per-class error analysis and confusion matrices shall be produced for the disease model. | A |
| NFR-ML-008 | Each production model shall have a model card listing intended use, data, metrics, limitations, and ethical considerations. | I |

---

## 6. Data Requirements

### 6.1 Logical Data Entities
| Entity | Key Attributes |
|---|---|
| Profile | id, display_name, preferred_language |
| Farm | id, user_id, name, lat, lon, region, default_crop, area_ha |
| DiseasePrediction | id, user_id?, class_id, confidence, status, top_k, severity, image_key, overlay_key, model_version, latency |
| YieldPrediction | id, user_id?, crop, location, season, inputs, predicted_yield, unit, interval, risk, baseline, shap, weather_summary, model_version |
| DiseaseKnowledge | class_id, crop, disease, symptoms, cause, actions, prevention, sources, reviewed_at |
| ModelVersion | pipeline, name, version, run_id, git_sha, metrics, artifact_uri, is_production |
| WeatherCache | key, payload, provider, fetched_at, expires_at |

(DDL in `ARCH.md` §8.2.)

### 6.2 Input Data Requirements
| Data | Format | Constraints |
|---|---|---|
| Leaf image | JPEG/PNG/WebP | ≤ 10 MB; min 128×128 px; RGB; single leaf recommended |
| Crop | enum | Must be in supported list |
| Location | lat ∈ [-90,90], lon ∈ [-180,180] or named region | Must map to a supported region for the yield model |
| Season/dates | ISO-8601 | sowing < harvest; year within supported range |
| Area | ha, > 0 | optional |
| Soil | pH ∈ [3,10], OC ≥ 0, texture ∈ enum | optional |

### 6.3 Training Data Requirements
| Pipeline | Requirement |
|---|---|
| Disease | PlantVillage labelled images; documented class counts; class-imbalance handling; deduplication check; held-out test split never used for tuning; separate field-image evaluation set (even small) |
| Yield | Multi-year yield per crop/region; aligned weather (Open-Meteo/NASA POWER); soil attributes; cleaning, outlier handling, imputation policy; time/region-based splits |
| KB | Manually curated from trusted sources with citations |

### 6.4 Data Retention
| Data | Retention |
|---|---|
| Anonymous uploads/overlays | 30 days default (configurable) |
| Authenticated user data | Until user deletes account/record |
| Weather cache | TTL-based (hours) |
| Logs | 30 days |

---

## 7. ML & MLOps Requirements (Detailed)

| ID | Requirement |
|---|---|
| ML-001 | The disease baseline CNN, a pretrained ResNet, a pretrained EfficientNet, and a ViT shall each be trained/fine-tuned and compared. |
| ML-002 | Data augmentation (flip, rotation, colour jitter, blur, random crop, background variation) shall be applied and its effect measured (ablation). |
| ML-003 | Disease metrics shall include accuracy, precision, recall, F1 (macro & weighted), confusion matrix. |
| ML-004 | Yield models LR, RF, XGBoost shall be evaluated before LSTM/Transformer; MAE, RMSE, R² shall be reported. |
| ML-005 | Hyper-parameter search (grid/random/Optuna) shall be recorded as a parent run plus one child run per trial, linked by the parent's `run_id`. |
| ML-006 | Final disease model shall be exported to a deployment format (TorchScript/ONNX or state-dict + config) and verified for numerical parity with the training model (tolerance 1e-4 on logits). |
| ML-007 | Preprocessing config, label map, and feature schema shall be versioned with each model artifact. |
| ML-008 | A "golden test set" of ≥ 20 images and ≥ 10 yield payloads with expected outputs shall be kept in `backend/tests/fixtures` for regression testing after model updates. |
| ML-009 | Error analysis shall cover hard disease classes, real-world conditions, and unusual weather/soil conditions. |
| ML-010 | Model promotion requires: metrics ≥ prior production (or documented justification), parity test pass, golden-set pass, model card updated. |

---

## 8. Constraints Summary
| Type | Constraint |
|---|---|
| Technical | CPU-only inference; limited RAM; free-tier cold starts; Kaggle session and weekly GPU quotas |
| Data | PlantVillage domain gap; sparse yield/soil data; geography-bound |
| Legal/Ethical | Dataset licences; advice is non-prescriptive; privacy of images/location |
| Schedule | One-semester (~14 weeks) delivery; scope controlled via MoSCoW |
| Team | Small team; extensions deferred |

---

## 9. Use Cases

### UC-1: Detect Disease from Leaf Image
| Item | Description |
|---|---|
| Actor | Farmer |
| Pre-conditions | Device with image; internet access |
| Trigger | Farmer opens Disease page |
| Main flow | 1) Select/capture image → 2) Client validates/compresses → 3) Click Analyze → 4) API validates & preprocesses → 5) Model predicts → 6) Grad-CAM + severity computed → 7) KB actions fetched → 8) Result rendered |
| Alternate A1 | Invalid file → inline error; no upload |
| Alternate A2 | Confidence < threshold → "uncertain" message with retake tips |
| Alternate A3 | Explanation fails → prediction shown without heatmap + notice |
| Alternate A4 | Server cold → waking message → retry |
| Post-conditions | Prediction stored (if enabled); result on dashboard |

### UC-2: Predict Crop Yield
| Item | Description |
|---|---|
| Actor | Farmer |
| Pre-conditions | Supported crop & region |
| Main flow | 1) Enter crop/location/season/farm → 2) System fetches weather & soil → 3) User reviews/overrides → 4) Submit → 5) Features built → 6) Model predicts → 7) Risk computed → 8) SHAP computed → 9) Results + charts shown |
| Alternate A1 | Weather unavailable → fallback → cache → manual entry |
| Alternate A2 | Out-of-range inputs → warning/refusal |
| Alternate A3 | Unsupported crop → list of supported crops |
| Post-conditions | Prediction stored (if enabled); dashboard updated |

### UC-3: View Combined Dashboard
Actor: Farmer. Flow: open Dashboard → latest disease result card + yield outlook card + trend charts → navigate to details.

### UC-4: Review Model Transparency
Actor: Agronomist/Evaluator. Flow: open About → view model names/versions/metrics/limitations → optionally inspect Grad-CAM/SHAP examples.

### UC-5: Train, Track & Promote a Model
Actor: ML Engineer. Flow: configure experiment YAML → train on Kaggle → run record written → compare runs → export → parity test → upload to Supabase Storage → update `production.json` → redeploy → verify `/models`.

### UC-6: Manage History (Stretch)
Actor: Registered Farmer. Flow: login → History → select record → view/delete.

---

## 10. Acceptance Criteria (Representative)

| ID | Scenario | Expected |
|---|---|---|
| AC-1 | Upload a clear tomato early-blight test image | Response `status=ok`, class contains Early blight, confidence ≥ 0.6, overlay URL present, severity ≠ none, KB actions present, disclaimer present |
| AC-2 | Upload a healthy leaf image | `is_healthy=true`, severity `none`, "healthy plant care" advice |
| AC-3 | Upload a photo of a non-leaf object | `status` is `uncertain` or `not_a_leaf`; no diagnosis/treatment displayed |
| AC-4 | Upload a 25 MB file / a `.pdf` renamed `.jpg` | 413 / 415 or 400 with standard error body |
| AC-5 | Disease request with model offline | `/health/ready` fails; predict returns 503 `MODEL_NOT_READY` |
| AC-6 | Yield request for supported crop/location | Response with yield, unit, risk, ≥ 5 SHAP contributions, weather source |
| AC-7 | Open-Meteo blocked in test | System falls back to NASA POWER (or cache) and still returns a prediction |
| AC-8 | Yield request for unsupported crop | 400 `UNSUPPORTED_CROP` with supported list |
| AC-9 | Grad-CAM sanity review (≥ 50 images) | ≥ 80% reviewed images highlight lesion/leaf region rather than background (reported) |
| AC-10 | CI on PR | Lint, type-check, tests all pass; coverage thresholds met |
| AC-11 | Run records | Every model in `models/production.json` links to a run record with params/metrics |
| AC-12 | Mobile (360 px) | All pages usable without horizontal scroll; tap targets ≥ 44 px |
| AC-13 | Production deploy | Public frontend URL loads; API `/health/ready` green; end-to-end disease + yield demos succeed |
| AC-14 | Security | Private buckets not publicly listable; expired signed URL returns 403; service-role key absent from frontend bundle |

---

## 11. Traceability Matrix (PRD → SRS)

| PRD Story | SRS Requirements |
|---|---|
| US-D1 | FR-D-001…006 |
| US-D2 | FR-D-008…010, FR-D-020 |
| US-D3 | FR-D-013…015 |
| US-D4 | FR-D-016, FR-X-001…004 |
| US-D5 | FR-D-017, FR-K-001…009 |
| US-D6 | FR-D-011, FR-D-012 |
| US-D7 | FR-D-002 |
| US-D8 | FR-D-010 |
| US-D9 | FR-A-002 |
| US-Y1 | FR-Y-001…003 |
| US-Y2 | FR-Y-004, FR-W-001…007 |
| US-Y3 | FR-Y-009, FR-Y-010 |
| US-Y4 | FR-Y-011, FR-X-005…008 |
| US-Y5 | FR-Y-004 (override) |
| US-Y6 | FR-Y-008 |
| US-Y7 | FR-Y-010, FR-Y-015 |
| US-P1 | FR-UI-002 |
| US-P2 | FR-UI-003, NFR-U-004 |
| US-P3 | FR-UI-005, FR-UI-006 |
| US-P4 | FR-A-001…006 |
| US-P5 | FR-UI-009, FR-M-008 |
| US-P6 | FR-M-001, FR-M-002 |

---

## 12. Appendices

### Appendix A — Supported Scope (MVP)
- **Disease classes:** PlantVillage classes (38 classes across 14 crops: apple, blueberry, cherry, corn, grape, orange, peach, bell pepper, potato, raspberry, soybean, squash, strawberry, tomato). If time or deployment size requires, the MVP may restrict the UI to a subset of crops while the model covers all; the supported list is exposed by `GET /disease/classes`.
- **Yield crops/region:** To be fixed in Phase 1 (decision Q1) — recommended 2–3 crops in one country/region with ≥ 10 years of yield records.

### Appendix B — Standard Error Codes
`INVALID_INPUT, UNSUPPORTED_CROP, FILE_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE, NOT_A_LEAF, RATE_LIMITED, WEATHER_UNAVAILABLE, MODEL_NOT_READY, EXPLANATION_UNAVAILABLE, INTERNAL_ERROR`

### Appendix C — Default Parameters
| Parameter | Default |
|---|---|
| `CONFIDENCE_THRESHOLD` | 0.60 |
| Image input size | 224×224 (per model config) |
| Severity bands | low < 10%, moderate 10–30%, severe > 30% |
| Risk thresholds | low ≥ 0.95, medium 0.80–0.95, high < 0.80 of baseline |
| SHAP top-N | 8 |
| Signed URL TTL | 15 min |
| Weather cache TTL | 180 min |
| Anonymous retention | 30 days |
| Rate limit | 20 requests/min/client on predict |

### Appendix D — Requirement Counts
Functional (FR): 91 · Non-functional (NFR): 48 · ML/MLOps (ML): 10 · Use cases: 6 · Acceptance criteria: 14 (representative).

### Appendix E — Revision History
| Version | Date | Notes |
|---|---|---|
| 1.0 | 24 Oct 2026 | Initial draft derived from the project brief |