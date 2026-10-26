# ADR-0011: Use Supabase Storage instead of Cloudflare R2

- **Status:** Accepted — supersedes the "Cloudflare R2" wording of ADR-0007 and
  ADR-0008 in `ARCH.md` §15
- **Date:** 24 Oct 2026
- **Deciders:** project owner
- **Affects:** ARCH §2 (stack), §2.1 (libraries), §4 (diagram), §6.4 (registry),
  §9 (storage), §11 (deployment), §13 (config), §15 (ADRs), §16 (failure modes);
  SRS §1.2, §2.1, §2.4, §4.2, §8, UC-5; PRD §6.1, §12, §13; DEV_PLAN tasks
  0.3, 2.12, 3.12, 5.3, 5.11, 7.1, 8.4; `ml/` notebooks and secrets

## Context

The original architecture splits persistence across two vendors: **Supabase
PostgreSQL** for relational data and **Cloudflare R2** for objects (leaf images,
Grad-CAM overlays, model artifacts).

The project is a single-semester build with a small team. The practical costs of
the split are:

- two dashboards, two sets of credentials, two quota systems, two backup stories;
- a second place to configure CORS and lifecycle rules;
- a second vendor whose free tier can change independently of the one already
  required for the database;
- a service-role key *and* an R2 key pair to rotate and explain.

Supabase Storage is part of the Supabase project that is already mandatory for
Postgres. It exposes private buckets, signed URLs, per-bucket policies, and an
S3-compatible endpoint.

## Decision

Store all objects in **Supabase Storage**, in three private buckets:
`agri-uploads`, `agri-overlays`, `agri-models`.

Access is split by caller:

| Caller | Mechanism | Credential |
|---|---|---|
| FastAPI backend | Storage REST API over `httpx` | `SUPABASE_SERVICE_ROLE_KEY` (server-side only) |
| Kaggle training | S3-compatible endpoint (`/storage/v1/s3`) | dedicated S3 access key pair |
| Browser | short-lived signed URL minted by the API | none |

Training gets its **own** S3 key pair rather than the service-role key, so a
notebook compromise cannot read the database.

## Consequences

**Positive**
- One vendor, one project, one budget. No second account to create in Phase 0.
- Credentials already needed for Postgres also cover backend object access.
- Buckets sit next to the rows that reference them, which simplifies deletion
  (drop the row, delete the object) and staging/prod separation.
- Private-by-default buckets plus signed URLs satisfy NFR-S-005 without
  extra configuration.
- The S3-compatible endpoint keeps the training code portable: `boto3` against
  Supabase today, any S3 provider later.

**Negative / mitigations**
- **Per-object size limit** — the free plan defaults to 50 MB per object, which a
  raw ResNet/EfficientNet checkpoint can exceed. *Mitigation:* promote ONNX or
  quantized exports (smaller), raise the global limit on a paid plan, and keep
  oversized *training* checkpoints in a Kaggle Dataset version instead.
- **Smaller free egress allowance** than R2's zero-egress pricing. *Mitigation:*
  model artifacts are downloaded once at startup into `MODEL_CACHE_DIR`; images
  are served through expiring signed URLs and purged on the retention schedule.
- **Fewer S3 features** than a dedicated object store (no bucket versioning,
  narrower multipart/lifecycle surface). *Mitigation:* the provider is behind a
  thin storage adapter, so switching later means changing one module; model
  versions are already tracked in `model_versions`, not by bucket versioning.
- **Region coupling** — S3 signatures require `SUPABASE_S3_REGION` to match the
  project region. *Mitigation:* it is an explicit env var with a documented
  default, and the setup notebook prints the derived endpoint.

## Alternatives considered

| Option | Why not |
|---|---|
| Cloudflare R2 (original ADR-0007) | Second vendor with its own credentials, quotas and CORS; no benefit at this scale, since Supabase is already required |
| AWS S3 | More configuration (IAM, bucket policies) and cost for a demo-scale project |
| Store objects in Postgres (`bytea`) | Bloats the database, poor streaming, backups become huge |
| Local disk / container volume | Lost on redeploy; no shared state between instances |
| Kaggle Datasets only | Fine for training artifacts, unusable as the runtime store for user uploads |

## Rollback

Storage access is isolated in one service module and configured entirely through
environment variables. Moving back to R2 (or to any S3-compatible provider)
means pointing the adapter at another endpoint and swapping the bucket names —
no schema or API-contract change.
