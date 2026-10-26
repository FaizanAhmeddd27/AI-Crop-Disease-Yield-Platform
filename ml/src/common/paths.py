"""Path resolution that works both on Kaggle and locally.

Kaggle mounts attached datasets read-only under `/kaggle/input/<slug>/` and only
`/kaggle/working` is captured when a version is committed. Locally the same code
reads `ml/data/` and writes `ml/artifacts/` (git-ignored). Nothing in the
training code should hard-code either location.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

KAGGLE_INPUT = Path("/kaggle/input")
KAGGLE_WORKING = Path("/kaggle/working")


def on_kaggle() -> bool:
    return KAGGLE_INPUT.is_dir()


def _repo_ml_dir() -> Path:
    # .../ml/src/common/paths.py -> .../ml
    return Path(__file__).resolve().parents[2]


def resolve_data_root(explicit: str | Path | None = None) -> Path:
    """Root of the read-only datasets.

    Precedence: explicit argument -> ML_DATA_ROOT env -> /kaggle/input ->
    repo `ml/data`.
    """
    if explicit:
        return Path(explicit)
    if env := os.environ.get("ML_DATA_ROOT"):
        return Path(env)
    if KAGGLE_INPUT.is_dir():
        return KAGGLE_INPUT
    return _repo_ml_dir() / "data"


def resolve_artifact_root(explicit: str | Path | None = None) -> Path:
    """Root for anything that must be persisted (checkpoints, plots, reports)."""
    if explicit:
        root = Path(explicit)
    elif env := os.environ.get("ML_ARTIFACT_ROOT"):
        root = Path(env)
    elif on_kaggle():
        root = KAGGLE_WORKING / "artifacts"
    else:
        root = _repo_ml_dir() / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def find_attached_dataset(glob_pattern: str) -> Path | None:
    """Return the first attached Kaggle dataset matching `glob_pattern`."""
    matches = sorted(KAGGLE_INPUT.glob(glob_pattern))
    return matches[0] if matches else None


@dataclass(frozen=True)
class DatasetLayout:
    """Conventional layout of a prepared dataset (ARCH §5.2)."""

    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def interim(self) -> Path:
        return self.root / "interim"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    @property
    def external(self) -> Path:
        return self.root / "external"

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    @property
    def manifest_file(self) -> Path:
        return self.manifests / "data_manifest.json"
