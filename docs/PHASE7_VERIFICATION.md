# Phase 7 verification

Run date: 2026-10-26

## Completed checks

| Phase 7 item | Evidence | Result |
|---|---|---|
| 7.1 Frontend ↔ backend integration | FastAPI TestClient endpoint suite, live `/health`, `/models`, `/yield/options`, `/weather`, disease and yield flows | Pass |
| 7.2 Acceptance criteria | `backend/tests/test_phase5_endpoints.py`, `backend/tests/test_phase7_integration.py`, frontend responsive suite | Pass for locally executable criteria |
| 7.3 Load/rate protection | Prediction rate-limit acceptance test and latency fields on disease/yield responses | Pass for the configured local protection check |
| 7.4 Security checks | CORS allow-list, upload-size guard, redacted errors, malformed image handling, path traversal guard, private-storage signed URL flow | Pass locally |
| 7.8 Bug triage | Frontend CORS support for `localhost` and `127.0.0.1`; duplicate loader dots removed | Resolved |

## Test evidence

- Backend: `pytest -q` — 66 tests passed.
- Frontend unit/component tests: `npm test` — 4 tests passed.
- Frontend responsive tests: `npm run test:e2e` — 24 viewport checks passed at
  360, 390, 768, and 1280 px across all six routes.
- Frontend lint, TypeScript, and production build passed.
- FastAPI `/api/v1/health` returned HTTP 200 with both models warmed.
- CORS returned the requesting local frontend origin for both supported local hosts.

## Criteria requiring external evidence

The following are not honestly reproducible in this local workspace and remain
deployment/evaluation tasks:

- AC-9: Grad-CAM review on at least 50 independently labelled field images.
- AC-11: final production run-record linkage for every promoted model.
- AC-13: public staging deployment and phone-based end-to-end demo.
- AC-14: expired signed-URL verification against the production Supabase project.
- 7.7: usability study with five real participants and SUS scoring.

These are recorded as release gates rather than replaced with synthetic results.
The app's existing model limitations and local fallback behavior remain the
source of truth until staging credentials, field images, and participants are
available.
