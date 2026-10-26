# ADR-0003 (revised): Train on Kaggle, serve on CPU

- **Status:** Accepted — supersedes the "Google Colab" wording of ADR-0003 in `ARCH.md` §15
- **Date:** 24 Oct 2026
- **Deciders:** project owner
- **Affects:** PRD §11 assumption 3, PRD §12 dependencies, ARCH §2 (AI Training),
  ARCH §6.5, ARCH §13, DEV_PLAN P0 task 0.8, P2/P3 Colab workflow, P9

## Context

The original plan trains on Google Colab (GPU) and persists checkpoints and
MLflow runs to Google Drive. Constraints that matter more than the choice of
host:

- Training is offline and disposable; nothing about the product depends on
  Colab specifically.
- Sessions are killed abruptly, so checkpoint-and-resume is mandatory
  regardless of host (DEV_PLAN risk R5).
- Experiment tracking must survive across sessions (requirement E2 / FR-M-001).

Colab's free tier has become unreliable for multi-hour runs (quota exhaustion,
forced disconnects), and the Drive mount adds failure modes on top.

## Decision

Train and experiment on **Kaggle Notebooks (GPU)**. Persist everything that must
outlive a session to **Supabase Storage** (checkpoints, exports, run records)
and/or a versioned **Kaggle Dataset**. (Provider choice: see
[ADR-0011](0011-supabase-storage.md); tracking is file-based per
[ADR-0012](0012-drop-mlflow.md).)

Production inference remains **CPU-only** in the FastAPI container, unchanged.

## Consequences

**Positive**
- Larger, more predictable weekly GPU allowance; a stable preinstalled
  PyTorch/timm/scikit-learn stack.
- Datasets are first-class versioned inputs (`/kaggle/input/<slug>`) instead of
  re-downloads or a Drive mount.
- No local GPU requirement for the team.

**Negative / mitigations**
- No persistent disk between sessions → mandatory checkpointing and an outward
  push (Supabase Storage) after every epoch; the setup notebook reports whether
  secrets are present so this fails loudly rather than silently.
- Files in `/kaggle/working` only survive if a version is committed, and are
  capped (~20 GB) → large checkpoints go to storage, not working storage.
- A ~12 h session cap and a weekly GPU quota → short, resumable experiments;
  a `time_budget_min` config field stops a run cleanly before the kill.
- Pip installs do not persist → `00_kaggle_setup.ipynb` installs only missing
  packages each session and must never reinstall `torch` (it can clobber the
  CUDA-matched wheel).
- Reasonable, but not identical, reproducibility story: the exact GPU model can
  differ between sessions (T4 vs P100), so GPU-specific results are recorded as
  an environment artifact rather than assumed.

## Alternatives considered

| Option | Why not |
|---|---|
| Google Colab (original ADR) | Unreliable quotas/disconnects; Drive mount adds failure modes |
| Kaggle + Kaggle Dataset as the only persistence | Dataset versioning is slow and awkward for many small checkpoints; Supabase Storage is already in the stack |
| Paid GPU VM / RunPod | Cost; unnecessary at this scale |
| Train on CPU locally | Infeasible for CNN/ViT fine-tuning |
