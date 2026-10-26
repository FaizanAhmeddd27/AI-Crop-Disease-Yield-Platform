# Zenvy deployment guide

This is the Phase 8 runbook for the current stack:

- Frontend: Next.js in `frontend/`
- Backend: FastAPI in `backend/`
- Database and private object storage: Supabase
- Weather: Open-Meteo with the configured NASA POWER fallback
- Model serving: CPU inference inside the backend container

The backend Dockerfile runs one worker intentionally. PyTorch and SHAP are
memory-sensitive on free-tier hosts.

## 1. Release gates

Run these checks before every release:

```powershell
Set-Location C:\Users\HP\Desktop\ai-crop\backend
.\.venv\Scripts\python.exe -m pytest -q

Set-Location C:\Users\HP\Desktop\ai-crop\frontend
npm ci
npm run lint
npx tsc --noEmit --pretty false
npm test
npm run build
```

For responsive validation, start the frontend and run `npm run test:e2e`.
The suite checks all routes at 360, 390, 768, and 1280 pixels.

## 2. Secrets and environment variables

Never put production values in Git, the frontend bundle, Dockerfile layers,
or a committed `.env` file.

### Backend

Copy `backend/.env.example` to `backend/.env` for local work. Configure these
as secrets on the production host:

| Variable | Required | Purpose |
|---|---:|---|
| `APP_ENV` | Yes | Set to `production` |
| `CORS_ORIGINS` | Yes | Exact frontend origin(s) |
| `DATABASE_URL` | Yes | Supabase pooler URL, preferably port 6543 |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Backend-only database/storage access |
| `JWT_SECRET_KEY` | Yes | Long random application signing key |
| `REQUIRE_MODELS` | Yes | Set to `true` after promotion |
| `MODEL_REGISTRY_URI` | Recommended | `supabase://agri-models/models/production.json` |
| `WEATHER_PRIMARY` | Yes | Normally `open-meteo` |
| `WEATHER_FALLBACK` | Yes | Normally `nasa-power` |
| `RATE_LIMIT_PREDICT` | Yes | Example: `20/minute` |
| `SUPABASE_BUCKET_UPLOADS` | Yes | Private uploads bucket |
| `SUPABASE_BUCKET_OVERLAYS` | Yes | Private Grad-CAM bucket |
| `SUPABASE_BUCKET_MODELS` | Yes | Private model bucket |

Use the Supabase pooler connection string on hosts without direct IPv6
database connectivity. Never expose the service-role key to Next.js.

### Frontend

Set this build-time variable in Vercel or the frontend host:

