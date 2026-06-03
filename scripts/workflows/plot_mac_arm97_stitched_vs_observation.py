from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local_cache/matplotlib-cache"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".local_cache"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from netCDF4 import Dataset, num2date


STITCHED = ROOT / "mac_arm97_segment_design/mac_ARM97_26day_stitched_from_segments.nc"
DEFAULT_OBSERVATION = ROOT / "e3sm_scm_run_scripts_baseline/ARM97_iopfile_4scam.nc"
OBSERVATION = Path(os.environ.get("ARM97_IOP_FILE", DEFAULT_OBSERVATION))
OUT_DIR = ROOT / "mac_arm97_segment_design/comparison/figures_observation"
SUMMARY_CSV = ROOT / "mac_arm97_segment_design/comparison/stitched_vs_observation_summary.csv"


@dataclass(frozen=True)
class VarSpec:
    model: str
    obs: str
    units: str
    scale_obs: float = 1.0
    obs_offset: float = 0.0
    description: str = ""


VARS = [
    VarSpec("TREFHT", "Tsair", "K", description="2 m air temperature"),
    VarSpec("TS", "Tg", "K", description="surface/ground temperature"),
    VarSpec("TMQ", "prew", "kg/m2", scale_obs=10.0, description="precipitable water"),
    VarSpec("CLDTOT", "totcld", "1", scale_obs=0.01, description="total cloud fraction"),
    VarSpec("PS", "Ps", "Pa", description="surface pressure"),
    VarSpec("LHFLX", "lhflx", "W/m2", description="latent heat flux"),
    VarSpec("SHFLX", "shflx", "W/m2", description="sensible heat flux"),
    VarSpec("FSNS", "srfswdn-srfswup", "W/m2", description="surface net shortwave flux"),
    VarSpec("FLNS", "srflwup-srflwdn", "W/m2", description="surface net longwave flux"),
    VarSpec("FSDS", "srfswdn", "W/m2", description="surface downwelling shortwave flux"),
    VarSpec("FLDS", "srflwdn", "W/m2", description="surface downwelling longwave flux"),
]


def as_series(var) -> np.ma.MaskedArray:
    data = np.ma.asarray(var[:], dtype=np.float64)
    if data.ndim == 1:
        return data
    axes = tuple(range(1, data.ndim))
    return np.ma.mean(data, axis=axes)


def obs_series(ds: Dataset, expression: str) -> np.ma.MaskedArray:
    if "-" in expression:
        left, right = expression.split("-", 1)
        return as_series(ds.variables[left]) - as_series(ds.variables[right])
    return as_series(ds.variables[expression])


def filled_for_interp(arr: np.ma.MaskedArray) -> np.ndarray:
    masked = np.ma.asarray(arr, dtype=np.float64)
    data = masked.filled(np.nan)
    return np.asarray(data, dtype=np.float64)


def interpolate_obs(obs_days: np.ndarray, obs_values: np.ndarray, target_days: np.ndarray) -> np.ndarray:
    finite = np.isfinite(obs_values)
    if finite.sum() < 2:
        return np.full_like(target_days, np.nan, dtype=np.float64)
    return np.interp(target_days, obs_days[finite], obs_values[finite], left=np.nan, right=np.nan)


def finite_stats(diff: np.ndarray) -> dict[str, float]:
    finite = np.isfinite(diff)
    if not finite.any():
        return {
            "n_finite": 0,
            "mean_obs": np.nan,
            "mean_stitched": np.nan,
            "mean_bias": np.nan,
            "mean_abs_diff": np.nan,
            "rmse": np.nan,
            "max_abs_diff": np.nan,
        }
    x = np.asarray(diff[finite], dtype=np.float64)
    return {
        "n_finite": int(x.size),
        "mean_bias": float(np.mean(x)),
        "mean_abs_diff": float(np.mean(np.abs(x))),
        "rmse": float(np.sqrt(np.mean(x * x))),
        "max_abs_diff": float(np.max(np.abs(x))),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    with Dataset(STITCHED) as stitched, Dataset(OBSERVATION) as obs:
        st = stitched.variables["time"]
        model_days = np.asarray(st[:], dtype=np.float64)
        model_dates = num2date(
            model_days,
            st.units,
            getattr(st, "calendar", "standard"),
            only_use_cftime_datetimes=False,
        )
        obs_days = (np.asarray(obs.variables["tsec"][:], dtype=np.float64) - float(obs.variables["tsec"][0])) / 86400.0
        origin = model_dates[0] - timedelta(days=float(model_days[0]))
        obs_dates = np.array([origin + timedelta(days=float(x)) for x in obs_days])

        for spec in VARS:
            if spec.model not in stitched.variables:
                print(f"skip {spec.model}: not in stitched file")
                continue
            obs_names = spec.obs.split("-")
            missing = [name for name in obs_names if name not in obs.variables]
            if missing:
                print(f"skip {spec.model}: missing observation variables {missing}")
                continue

            model_values = filled_for_interp(as_series(stitched.variables[spec.model]))
            observed_raw = filled_for_interp(obs_series(obs, spec.obs))
            observed_raw = observed_raw * spec.scale_obs + spec.obs_offset
            observed_at_model = interpolate_obs(obs_days, observed_raw, model_days)
            diff = model_values - observed_at_model

            stats = finite_stats(diff)
            finite = np.isfinite(model_values) & np.isfinite(observed_at_model)
            stats.update(
                {
                    "model_variable": spec.model,
                    "observation_variable": spec.obs,
                    "description": spec.description,
                    "units": spec.units,
                    "mean_obs": float(np.mean(observed_at_model[finite])) if finite.any() else np.nan,
                    "mean_stitched": float(np.mean(model_values[finite])) if finite.any() else np.nan,
                }
            )
            rows.append(stats)

            fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, height_ratios=[2, 1])
            axes[0].plot(obs_dates, observed_raw, label="observation", color="black", linewidth=1.0, alpha=0.55)
            axes[0].plot(model_dates, model_values, label="stitched", color="tab:blue", linewidth=1.1, alpha=0.9)
            axes[0].set_ylabel(f"{spec.model} ({spec.units})")
            axes[0].legend(loc="best", frameon=False)
            axes[0].grid(True, alpha=0.25)

            axes[1].plot(model_dates, diff, color="tab:red", linewidth=1.0)
            axes[1].axhline(0, color="black", linewidth=0.8)
            axes[1].set_ylabel("stitched - obs")
            axes[1].grid(True, alpha=0.25)

            title = f"{spec.model}: stitched vs observation"
            if spec.description:
                title += f" ({spec.description})"
            fig.suptitle(title)
            fig.autofmt_xdate()
            fig.tight_layout()
            out = OUT_DIR / f"{spec.model}_stitched_vs_observation.png"
            fig.savefig(out, dpi=160)
            plt.close(fig)
            print(out)

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary[
            [
                "model_variable",
                "observation_variable",
                "description",
                "units",
                "n_finite",
                "mean_obs",
                "mean_stitched",
                "mean_bias",
                "mean_abs_diff",
                "rmse",
                "max_abs_diff",
            ]
        ].sort_values("rmse", ascending=False)
        summary.to_csv(SUMMARY_CSV, index=False)
        print(SUMMARY_CSV)


if __name__ == "__main__":
    main()
