# Zenvy

Zenvy is a crop intelligence platform for farmers and agronomists. It turns a
leaf photo into an explainable disease assessment and combines crop, location,
soil, season, and weather data into a yield forecast.

Zenvy is **decision support only**. Confirm serious crop problems and treatment
decisions with a qualified local agronomist.

## What Zenvy does

- **Disease detection** — JPEG, PNG, and WebP upload with drag-and-drop,
  camera capture, client-side validation, compression, confidence, top-3
  alternatives, severity, quality warnings, Grad-CAM evidence, recommendations,
  sources, and uncertain states.
- **Yield forecasting** — supported crop and district options from the backend,
  editable latitude/longitude, season and area inputs, live weather preview,
  weather overrides, 80% prediction intervals, risk advisories, and SHAP
  explanations.
- **Dashboard** — disease and yield history, summary counters, recent scans,
  forecast shortcuts, account controls, and model status.
- **Model information** — live model versions and metrics from the backend,
  explanation methods, datasets, limitations, and responsible-use guidance.
- **Private storage** — Supabase Storage uploads and Grad-CAM overlays use
  signed URLs, with local filesystem fallback for development.

## Product status

| Area | Status |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS v4, responsive routes, typed API client, loading/error states, accessibility and mobile checks |
| Backend | FastAPI API with auth, disease prediction, yield prediction, weather adapters, history, rate limiting, storage, model registry, and readiness checks |
| Disease model | 38-class EfficientNet/TorchScript pipeline with Grad-CAM and severity estimation |
| Yield model | XGBoost prediction with conformal interval calibration, risk assessment, and SHAP contributions |
| Database | SQLAlchemy/Alembic with local SQLite fallback and Supabase PostgreSQL support |
| Storage | Private Supabase buckets with signed URLs and local fallback |
| Phase 6 | Complete locally: tests, responsive checks, Lighthouse audit, loading system, and locale-ready copy structure |
| Phase 7 | Local integration and security checks complete; field evaluation and staging gates documented |
| Phase 8 | Deployment workflows and runbook complete; provider deployment still requires production accounts and secrets |

## Application routes

| Route | Purpose | Auth |
|---|---|---|
| `/` | Landing page and product overview | No |
| `/login` | Login and registration | No |
| `/disease` | Upload and analyze a leaf image | Yes |
| `/yield` | Create an explainable yield forecast | Yes |
| `/dashboard` | Review history, metrics, and account data | Yes |
| `/about` | Inspect live model cards and limitations | No |

## Repository layout

```text
backend/     FastAPI service, schemas, API routes, services, database, tests
frontend/    Next.js application and frontend tests
ml/          Training notebooks, model artifacts, configs, and knowledge base
docs/        Product, architecture, development, verification, and deployment docs
.github/     CI and backend image workflows
```

## Requirements

- Python 3.13 recommended
- Node.js 20+
- npm
- Docker for container builds
- CPU is enough for local inference; model training runs on Kaggle GPU notebooks

## Run locally

### Backend

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The backend loads `.env` relative to the backend directory. Fill in Supabase
and database values when using remote services; local development can use the
SQLite and filesystem fallbacks.

Backend URLs:

- API docs: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/api/v1/health>
- Readiness: <http://localhost:8000/api/v1/health/ready>
- Model registry: <http://localhost:8000/api/v1/models>

### Frontend

From `frontend/`:

```powershell
npm ci
Copy-Item .env.local.example .env.local
npm run dev
```

Open <http://localhost:3000>.

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` when the API is not
running at `http://localhost:8000`. `NEXT_PUBLIC_*` values are public and are
embedded into the browser bundle.

### Start both services

Use two terminals:

```powershell
# Terminal 1
Set-Location C:\Users\HP\Desktop\ai-crop\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2
Set-Location C:\Users\HP\Desktop\ai-crop\frontend
npm run dev
```

## Testing and validation

### Backend

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers API contracts, auth, disease and yield inference, weather
fallback behavior, errors, rate limits, storage safety, and Phase 7 checks.

### Frontend

```powershell
Set-Location frontend
npm run lint
npx tsc --noEmit --pretty false
npm test
npm run build
```

Responsive browser checks:

```powershell
npm run test:e2e
```

The Playwright suite checks all routes at 360, 390, 768, and 1280 pixels.
Install the browser once if needed:

