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


DEFAULT_BASELINE_HISTORY = (
    ROOT
    / "e3sm_scm_run_scripts_baseline/baseline-output/scm_ARM97_baseline/run"
    / "case_scripts.eam.h0.1997-06-19-84585.nc"
)
DEFAULT_OBSERVATION = ROOT / "e3sm_scm_run_scripts_baseline/ARM97_iopfile_4scam.nc"
DEFAULT_OBS_MAP = ROOT / "notebooks/observed_variable_pairs.csv"
BASELINE = Path(os.environ.get("SCM_BASELINE_HISTORY_FILE", DEFAULT_BASELINE_HISTORY))
OBSERVATION = Path(os.environ.get("ARM97_IOP_FILE", DEFAULT_OBSERVATION))
OBS_MAP = Path(os.environ.get("ARM97_OBS_MAP", DEFAULT_OBS_MAP))
OUT_DIR = ROOT / "baseline_arm97_comparison"
FIG_DIR = OUT_DIR / "figures"
SURFACE_SUMMARY_CSV = OUT_DIR / "baseline_vs_observation_surface_summary.csv"
PROFILE_SUMMARY_CSV = OUT_DIR / "baseline_vs_observation_profile_summary.csv"


@dataclass(frozen=True)
class VarSpec:
    model: str
    obs_terms: tuple[str, ...]
    units: str
    scale_obs: float = 1.0
    obs_offset: float = 0.0
    description: str = ""


def as_series(var) -> np.ma.MaskedArray:
    data = np.ma.asarray(var[:], dtype=np.float64)
    if data.ndim == 1:
        return data
    axes = tuple(range(1, data.ndim))
    return np.ma.mean(data, axis=axes)


def filled(arr: np.ma.MaskedArray) -> np.ndarray:
    return np.asarray(np.ma.asarray(arr, dtype=np.float64).filled(np.nan), dtype=np.float64)


def load_obs_specs(path: Path) -> list[VarSpec]:
    df = pd.read_csv(path)
    specs = []
    for row in df.itertuples(index=False):
        terms = tuple(
            term.strip()
            for term in str(row.observation_source_variables).replace(";", ",").split(",")
            if term.strip()
        )
        if not terms:
            continue
        specs.append(
            VarSpec(
                model=str(row.model_variable),
                obs_terms=terms,
                units="" if pd.isna(row.units_after_conversion) else str(row.units_after_conversion),
                scale_obs=float(row.scale_obs),
                obs_offset=float(row.obs_offset),
                description="" if pd.isna(row.description) else str(row.description),
            )
        )
    return specs


def model_available(ds: Dataset, name: str) -> bool:
    return name in ds.variables or (name == "PRECT" and {"PRECC", "PRECL"}.issubset(ds.variables))


def model_series(ds: Dataset, name: str) -> np.ma.MaskedArray:
    if name in ds.variables:
        return as_series(ds.variables[name])
    if name == "PRECT" and {"PRECC", "PRECL"}.issubset(ds.variables):
        return as_series(ds.variables["PRECC"]) + as_series(ds.variables["PRECL"])
    raise KeyError(name)


def model_matrix(ds: Dataset, name: str) -> np.ndarray:
    if name in ds.variables:
        return np.asarray(ds.variables[name][:], dtype=np.float64).squeeze()
    if name == "PRECT" and {"PRECC", "PRECL"}.issubset(ds.variables):
        return (
            np.asarray(ds.variables["PRECC"][:], dtype=np.float64).squeeze()
            + np.asarray(ds.variables["PRECL"][:], dtype=np.float64).squeeze()
        )
    raise KeyError(name)


def obs_available(ds: Dataset, spec: VarSpec) -> bool:
    return all(term in ds.variables for term in spec.obs_terms)


def obs_series(ds: Dataset, spec: VarSpec) -> np.ma.MaskedArray:
    values = as_series(ds.variables[spec.obs_terms[0]])
    for term in spec.obs_terms[1:]:
        values = values - as_series(ds.variables[term])
    return values * spec.scale_obs + spec.obs_offset


def is_profile_spec(baseline: Dataset, obs: Dataset, spec: VarSpec) -> bool:
    obs_var = obs.variables[spec.obs_terms[0]]
    if "lev" in getattr(obs_var, "dimensions", ()):
        return True
    if spec.model in baseline.variables and "lev" in getattr(baseline.variables[spec.model], "dimensions", ()):
        return True
    return False


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
    if not OBS_MAP.exists():
        raise FileNotFoundError(OBS_MAP)

    FIG_DIR.mkdir(parents=True, exist_ok=True)

    surface_rows = []
    profile_rows = []
    figure_paths = []
    specs = load_obs_specs(OBS_MAP)

    with Dataset(BASELINE) as baseline, Dataset(OBSERVATION) as obs:
        bt = baseline.variables["time"]
        model_days = np.asarray(bt[:], dtype=np.float64)
        model_dates = np.array(
            num2date(model_days, bt.units, getattr(bt, "calendar", "standard"), only_use_cftime_datetimes=False)
        )

        obs_days = (np.asarray(obs.variables["tsec"][:], dtype=np.float64) - float(obs.variables["tsec"][0])) / 86400.0
        origin = model_dates[0] - timedelta(days=float(model_days[0]))
        obs_dates = np.array([origin + timedelta(days=float(x)) for x in obs_days])

        surface_specs = [spec for spec in specs if not is_profile_spec(baseline, obs, spec)]
        profile_specs = [spec for spec in specs if is_profile_spec(baseline, obs, spec)]

        for spec in surface_specs:
            if not model_available(baseline, spec.model):
                print(f"skip {spec.model}: missing baseline variable")
                continue
            missing_obs = [name for name in spec.obs_terms if name not in obs.variables]
            if missing_obs:
                print(f"skip {spec.model}: missing observation variables {missing_obs}")
                continue

            model_values = filled(model_series(baseline, spec.model))
            obs_native = filled(obs_series(obs, spec))
            obs_at_model = interpolate_obs(obs_days, obs_native, model_days)
            diff = model_values - obs_at_model

            row = stats(model_values, obs_at_model)
            row.update(
                {
                    "variable": spec.model,
                    "observation": ",".join(spec.obs_terms),
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

        for spec in profile_specs:
            if not model_available(baseline, spec.model) or not obs_available(obs, spec):
                print(f"skip profile {spec.model}: missing baseline or observation variable")
                continue

            model_values_by_level = model_matrix(baseline, spec.model)
            obs_values_by_level = np.asarray(obs.variables[spec.obs_terms[0]][:], dtype=np.float64).squeeze()

            for level_index, level_pa in enumerate(obs_levels_pa):
                model_at_level = interp_model_matrix_to_pressure(model_values_by_level, model_pressure, float(level_pa))
                obs_native = obs_values_by_level[:, level_index] * spec.scale_obs + spec.obs_offset
                obs_at_model = interpolate_obs(obs_days, obs_native, model_days)
                row = stats(model_at_level, obs_at_model)
                row.update(
                    {
                        "variable": spec.model,
                        "observation": ",".join(spec.obs_terms),
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
