from __future__ import annotations

from pathlib import Path
import os

import numpy as np
import pandas as pd
from netCDF4 import Dataset, num2date


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_HISTORY = (
    ROOT
    / "e3sm_scm_run_scripts_baseline/baseline-output/scm_ARM97_baseline/run"
    / "case_scripts.eam.h0.1997-06-19-84585.nc"
)
BASELINE = Path(os.environ.get("SCM_BASELINE_HISTORY_FILE", DEFAULT_BASELINE_HISTORY))
STITCHED = ROOT / "mac_arm97_segment_design/mac_ARM97_26day_stitched_from_segments.nc"
OUT_DIR = ROOT / "mac_arm97_segment_design/comparison"
SUMMARY_CSV = OUT_DIR / "stitched_vs_baseline_variable_differences.csv"
TOP_CSV = OUT_DIR / "stitched_vs_baseline_top_differences.csv"

KEY_VARS = [
    "TREFHT",
    "TS",
    "PRECT",
    "TMQ",
    "LHFLX",
    "SHFLX",
    "FSNS",
    "FLNS",
    "CLDTOT",
    "PS",
]


def finite_stats(diff: np.ndarray) -> dict[str, float]:
    arr = np.ma.asarray(diff, dtype=np.float64)
    if np.ma.is_masked(arr):
        arr = arr.compressed()
    else:
        arr = np.asarray(arr)
    finite = np.isfinite(arr)
    if not finite.any():
        return {
            "n_finite": 0,
            "max_abs_diff": np.nan,
            "mean_abs_diff": np.nan,
            "rmse": np.nan,
            "mean_diff": np.nan,
        }
    x = np.asarray(arr[finite], dtype=np.float64)
    return {
        "n_finite": int(x.size),
        "max_abs_diff": float(np.max(np.abs(x))),
        "mean_abs_diff": float(np.mean(np.abs(x))),
        "rmse": float(np.sqrt(np.mean(x * x))),
        "mean_diff": float(np.mean(x)),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    with Dataset(BASELINE) as base, Dataset(STITCHED) as stitched:
        base_vars = set(base.variables)
        stitched_vars = set(stitched.variables)
        if base_vars != stitched_vars:
            missing = sorted(base_vars - stitched_vars)
            extra = sorted(stitched_vars - base_vars)
            raise RuntimeError(f"variable mismatch missing={missing} extra={extra}")

        bt = base.variables["time"]
        st = stitched.variables["time"]
        base_dates = num2date(bt[:], bt.units, getattr(bt, "calendar", "standard"), only_use_cftime_datetimes=False)
        stitched_dates = num2date(st[:], st.units, getattr(st, "calendar", "standard"), only_use_cftime_datetimes=False)
        if [str(x) for x in base_dates] != [str(x) for x in stitched_dates]:
            raise RuntimeError("time axis mismatch")

        for name in sorted(base.variables):
            bvar = base.variables[name]
            svar = stitched.variables[name]
            if bvar.dimensions != svar.dimensions:
                raise RuntimeError(f"dimension mismatch for {name}: {bvar.dimensions} != {svar.dimensions}")
            if "time" not in bvar.dimensions:
                continue
            if not np.issubdtype(bvar[:].dtype, np.number):
                continue

            b = np.ma.asarray(bvar[:])
            s = np.ma.asarray(svar[:])
            if b.shape != s.shape:
                raise RuntimeError(f"shape mismatch for {name}: {b.shape} != {s.shape}")

            valid = ~(np.ma.getmaskarray(b) | np.ma.getmaskarray(s))
            diff = np.ma.array(np.asarray(s, dtype=np.float64) - np.asarray(b, dtype=np.float64), mask=~valid)
            stats = finite_stats(diff)
            stats.update(
                {
                    "variable": name,
                    "dimensions": " ".join(bvar.dimensions),
                    "shape": "x".join(str(x) for x in b.shape),
                    "units": getattr(bvar, "units", ""),
                    "long_name": getattr(bvar, "long_name", ""),
                }
            )
            rows.append(stats)

    summary = pd.DataFrame(rows)
    summary = summary[
        [
            "variable",
            "dimensions",
            "shape",
            "units",
            "long_name",
            "n_finite",
            "max_abs_diff",
            "mean_abs_diff",
            "rmse",
            "mean_diff",
        ]
    ].sort_values("max_abs_diff", ascending=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    summary.head(30).to_csv(TOP_CSV, index=False)

    key_rows = summary[summary["variable"].isin(KEY_VARS)]
    print(f"time-dependent numeric variables compared: {len(summary)}")
    print(SUMMARY_CSV)
    print(TOP_CSV)
    print("\nKey variables:")
    if key_rows.empty:
        print("  none of requested key variables found")
    else:
        print(key_rows[["variable", "max_abs_diff", "mean_abs_diff", "rmse", "units"]].to_string(index=False))
    print("\nTop 10 by max_abs_diff:")
    print(summary.head(10)[["variable", "max_abs_diff", "mean_abs_diff", "rmse", "units"]].to_string(index=False))


if __name__ == "__main__":
    main()
