"""Lightweight experiment tracking: one JSON record per training run.

Replaces the MLflow dependency (see `docs/adr/0012-drop-mlflow.md`). There is no
server and no database: a run is a directory on disk, and a one-line summary is
appended to an index so runs can be compared by reading a file.

Layout:

    <artifact_root>/runs/
        index.jsonl                 # one summary object per run, append-only
        <run_id>/
            run.json                # params, metrics, environment, provenance
            <artifacts...>          # checkpoints, plots, reports

`run.json` is written when the run *starts* and rewritten when it finishes, so a
Kaggle session that is killed mid-training still leaves evidence of what ran.
Everything here is standard library only — importing this module must never pull
in torch, because the backend and CI use it without an ML stack.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.common.paths import resolve_artifact_root

INDEX_FILENAME = "index.jsonl"
RUN_FILENAME = "run.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_run_id(name: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name).strip("-")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{slug}-{uuid.uuid4().hex[:6]}"


def git_sha() -> tuple[str | None, bool]:
    """Return `(sha, is_dirty)`; `(None, False)` outside a git checkout.

    The project may be used as a plain folder (as during Phase 0), so this must
    never raise.
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if sha.returncode != 0:
            return None, False
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return sha.stdout.strip(), bool(dirty.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None, False


def environment_info() -> dict[str, Any]:
    """Interpreter, platform and installed ML package versions (no imports)."""
    from importlib import metadata

    packages = ("torch", "torchvision", "timm", "shap", "xgboost", "scikit-learn")
    versions: dict[str, str | None] = {}
    for name in packages:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "packages": versions,
    }


@dataclass
class Run:
    """A single training/evaluation run, persisted under `artifact_root/runs/`."""

    run_id: str
    name: str
    run_dir: Path
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    status: str = "running"
    started_at: str = field(default_factory=_utc_now)
    finished_at: str | None = None

    def log_params(self, **params: Any) -> None:
        self.params.update(params)

    def log_metrics(self, **metrics: float) -> None:
        self.metrics.update({key: float(value) for key, value in metrics.items()})

    def log_artifact(self, path: str | Path) -> None:
        """Record an artifact that lives inside the run directory."""
        candidate = Path(path)
        try:
            relative = candidate.resolve().relative_to(self.run_dir.resolve())
        except ValueError:
            relative = candidate
        self.artifacts.append(str(relative))

    def to_dict(self) -> dict[str, Any]:
        sha, dirty = git_sha()
        return {
            "run_id": self.run_id,
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "params": self.params,
            "metrics": self.metrics,
            "tags": self.tags,
            "artifacts": self.artifacts,
            "run_dir": str(self.run_dir),
            "git_sha": sha,
            "git_dirty": dirty,
            "environment": environment_info(),
        }

    def _flush(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / RUN_FILENAME).write_text(
            json.dumps(self.to_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    def _append_index(self) -> None:
        record = self.to_dict()
        summary = {
            key: record[key]
            for key in (
                "run_id",
                "name",
                "status",
                "started_at",
                "finished_at",
                "metrics",
                "git_sha",
                "run_dir",
            )
        }
        summary["params"] = record["params"]
        with (self.run_dir.parent / INDEX_FILENAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, default=str) + "\n")


@contextmanager
def start_run(
    name: str,
    *,
    params: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    artifact_root: str | Path | None = None,
) -> Iterator[Run]:
    """Context manager that records a run, even if the process dies mid-way.

    ```python
    with start_run("D-03-effnetb0-strongaug", params=cfg) as run:
        ...
        run.log_metrics(macro_f1=0.94)
        run.log_artifact("confusion_matrix.png")
    ```
    """
    root = resolve_artifact_root(artifact_root)
    run_id = _new_run_id(name)
    run = Run(
        run_id=run_id,
        name=name,
        run_dir=root / "runs" / run_id,
        params=dict(params or {}),
        tags=dict(tags or {}),
    )
    run._flush()  # a killed run still leaves a record behind
    try:
        yield run
    except BaseException:
        run.status = "failed"
        run.finished_at = _utc_now()
        run._flush()
        run._append_index()
        raise
    run.status = "completed"
    run.finished_at = _utc_now()
    run._flush()
    run._append_index()


def load_runs(artifact_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Read every run summary from the index, skipping unparsable lines."""
    root = resolve_artifact_root(artifact_root)
    index = root / "runs" / INDEX_FILENAME
    if not index.is_file():
        return []

    runs: list[dict[str, Any]] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def compare_runs(
    artifact_root: str | Path | None = None,
    *,
    metric: str,
    descending: bool = True,
) -> list[dict[str, Any]]:
    """Completed runs sorted by one metric, for the comparison tables."""
    runs = [run for run in load_runs(artifact_root) if run.get("status") == "completed"]
    return sorted(
        runs,
        key=lambda run: run.get("metrics", {}).get(metric, float("-inf")),
        reverse=descending,
    )
