# ADR-0012: Drop MLflow for file-based run records

- **Status:** Accepted — supersedes ADR-0009
- **Date:** 24 Oct 2026
- **Deciders:** project owner
- **Affects:** ARCH §1 (goals), §2 (stack), §2.1 (libraries), §4 (diagram + tree),
  §6.4–6.5 (registry, tracking), §8.2 (`model_versions`), §13 (config), §15 (ADRs);
  SRS §1.2, §1.4, §2.1–2.5, §3.8 (FR-M-001/002), §4.2, §6.1, §7 (ML-005), §9
  (UC-5), §10 (AC-11); PRD §1, §4 (E2), §6 (US-P6), §6.1, §7.1 (F9), §10, §12,
  §13 (Q3, glossary); DEV_PLAN tasks 0.3, 0.8, 0.9, 2.1, 3.5, 8.6, 9.2 and the
  phase checklists; `ml/` notebooks, secrets and requirements

## Context

Every specification so far assumes MLflow: runs are tracked in it, experiments are
"comparable in MLflow", the `model_versions` table stores an `mlflow_run_id`, and
AC-11 asks that each production model link to an MLflow run.

The actual constraint is narrower than the tooling implies. What the project
needs is:

1. evidence that each experiment happened (params, metrics, seed, git SHA, data
   manifest, environment);
2. a way to compare runs and pick a winner;
3. a traceable link from a promoted artifact back to the run that produced it.

That is a **record** plus an **index** — not a tracking server. MLflow adds a
server (or a file store that dies with the session), a client dependency, a
database schema, a UI, and a second thing to host. On Kaggle specifically, the
local file store is lost when the session ends, so the "zero setup" option does
not actually satisfy requirement 2 across sessions, and a hosted server is yet
another account and credential set.

## Decision

No experiment-tracking server anywhere in the stack. A run is a **directory**
plus **one line** in an append-only index, written by
`ml/src/common/tracking.py` (standard library only):

```
artifacts/runs/
├── index.jsonl                    # one summary object per run
└── 20261024T101500Z-D-03-a1b2c3/
    ├── run.json                   # params, metrics, tags, artifacts, git SHA, env
    ├── confusion_matrix.png
    └── effnetb0.pt
```

- `start_run(...)` is a context manager: `run.json` is flushed when the run
  **starts**, so a Kaggle session killed mid-training still leaves evidence.
- `load_runs()` / `compare_runs(metric=...)` read the index and produce the
  comparison tables that used to come from the MLflow UI.
- `run.json` carries `git_sha` (+ dirty flag), the seed, the data-manifest hash
  and the resolved package versions, which is what FR-M-001 actually asked for.
- Hyper-parameter searches write a parent run and one child run per trial,
  with the parent id stored in the child's `tags`.
- The `model_versions.run_id` column replaces `mlflow_run_id`, and promotion
  copies the winning `run.json` next to the exported artifact.
- `artifacts/runs/` is pushed to Supabase Storage with the rest of the artifacts
  before the Kaggle session closes (ADR-0011).

## Consequences

**Positive**
- One less service, one less account, one less credential set to rotate and
  explain; nothing to host or pay for.
- Works identically on a laptop, in CI and on Kaggle — no server reachability
  question, no "localhost is not visible from Kaggle" trap.
- The record is plain JSON in the same repository layout as the artifacts, so it
  survives a deleted session once pushed, and can be diffed, grepped or read by
  a script without a client library.
- The backend and CI can import the tracking helpers without pulling in torch or
  any ML dependency.
- Reproducibility is stronger, not weaker: git SHA and environment versions are
  captured in the same object as the metrics they belong to.

**Negative / mitigations**
- **No browsing UI.** *Mitigation:* `compare_runs()` prints a sorted table; the
  notebooks render the same data with pandas. For a single-semester project
  with tens of runs, a file read is sufficient — and the index is valid JSONL
  that any tool can consume later.
- **No artifact store or lineage graph.** *Mitigation:* artifacts live in the
  run directory and are pushed to Supabase Storage under the same `run_id`, so
  the path *is* the lineage.
- **We own the schema.** *Mitigation:* the schema is small and versioned by the
  code that writes it; unknown keys are ignored by readers.
- **Concurrent writes to `index.jsonl`.** *Mitigation:* runs are sequential in
  practice (one Kaggle session at a time); the writer appends a single line, so
  the failure mode is a corrupted last line, which `load_runs()` skips.
- **No native integration with tooling that expects MLflow.** *Mitigation:* if a
  course or reviewer later requires MLflow, the records can be replayed into it
  — they contain params, metrics and artifact paths — without re-running
  training.

## Alternatives considered

| Option | Why not |
|---|---|
| MLflow local file store (original ADR-0009) | Dies with the Kaggle session; cannot compare runs across sessions without a hosted server |
| Hosted MLflow (DagsHub / self-hosted) | Extra account, credential set and public service to maintain for a feature a JSON file already provides |
| Weights & Biases / Neptune | Same objections as hosted MLflow, plus a paid tier and a vendor dependency |
| TensorBoard | Good for live curves, poor as a durable, queryable record of params and provenance |
| A database table for runs | Requires the DB to be reachable from Kaggle; adds a migration and a write path for something that is naturally a file |
| Do nothing (no tracking) | Fails FR-M-001, FR-M-002 and AC-11; reproducibility claims become unverifiable |

## Rollback

`tracking.py` is the only place that knows where records live. Adopting any
tracking backend later means implementing the same `start_run` /
`load_runs` / `compare_runs` surface over that backend; existing `run.json`
files stay readable as the historical record.
