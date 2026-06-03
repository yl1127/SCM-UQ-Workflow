from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local_cache/matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from netCDF4 import Dataset, num2date


BASELINE = (
    Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
    / "scm_ARM97_baseline/run/case_scripts.eam.h0.1997-06-19-84585.nc"
)
OBSERVATION = Path(os.environ.get("ARM97_IOP_FILE", "/path/to/ARM97_iopfile_4scam.nc"))
OUT_DIR = ROOT / "baseline_arm97_comparison"
FIG_DIR = OUT_DIR / "figures"
SURFACE_SUMMARY_CSV = OUT_DIR / "baseline_vs_observation_surface_summary.csv"
PROFILE_SUMMARY_CSV = OUT_DIR / "baseline_vs_observation_profile_summary.csv"


@dataclass(frozen=True)
class VarSpec:
    model: str
    obs: str
    units: str
    scale_obs: float = 1.0
    obs_offset: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class ProfileSpec:
    model: str
    obs: str
    units: str
    description: str = ""


SURFACE_VARS = [
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

PROFILE_VARS = [
    ProfileSpec("T", "T", "K", "temperature"),
    ProfileSpec("Q", "q", "kg/kg", "specific humidity"),
    ProfileSpec("U", "u", "m/s", "zonal wind"),
    ProfileSpec("V", "v", "m/s", "meridional wind"),
    ProfileSpec("OMEGA", "omega", "Pa/s", "pressure vertical velocity"),
    ProfileSpec("RELHUM", "rh", "%", "relative humidity"),
]


def as_series(var) -> np.ma.MaskedArray:
    data = np.ma.asarray(var[:], dtype=np.float64)
    if data.ndim == 1:
        return data
    axes = tuple(range(1, data.ndim))
    return np.ma.mean(data, axis=axes)


def filled(arr: np.ma.MaskedArray) -> np.ndarray:
    return np.asarray(np.ma.asarray(arr, dtype=np.float64).filled(np.nan), dtype=np.float64)


def obs_series(ds: Dataset, expression: str) -> np.ma.MaskedArray:
    if "-" in expression:
        left, right = expression.split("-", 1)
        return as_series(ds.variables[left]) - as_series(ds.variables[right])
    return as_series(ds.variables[expression])


def interpolate_obs(obs_days: np.ndarray, obs_values: np.ndarray, target_days: np.ndarray) -> np.ndarray:
    finite = np.isfinite(obs_values)
    if finite.sum() < 2:
        return np.full_like(target_days, np.nan, dtype=np.float64)
    return np.interp(target_days, obs_days[finite], obs_values[finite], left=np.nan, right=np.nan)


def stats(model_values: np.ndarray, obs_values: np.ndarray) -> dict[str, float]:
    finite = np.isfinite(model_values) & np.isfinite(obs_values)
    if not finite.any():
        return {
            "n": 0,
            "mean_obs": np.nan,
            "mean_baseline": np.nan,
            "bias": np.nan,
            "mae": np.nan,
            "rmse": np.nan,
            "max_abs": np.nan,
        }
    diff = model_values[finite] - obs_values[finite]
    return {
        "n": int(diff.size),
        "mean_obs": float(np.mean(obs_values[finite])),
        "mean_baseline": float(np.mean(model_values[finite])),
        "bias": float(np.mean(diff)),
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(np.sqrt(np.mean(diff * diff))),
        "max_abs": float(np.max(np.abs(diff))),
    }


def interp_model_matrix_to_pressure(values: np.ndarray, pressure: np.ndarray, target_pressure: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    pressure = np.asarray(pressure, dtype=np.float64)
    idx = np.sum(pressure < target_pressure, axis=1)
    valid = (idx > 0) & (idx < pressure.shape[1])
    out = np.full(values.shape[0], np.nan, dtype=np.float64)
    if not valid.any():
        return out

    rows = np.arange(values.shape[0])[valid]
    upper = idx[valid]
    lower = upper - 1
    p0 = pressure[rows, lower]
    p1 = pressure[rows, upper]
    v0 = values[rows, lower]
    v1 = values[rows, upper]
    ok = np.isfinite(p0) & np.isfinite(p1) & np.isfinite(v0) & np.isfinite(v1) & (p1 != p0)
    interp = np.full(rows.shape[0], np.nan, dtype=np.float64)
    interp[ok] = v0[ok] + (target_pressure - p0[ok]) * (v1[ok] - v0[ok]) / (p1[ok] - p0[ok])
    out[rows] = interp
    return out


def plot_surface(spec: VarSpec, dates, obs_dates, model_values, obs_native, diff, row_stats) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, height_ratios=[2, 1])
    axes[0].plot(obs_dates, obs_native, label="observation", color="0.25", linewidth=1.0, alpha=0.65)
    axes[0].plot(dates, model_values, label="baseline", color="#1261A6", linewidth=1.2)
    axes[0].set_ylabel(f"{spec.model} ({spec.units})")
    axes[0].legend(loc="best", frameon=False)
    axes[0].grid(True, alpha=0.25)

    axes[1].plot(dates, diff, color="#C2410C", linewidth=1.0)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_ylabel("baseline - obs")
    axes[1].grid(True, alpha=0.25)

    title = (
        f"{spec.model}: baseline vs observation"
        f"\n{spec.description} | bias={row_stats['bias']:.4g} {spec.units}, "
        f"RMSE={row_stats['rmse']:.4g}, MAE={row_stats['mae']:.4g}, n={row_stats['n']}"
    )
    fig.suptitle(title)
    fig.autofmt_xdate()
    fig.tight_layout()
    out = FIG_DIR / f"{spec.model}_baseline_vs_observation.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> None:
    if not BASELINE.exists():
        raise FileNotFoundError(BASELINE)
    if not OBSERVATION.exists():
        raise FileNotFoundError(OBSERVATION)

    FIG_DIR.mkdir(parents=True, exist_ok=True)

    surface_rows = []
    profile_rows = []
    figure_paths = []

    with Dataset(BASELINE) as baseline, Dataset(OBSERVATION) as obs:
        bt = baseline.variables["time"]
        model_days = np.asarray(bt[:], dtype=np.float64)
        model_dates = np.array(
            num2date(model_days, bt.units, getattr(bt, "calendar", "standard"), only_use_cftime_datetimes=False)
        )

        obs_days = (np.asarray(obs.variables["tsec"][:], dtype=np.float64) - float(obs.variables["tsec"][0])) / 86400.0
        origin = model_dates[0] - timedelta(days=float(model_days[0]))
        obs_dates = np.array([origin + timedelta(days=float(x)) for x in obs_days])

        for spec in SURFACE_VARS:
            if spec.model not in baseline.variables:
                print(f"skip {spec.model}: missing baseline variable")
                continue
            missing_obs = [name for name in spec.obs.split("-") if name not in obs.variables]
            if missing_obs:
                print(f"skip {spec.model}: missing observation variables {missing_obs}")
                continue

            model_values = filled(as_series(baseline.variables[spec.model]))
            obs_native = filled(obs_series(obs, spec.obs)) * spec.scale_obs + spec.obs_offset
            obs_at_model = interpolate_obs(obs_days, obs_native, model_days)
            diff = model_values - obs_at_model

            row = stats(model_values, obs_at_model)
            row.update(
                {
                    "variable": spec.model,
                    "observation": spec.obs,
                    "description": spec.description,
                    "units": spec.units,
                }
            )
            surface_rows.append(row)
            figure_paths.append(plot_surface(spec, model_dates, obs_dates, model_values, obs_native, diff, row))

        obs_levels_pa = np.asarray(obs.variables["lev"][:], dtype=np.float64)
        p0 = float(np.asarray(baseline.variables["P0"][...]))
        hyam = np.asarray(baseline.variables["hyam"][:], dtype=np.float64)
        hybm = np.asarray(baseline.variables["hybm"][:], dtype=np.float64)
        ps = np.asarray(baseline.variables["PS"][:], dtype=np.float64).squeeze()
        model_pressure = hyam[None, :] * p0 + hybm[None, :] * ps[:, None]

        for spec in PROFILE_VARS:
            if spec.model not in baseline.variables or spec.obs not in obs.variables:
                print(f"skip profile {spec.model}: missing baseline or observation variable")
                continue

            model_matrix = np.asarray(baseline.variables[spec.model][:], dtype=np.float64).squeeze()
            obs_matrix = np.asarray(obs.variables[spec.obs][:], dtype=np.float64).squeeze()

            for level_index, level_pa in enumerate(obs_levels_pa):
                model_at_level = interp_model_matrix_to_pressure(model_matrix, model_pressure, float(level_pa))
                obs_native = obs_matrix[:, level_index]
                obs_at_model = interpolate_obs(obs_days, obs_native, model_days)
                row = stats(model_at_level, obs_at_model)
                row.update(
                    {
                        "variable": spec.model,
                        "observation": spec.obs,
                        "description": spec.description,
                        "level_pa": float(level_pa),
                        "level_hpa": float(level_pa / 100.0),
                        "units": spec.units,
                    }
                )
                profile_rows.append(row)

    surface = pd.DataFrame(surface_rows)
    if not surface.empty:
        surface = surface[
            [
                "variable",
                "observation",
                "description",
                "units",
                "n",
                "mean_obs",
                "mean_baseline",
                "bias",
                "mae",
                "rmse",
                "max_abs",
            ]
        ].sort_values("rmse", ascending=False)
        surface.to_csv(SURFACE_SUMMARY_CSV, index=False)

    profile = pd.DataFrame(profile_rows)
    if not profile.empty:
        profile = profile[
            [
                "variable",
                "observation",
                "description",
                "level_pa",
                "level_hpa",
                "units",
                "n",
                "mean_obs",
                "mean_baseline",
                "bias",
                "mae",
                "rmse",
                "max_abs",
            ]
        ].sort_values(["variable", "level_pa"])
        profile.to_csv(PROFILE_SUMMARY_CSV, index=False)

    print(f"surface summary: {SURFACE_SUMMARY_CSV}")
    print(f"profile summary: {PROFILE_SUMMARY_CSV}")
    print(f"figures: {FIG_DIR}")
    print("\nSurface variables sorted by RMSE:")
    if surface.empty:
        print("no surface variables compared")
    else:
        print(surface[["variable", "bias", "mae", "rmse", "units", "n"]].to_string(index=False))

    if not profile.empty:
        best_levels = profile.loc[profile.groupby("variable")["rmse"].idxmin()]
        worst_levels = profile.loc[profile.groupby("variable")["rmse"].idxmax()]
        print("\nProfile level with smallest RMSE per variable:")
        print(best_levels[["variable", "level_hpa", "bias", "mae", "rmse", "units", "n"]].to_string(index=False))
        print("\nProfile level with largest RMSE per variable:")
        print(worst_levels[["variable", "level_hpa", "bias", "mae", "rmse", "units", "n"]].to_string(index=False))


if __name__ == "__main__":
    main()
