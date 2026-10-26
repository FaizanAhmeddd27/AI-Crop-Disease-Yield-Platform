"""Re-export the production yield package with CV+ conformal calibration (fast path).

Reuses the newest Y-03-xgboost run record for the card's point metrics instead of
retraining the whole experimental matrix. Run from the ml/ directory:

    python -m src.crop_yield.reexport_yield_package
"""

from __future__ import annotations

import json
from pathlib import Path

from src.common.paths import resolve_artifact_root
from src.crop_yield.train import export_production_yield_package


def newest_run_summary(exp_id: str) -> dict:
    dirs = sorted(
        (
            d
            for d in (resolve_artifact_root() / "runs").glob(f"*-{exp_id}-*")
            if (d / "eval_summary.json").exists()
        ),
        key=lambda d: d.name,
    )
    if not dirs:
        raise SystemExit(f"No run record found for {exp_id}")
    return json.loads((dirs[-1] / "eval_summary.json").read_text(encoding="utf-8"))


def main() -> Path:
    results = {"Y-03-xgboost": newest_run_summary("Y-03-xgboost")}
    return export_production_yield_package(results)


if __name__ == "__main__":
    path = main()
    card = json.loads((path / "card.json").read_text(encoding="utf-8"))
    calibration = json.loads((path / "calibration.json").read_text(encoding="utf-8"))
    print("Coverage (walk-forward conformal) on test:", calibration["test_interval_metrics"])
    print("card coverage_80_pct:", card["coverage_80_pct"])
