from __future__ import annotations

import matplotlib
from pathlib import Path
import os

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from netCDF4 import Dataset, num2date


ROOT = Path(__file__).resolve().parents[2]
BASELINE = (
    Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
    / "qmc_ARM97_baseline/run/case_scripts.eam.h0.1997-06-19-84585.nc"
)
STITCHED = ROOT / "mac_arm97_segment_design/mac_ARM97_26day_stitched_from_segments.nc"
OUT_DIR = ROOT / "mac_arm97_segment_design/comparison/figures"

VARS = ["TREFHT", "TMQ", "CLDTOT", "FSNS", "FLNS", "PS", "TS", "LHFLX", "SHFLX"]


def as_series(var):
    data = np.ma.asarray(var[:], dtype=np.float64)
    if data.ndim == 1:
        return data
    axes = tuple(range(1, data.ndim))
    return np.ma.mean(data, axis=axes)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with Dataset(BASELINE) as base, Dataset(STITCHED) as stitched:
        t = base.variables["time"]
        dates = num2date(t[:], t.units, getattr(t, "calendar", "standard"), only_use_cftime_datetimes=False)

        for name in VARS:
            if name not in base.variables:
                continue
            b = as_series(base.variables[name])
            s = as_series(stitched.variables[name])
            diff = s - b
            units = getattr(base.variables[name], "units", "")

            fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, height_ratios=[2, 1])
            axes[0].plot(dates, b, label="baseline", linewidth=1.2)
            axes[0].plot(dates, s, label="stitched", linewidth=1.0, alpha=0.85)
            axes[0].set_ylabel(f"{name} ({units})" if units else name)
            axes[0].legend(loc="best", frameon=False)
            axes[0].grid(True, alpha=0.25)

            axes[1].plot(dates, diff, color="tab:red", linewidth=1.0)
            axes[1].axhline(0, color="black", linewidth=0.8)
            axes[1].set_ylabel("stitched - baseline")
            axes[1].grid(True, alpha=0.25)

            fig.suptitle(f"{name}: stitched segments vs continuous baseline")
            fig.autofmt_xdate()
            fig.tight_layout()
            out = OUT_DIR / f"{name}_stitched_vs_baseline.png"
            fig.savefig(out, dpi=160)
            plt.close(fig)
            print(out)


if __name__ == "__main__":
    main()