```powershell
npx playwright install chromium
```

## Docker

Build from the repository root because the image copies both backend and ML
files:

```powershell
docker build -f backend/Dockerfile -t zenvy-backend .
docker run --rm -p 8000:8000 --env-file backend/.env zenvy-backend
```

Verify the container:

```powershell
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/models
```

The image exposes port `8000`, includes a Docker health check, and runs one
worker to keep PyTorch and SHAP within small-host memory limits.

## Configuration

Copy the templates before configuring a local environment:

- [backend/.env.example](backend/.env.example)
- [frontend/.env.local.example](frontend/.env.local.example)

Important backend variables:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `staging`, or `production` |
| `CORS_ORIGINS` | Comma-separated frontend origin allow-list |
| `DATABASE_URL` | Supabase pooler URL in production |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only Supabase access |
| `JWT_SECRET_KEY` | Application token signing secret |
| `MODEL_REGISTRY_URI` | Optional production model pointer |
| `REQUIRE_MODELS` | Set to `true` for production readiness enforcement |
| `MAX_UPLOAD_MB` | Upload size limit, default 10 MB |
| `RATE_LIMIT_PREDICT` | Prediction rate limit, default `20/minute` |
| `SUPABASE_BUCKET_UPLOADS` | Private image upload bucket |
| `SUPABASE_BUCKET_OVERLAYS` | Private Grad-CAM bucket |
| `SUPABASE_BUCKET_MODELS` | Private model artifact bucket |

Never commit `.env`, service-role keys, JWT secrets, S3 secrets, or signed URLs.
The root [`.gitignore`](.gitignore) and [`.dockerignore`](.dockerignore) protect
the normal local and container build paths.

## API surface

The API is versioned under `/api/v1`:

```text
GET  /health
GET  /health/ready
GET  /models
GET  /disease/classes
POST /disease/predict
GET  /yield/options
POST /yield/predict
GET  /weather
POST /auth/register
POST /auth/login
GET  /auth/me
GET  /auth/history/stats
GET  /auth/history/disease
GET  /auth/history/yield
```

Errors use one envelope:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "A readable explanation",
    "details": {},
    "request_id": "..."
  }
}
```

Every request receives an `X-Request-ID`. Use it when investigating a failed
prediction or contacting the operator.

## Deployment

Read [docs/DEPLOY.md](docs/DEPLOY.md) before deploying. It covers:

- Vercel frontend setup
- Render or container-host backend setup
- Supabase migrations, private buckets, policies, signed URLs, and lifecycle
- Model promotion and rollback
- Health checks and cold starts
- Production smoke tests on a phone
- Monitoring, security, dependency scans, and quota planning

The repository includes:

- [Frontend CI](.github/workflows/ci-frontend.yml)
- [Backend CI](.github/workflows/ci-backend.yml)
- [Backend image workflow](.github/workflows/deploy-backend.yml)

Public deployment is not claimed until the provider URLs, readiness checks,
phone smoke test, and rollback evidence are recorded.

## ML and training

Training runs use Kaggle GPU notebooks. Start with
[`ml/README.md`](ml/README.md) and
[`docs/adr/0003-training-on-kaggle.md`](docs/adr/0003-training-on-kaggle.md).

Production artifacts are loaded from `ml/artifacts/models` during local
development or from the configured Supabase model registry in deployment.
Keep model versions, metrics, calibration files, and run IDs together.

## Documentation

- [Product requirements](docs/PRD.md)
- [Software requirements](docs/SRS.md)
- [Architecture](docs/ARCH.md)
- [Development plan](docs/DEV_PLAN.md)
- [Phase 6 verification](docs/DEV_PLAN.md)
- [Phase 7 verification](docs/PHASE7_VERIFICATION.md)
- [Deployment runbook](docs/DEPLOY.md)
- [Design system](docs/DESIGN.md)

## Responsible use

Zenvy can be wrong when a photo is blurry, poorly lit, contains multiple
leaves, or comes from a crop outside the supported classes. Disease severity
is an estimate from visible image regions, not a laboratory measurement.
Yield forecasts depend on the quality and coverage of weather, soil, location,
and historical data.

Use Zenvy to investigate and compare signals. Confirm high-impact decisions
with local agronomic expertise.
