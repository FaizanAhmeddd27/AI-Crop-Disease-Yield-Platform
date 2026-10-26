"""Export per-district yield history for production serving (DEV_PLAN Task 5.9).

Run on the ML/repo side:

    python -m ml.src.crop_yield.export_history_tables

Writes `history_tables.json` next to the exported production yield package:

    {
      "crops": {
        "wheat": {"2009": {"Faisalabad": {"yield_tha": 2.953, ...}, ...}, ...}
      },
      "trend_tha_per_year": {"wheat": {"Faisalabad": 0.012, ...}, ...},
      "first_season_year": 2008
    }

The backend yield service uses it to fill the leakage-free history features
(`yield_lag1_tha`, `yield_roll3_tha`, `yield_trend_tha_per_year`) from
*actual training-panel data* instead of hardcoded crop averages; for years
outside the panel it extrapolates with the per-district trend and falls back
to the crop mean.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.src.crop_yield.ingest import build_unified_yield_dataset


def export_history_tables(data_dir: Path | None = None) -> dict:
    """Build per-district, per-season yield history and trend tables."""
    panel = build_unified_yield_dataset(data_dir=data_dir)
    first_year = int(panel["season_year"].min())
    last_year = int(panel["season_year"].max())

    history: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    trend: dict[str, dict[str, float]] = {}

    for crop, group in panel.groupby("crop"):
        crop_history: dict[str, dict[str, dict[str, float]]] = {}
        crop_trend: dict[str, float] = {}
        for district, d_group in group.groupby("district"):
            series = (
                d_group[["season_year", "yield_tha"]]
                .dropna()
                .sort_values("season_year")
                .set_index("season_year")["yield_tha"]
            )
            # Per-district trend via simple OLS over seasons
            years = series.index.to_numpy(dtype=float)
            if len(years) >= 2:
                slope = float(pd.Series(series.to_numpy(), index=years).astype(float).diff().mean())
                x = years - years.mean()
                y = series.to_numpy(dtype=float) - series.to_numpy(dtype=float).mean()
                denom = float((x * x).sum()) or 1.0
                slope = float((x * y).sum() / denom)
            else:
                slope = 0.0
            crop_trend[district] = round(slope, 5)

            by_year: dict[str, dict[str, float]] = {}
            for year, value in series.items():
                by_year[str(int(year))] = {"yield_tha": round(float(value), 4)}
            crop_history[district] = by_year
        history[str(crop)] = crop_history
        trend[str(crop)] = crop_trend

    output = {
        "generated_from": "ml/src/crop_yield/ingest.build_unified_yield_dataset",
        "first_season_year": first_year,
        "last_season_year": last_year,
        "crops": history,
        "trend_tha_per_year": trend,
    }

    out_dir = Path(__file__).resolve().parents[2] / "artifacts" / "models" / "yield" / "v0.1.0"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "history_tables.json"
    out_path.write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(f"history tables written to {out_path}")
    print(f"panel seasons {first_year}..{last_year}; crops: {sorted(history.keys())}")
    return output


if __name__ == "__main__":
    export_history_tables()