```text
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

It must be a public backend origin without a trailing slash. `NEXT_PUBLIC_*`
values are embedded in the browser bundle and cannot contain secrets.

## 3. Supabase production setup

1. Create or select the production Supabase project.
2. Run the migrations in `backend/app/db/migrations/`.
3. Configure the backend pooler `DATABASE_URL`.
4. Create these private buckets:
   - `agri-uploads`
   - `agri-overlays`
   - `agri-models`
5. Apply policies so browsers cannot list or read objects directly.
6. Allow the backend service-role key to upload and create signed URLs.
7. Add a lifecycle rule to purge anonymous uploads after 30 days.
8. Verify signed URLs use `/storage/v1/object/sign/` and expire.
9. Rotate any service key ever pasted into chat, issues, logs, or terminals.

The storage service returns signed URLs for private buckets. A public object URL
is not a production substitute.

## 4. Model promotion and rollback

Promotion:

1. Upload model files and `production.json` to `agri-models`.
2. Ensure every entry contains version, metrics, and run ID.
3. Set `MODEL_REGISTRY_URI` to the production pointer.
4. Set `REQUIRE_MODELS=true`.
5. Restart the backend.
6. Check `/api/v1/health/ready` and `/api/v1/models`.
7. Run one disease and one yield smoke request.

Rollback:

1. Point `production.json` to the last known-good versions.
2. Restart or redeploy the backend.
3. Confirm readiness and model versions.
4. Keep failed model files for investigation.

The image also contains local model artifacts when available, so it remains
self-contained at this project stage. The registry becomes the source of truth
once promotion is active.

## 5. Backend deployment

### Build and run locally

From the repository root:

```powershell
docker build -f backend/Dockerfile -t zenvy-backend .
docker run --rm -p 8000:8000 --env-file backend/.env zenvy-backend
```

Verify:

```powershell
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/health/ready
```

The image exposes port 8000 and includes a Docker health check.

### Render or another container host

1. Create a private web service from the repository.
2. Use `backend/Dockerfile` with the repository root as build context.
3. Expose port `8000`.
4. Add backend environment variables through the platform secret manager.
5. Set the health path to `/api/v1/health/ready`.
6. Allow enough startup time for Torch and both models to warm.
7. Deploy from a protected branch or signed release tag.
8. Verify readiness, CORS, disease, yield, and signed storage flows.

The tagged image workflow publishes to GHCR. It does not silently deploy to a
third-party host.

## 6. Frontend deployment on Vercel

1. Import the repository into Vercel.
2. Set project root to `frontend`.
3. Use `npm ci` for install and `npm run build` for build.
4. Add `NEXT_PUBLIC_API_BASE_URL` for Preview and Production separately.
5. Add the deployed frontend origin to backend `CORS_ORIGINS`.
6. Deploy a Preview first and check every route.
7. Promote to Production only after backend smoke tests pass.

No backend secret belongs in a Vercel variable with a `NEXT_PUBLIC_` prefix.

## 7. Post-deploy smoke tests

```powershell
curl https://api.example.com/api/v1/health
curl https://api.example.com/api/v1/health/ready
curl https://api.example.com/api/v1/models
curl https://api.example.com/api/v1/yield/options
curl https://app.example.com/
```

Then verify on a phone:

1. Open the landing page.
2. Log in or register.
3. Upload a clear leaf photo and confirm diagnosis, confidence, severity,
   Grad-CAM, recommendations, and history.
4. Open `/yield`, choose a crop and district, refresh weather, and forecast.
5. Open `/dashboard` and confirm recent disease and yield records.
6. Open `/about` and confirm live model versions.
7. Test a bad image, unsupported crop, offline backend, and expired signed URL.

## 8. Observability and cold starts

- Monitor `/api/v1/health/ready`, not only `/api/v1/health`.
- Alert when readiness is non-200 or either model is unavailable.
- Track request IDs, prediction latency, 429s, 5xxs, and weather fallback use.
- Warm the service after deploy with health and model requests.
- Keep logs structured and never log image bytes, tokens, passwords, or signed
  URLs.

## 9. Security checklist

- [ ] `APP_ENV=production`
- [ ] `REQUIRE_MODELS=true`
- [ ] `JWT_SECRET_KEY` replaced with a generated secret
- [ ] Supabase service-role key exists only on the backend
- [ ] Storage buckets are private and not listable
- [ ] Signed URLs expire and fail after expiry
- [ ] CORS contains only real frontend origins
- [ ] Upload and prediction rate limits are enabled
- [ ] HTTPS is enabled on both public services
- [ ] Dependency and container scans run in CI
- [ ] Secrets are rotated after accidental exposure

## 10. Cost, quotas, and contingency

Track quotas for Vercel, the backend host, Supabase database/storage, Open-Meteo,
NASA POWER, and bandwidth. Set alerts before free-tier limits are reached.

If the backend host runs out of memory:

1. Keep one worker.
2. Reduce concurrent prediction limits.
3. Disable nonessential debug logging.
4. Move model artifacts to the registry and reduce image layers.
5. Upgrade the host before enabling more workers.

If weather providers fail, the adapter uses its configured fallback/cache. If
both are unavailable, return the degraded response and do not call live weather
current.

## 11. Phase 8 status

Completed in the repository:

- Root `.gitignore` and Docker build-context protection.
- Backend production Dockerfile and health check.
- Frontend and backend CI workflows.
- Tagged backend image publishing workflow.
- Environment, secrets, storage, model promotion, rollback, smoke-test,
  observability, security, and cost procedures.

Still requiring external accounts or credentials:

- Vercel production deployment.
- Render/Cloud production deployment.
- Production Supabase policies, lifecycle rules, and backup verification.
- Public uptime monitor and deployment webhook.
- Live rollback drill against the production host.

Do not mark those external steps complete until public URLs and evidence are
recorded in the release checklist.
