# `ml/` — Training & experimentation (Kaggle)

Offline training for both pipelines. **Training runs on Kaggle Notebooks (GPU);
inference runs on CPU in the FastAPI backend.** This replaces the Colab workflow
in `DEV_PLAN.md` — see [`docs/adr/0003-training-on-kaggle.md`](../docs/adr/0003-training-on-kaggle.md).

Current state: **Phase 0** — environment/setup only. Datasets, configs and
training code arrive in Phases 1–3.

```
ml/
├── requirements-kaggle.txt   # packages Kaggle does not ship (never install torch)
├── notebooks/kaggle/         # 00 setup, 01 EDA, 02 disease training, 03/04 yield, 05 XAI
├── src/common/               # seed_everything(), path resolution, run tracking
├── data/                     # local only, git-ignored
└── artifacts/                # local only, git-ignored
```

## Why Kaggle instead of Colab

| | Kaggle | Colab free |
|---|---|---|
| GPU quota | ~30 h/week, resets weekly | Session-dependent, throttled |
| Max session | ~12 h | ~12 h (free tier often less) |
| Preinstalled stack | torch/vision/timm/sklearn ready | Installed per session |
| Datasets | Attach as versioned inputs | Mount Drive or re-download |
| Persistence | Commit output + datasets | Drive |

The trade-off is that **nothing persists between sessions**. Every run must
checkpoint outward (Supabase Storage or a Kaggle Dataset version). That constraint
is why the training scripts must be resumable — it is a hard requirement, not a
nicety.

## One-time setup

1. **Account + phone verification** — GPU is unavailable until the account is
   phone-verified.
2. **Create a Kaggle Dataset for the data.** Upload PlantVillage (or the yield
   tables) as a private dataset; later attach it read-only at
   `/kaggle/input/<slug>/`. Do not re-download inside every session.
3. **Add secrets** (`Add-ons → Secrets`): `SUPABASE_URL`,
   `SUPABASE_S3_ACCESS_KEY_ID`, `SUPABASE_S3_SECRET_ACCESS_KEY`,
   `SUPABASE_S3_REGION` (must match the project region) and
   `SUPABASE_BUCKET_MODELS`. The S3 key pair comes from the Supabase dashboard
   under *Storage → S3 access keys*; do not reuse the service-role key there.
4. **Create the notebooks** as Kaggle notebooks from this folder, then set
   *Accelerator → GPU T4 x2 / P100* and *Internet → On*.

## Where each `.env` value comes from

Copy `ml/.env.example` to `ml/.env` for local runs, and put the same names into
*Add-ons → Secrets* for Kaggle.

| Variable | Required? | Where to get it |
|---|---|---|
| `ML_DATA_ROOT` | No | Empty is correct: it resolves to `/kaggle/input` on Kaggle and `ml/data` locally (`src/common/paths.py`). Set an absolute path only if the data lives somewhere else, e.g. `D:\datasets\plantvillage`. |
| `ML_ARTIFACT_ROOT` | No | Empty resolves to `/kaggle/working/artifacts` on Kaggle and `ml/artifacts` locally. Set an absolute path to redirect checkpoints (e.g. a fast local disk). |
| `SUPABASE_*` | Yes for persistence | Supabase dashboard: project URL, *Storage → S3 access keys*, project region, bucket name. |

There are no tracking-server credentials: **experiment tracking is file-based**
(no MLflow, no account). See below.

## How a run is recorded

Each run writes a self-contained record, so a comparison table is a file read
rather than a server query (`ml/src/common/tracking.py`):

```
artifacts/runs/
├── index.jsonl                      # one summary line per run, append-only
└── 20261024T101500Z-D-03-effnetb0-a1b2c3/
    ├── run.json                     # params, metrics, git SHA, env, artifacts
    ├── confusion_matrix.png
    └── effnetb0.pt
```

```python
from src.common.tracking import start_run, compare_runs

with start_run("D-03-effnetb0-strongaug", params={"lr": 3e-4, "seed": 42}) as run:
    ...
    run.log_metrics(macro_f1=0.94, accuracy=0.95)
    run.log_artifact("effusion_matrix_confusion.png")

best = compare_runs(metric="macro_f1")[0]
```

`run.json` is written at startup and rewritten at the end, so a Kaggle session
that is killed mid-run still leaves a record of what was attempted. Push
`artifacts/runs/` to Supabase Storage before closing — the index and the records
are what make experiments comparable across sessions.

## Run order

| Notebook | Phase | Purpose |
|---|---|---|
| `00_kaggle_setup.ipynb` | 0 | Environment report, package install, data check, secrets, run record, GPU smoke test |
| `01_plantvillage_eda.ipynb` | 1 | Class counts, duplicates, splits, `data_manifest.json` |
| `02_disease_training.ipynb` | 2 | D-01…D-06 from YAML configs |
| `03_yield_eda.ipynb` | 1 | Yield/weather/soil EDA, split definition |
| `04_yield_training.ipynb` | 3 | Y-00…Y-06 |
| `05_explainability_analysis.ipynb` | 4 | Grad-CAM sanity set, SHAP global/local |

Run `00` at the start of **every** session, then the training notebook. It is
idempotent.

## Session checklist

- [ ] Accelerator = GPU, Internet = On
- [ ] Dataset attached (check `image_count` in the setup notebook)
- [ ] Secrets readable (`secrets_present` all true)
- [ ] Run record written under `artifacts/runs/`
- [ ] Checkpointing enabled and verified with a one-epoch run
- [ ] Artifacts pushed to Supabase Storage **or** a Kaggle Dataset version before closing

## Local development

The same modules run locally on CPU for unit tests and CI (no Kaggle needed):

```bash
cd ml
python -m venv .venv
.venv/Scripts/activate           # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements-kaggle.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
python -c "from src.common.seed import seed_everything; print(seed_everything(42))"
```

`src/common/paths.py` picks `/kaggle/input` + `/kaggle/working` when on Kaggle
and `ml/data` + `ml/artifacts` otherwise, so training code never hard-codes a
path.

## Rules

- **Never `pip install torch` on Kaggle.** It can replace the CUDA-matched wheel.
  Install only what is missing, as `00_kaggle_setup.ipynb` does.
- **Never tune on the test split** (NFR-ML-006). Test is touched once, for the
  reported number.
- Every run records: seed, config, git SHA, data-manifest hash, metrics and
  artifact paths into `run.json`; the index in `runs/index.jsonl` is the
  comparison table (ML-001, DEV_PLAN §2.5).
- A model is not "done" until `docs/model_cards/` is updated and the export
  passes the parity check (ML-006, ML-010).
- **Mind the per-object size limit.** Supabase Storage's free plan caps a single
  object at 50 MB by default (raise it in *Storage → Settings* on a paid plan).
  Export ONNX or quantized weights for promotion; keep oversized training
  checkpoints in a Kaggle Dataset version instead of storage.
