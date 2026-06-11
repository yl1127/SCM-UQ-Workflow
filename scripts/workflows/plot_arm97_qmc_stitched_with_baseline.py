#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import timedelta
import math
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local_cache/matplotlib-cache"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".local_cache"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from netCDF4 import Dataset, num2date


DEFAULT_QMC_STITCHED_DIR = (
    ROOT / "arm97_experiments_0602/arm97_qmc14x5_stitched_seed20260602/mac/stitched"
)
DEFAULT_STITCHED_BASELINE = (
    ROOT
    / "arm97_experiments_0602/arm97_stitched_baseline_seed20260605/mac/stitched"
    / "mac_ARM97_arm97_stitched_baseline_seed20260605_000_stitched_26day.nc"
)
DEFAULT_OBSERVATION = ROOT / "e3sm_scm_run_scripts_baseline/ARM97_iopfile_4scam.nc"
DEFAULT_OBS_MAP = ROOT / "notebooks/observed_variable_pairs.csv"

EXCLUDE_VARIABLES = {
    "time",
    "time_bnds",
    "date",
    "datesec",
    "date_written",
    "time_written",
    "ndcur",
    "nscur",
    "nsteph",
}


@dataclass(frozen=True)
class VarSpec:
    model: str
    obs_terms: tuple[str, ...] = ()
    units: str = ""
    scale_obs: float = 1.0
    obs_offset: float = 0.0
    description: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot ARM97 QMC stitched members against a stitched-method baseline."
    )
    parser.add_argument("--stitched-dir", default=str(DEFAULT_QMC_STITCHED_DIR))
    parser.add_argument("--baseline-file", default=str(DEFAULT_STITCHED_BASELINE))
    parser.add_argument("--observation-file", default=str(DEFAULT_OBSERVATION))
    parser.add_argument("--obs-map", default=str(DEFAULT_OBS_MAP))
    parser.add_argument("--out-dir", help="Defaults to STITCHED_DIR/batch_figures_stitched_baseline.")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--batch-index", type=int, default=0)
    parser.add_argument("--all-batches", action="store_true")
    parser.add_argument(
        "--variables",
        nargs="+",
        help="Optional model variables to plot. Defaults to all numeric time-dependent variables.",
    )
    return parser.parse_args()


def as_series(var) -> np.ma.MaskedArray:
    data = np.ma.asarray(var[:], dtype=np.float64)
    if data.ndim == 1:
        return data
    return np.ma.mean(data, axis=tuple(range(1, data.ndim)))


def filled(arr) -> np.ndarray:
    return np.asarray(np.ma.asarray(arr, dtype=np.float64).filled(np.nan), dtype=np.float64)


def load_time_axis(ds: Dataset) -> tuple[np.ndarray, np.ndarray]:
    t = ds.variables["time"]
    days = np.asarray(t[:], dtype=np.float64)
    dates = np.array(
        num2date(days, t.units, getattr(t, "calendar", "standard"), only_use_cftime_datetimes=False)
    )
    return days, dates


def is_numeric_time_var(var) -> bool:
    dims = getattr(var, "dimensions", ())
    if not dims or dims[0] != "time":
        return False
    try:
        return np.issubdtype(np.dtype(var.dtype), np.number)
    except TypeError:
        return False


def model_available(ds: Dataset, name: str) -> bool:
    return name in ds.variables or (name == "PRECT" and {"PRECC", "PRECL"}.issubset(ds.variables))


def model_is_numeric_time_var(ds: Dataset, name: str) -> bool:
    if name in ds.variables:
        return is_numeric_time_var(ds.variables[name])
    if name == "PRECT" and {"PRECC", "PRECL"}.issubset(ds.variables):
        return is_numeric_time_var(ds.variables["PRECC"]) and is_numeric_time_var(ds.variables["PRECL"])
    return False


def model_series(ds: Dataset, name: str) -> np.ndarray:
    if name in ds.variables:
        return filled(as_series(ds.variables[name]))
    if name == "PRECT" and {"PRECC", "PRECL"}.issubset(ds.variables):
        return filled(as_series(ds.variables["PRECC"]) + as_series(ds.variables["PRECL"]))
    raise KeyError(name)


def score(model_values: np.ndarray, reference_values: np.ndarray) -> dict[str, float | int]:
    finite = np.isfinite(model_values) & np.isfinite(reference_values)
    if not finite.any():
        return {"n": 0, "bias": np.nan, "mae": np.nan, "rmse": np.nan, "max_abs": np.nan}
    diff = model_values[finite] - reference_values[finite]
    return {
        "n": int(diff.size),
        "bias": float(np.mean(diff)),
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(np.sqrt(np.mean(diff * diff))),
        "max_abs": float(np.max(np.abs(diff))),
    }


def interp_reference(source_days: np.ndarray, source_values: np.ndarray, target_days: np.ndarray) -> np.ndarray:
    finite = np.isfinite(source_values)
    if finite.sum() < 2:
        return np.full_like(target_days, np.nan, dtype=np.float64)
    return np.interp(target_days, source_days[finite], source_values[finite], left=np.nan, right=np.nan)


def run_id_from_path(path: Path) -> int:
    match = re.search(r"_(\d{3})_stitched_26day\.nc$", path.name)
    if not match:
        raise ValueError(f"cannot parse run id from {path}")
    return int(match.group(1))


def discover_qmc_files(stitched_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(stitched_dir.glob("*_stitched_26day.nc")):
        try:
            rows.append({"run_id": run_id_from_path(path), "path": path})
        except ValueError:
            continue
    df = pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)
    if df.empty:
        raise FileNotFoundError(f"No QMC stitched files found in {stitched_dir}")
    return df


def select_batch(files: pd.DataFrame, batch_size: int, batch_index: int) -> pd.DataFrame:
    start = batch_index * batch_size
    selected = files.iloc[start : start + batch_size].copy()
    if selected.empty:
        n_batches = math.ceil(len(files) / batch_size)
        raise ValueError(f"batch {batch_index} is empty; valid range is 0..{n_batches - 1}")
    return selected.reset_index(drop=True)


def load_obs_specs(path: Path) -> dict[str, VarSpec]:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    specs = {}
    for row in df.itertuples(index=False):
        terms = tuple(
            term.strip()
            for term in str(row.observation_source_variables).replace(";", ",").split(",")
            if term.strip()
        )
        specs[str(row.model_variable)] = VarSpec(
            model=str(row.model_variable),
            obs_terms=terms,
            units="" if pd.isna(row.units_after_conversion) else str(row.units_after_conversion),
            scale_obs=float(row.scale_obs),
            obs_offset=float(row.obs_offset),
            description="" if pd.isna(row.description) else str(row.description),
        )
    return specs


def obs_available(obs: Dataset, spec: VarSpec) -> bool:
    return bool(spec.obs_terms) and all(term in obs.variables for term in spec.obs_terms)


def obs_series(obs: Dataset, spec: VarSpec) -> np.ndarray:
    values = filled(as_series(obs.variables[spec.obs_terms[0]]))
    for term in spec.obs_terms[1:]:
        values = values - filled(as_series(obs.variables[term]))
    return values * spec.scale_obs + spec.obs_offset


def discover_specs(
    baseline: Dataset,
    sample: Dataset,
    observation: Dataset,
    obs_specs: dict[str, VarSpec],
    include_variables: set[str] | None,
) -> list[VarSpec]:
    specs = []
    candidate_names = list(baseline.variables)
    for name in obs_specs:
        if name not in candidate_names and model_available(baseline, name):
            candidate_names.append(name)

    for name in candidate_names:
        if name in EXCLUDE_VARIABLES:
            continue
        if include_variables is not None and name not in include_variables:
            continue
        if not model_available(sample, name):
            continue
        if not model_is_numeric_time_var(baseline, name) or not model_is_numeric_time_var(sample, name):
            continue
        mapped = obs_specs.get(name)
        if mapped and obs_available(observation, mapped):
            specs.append(mapped)
        else:
            var = baseline.variables[name]
            specs.append(
                VarSpec(
                    model=name,
                    units=getattr(var, "units", "") or "",
                    description=getattr(var, "long_name", "") or name,
                )
            )
    if not specs:
        raise ValueError("No plottable variables discovered")
    return specs


def load_batch(
    baseline_file: Path,
    observation_file: Path,
    obs_map: Path,
    batch_files: pd.DataFrame,
    variables: list[str] | None,
) -> tuple[dict[str, dict], pd.DataFrame]:
    include = set(variables) if variables else None
    obs_specs = load_obs_specs(obs_map)
    data = {}
    rows = []

    with Dataset(baseline_file) as baseline, Dataset(batch_files.iloc[0]["path"]) as sample, Dataset(
        observation_file
    ) as obs:
        specs = discover_specs(baseline, sample, obs, obs_specs, include)

    with Dataset(baseline_file) as baseline, Dataset(observation_file) as obs:
        baseline_days, baseline_dates = load_time_axis(baseline)
        obs_days = (np.asarray(obs.variables["tsec"][:], dtype=np.float64) - float(obs.variables["tsec"][0])) / 86400.0
        origin = baseline_dates[0] - timedelta(days=float(baseline_days[0]))
        obs_dates = np.array([origin + timedelta(days=float(x)) for x in obs_days])

        for spec in specs:
            baseline_values = model_series(baseline, spec.model)
            has_obs = obs_available(obs, spec)
            obs_native = None
            obs_at_baseline = None
            baseline_diff_obs = None
            baseline_stats = None
            if has_obs:
                obs_native = obs_series(obs, spec)
                obs_at_baseline = interp_reference(obs_days, obs_native, baseline_days)
                baseline_diff_obs = baseline_values - obs_at_baseline
                baseline_stats = score(baseline_values, obs_at_baseline)

            members = []
            for row in batch_files.itertuples(index=False):
                with Dataset(row.path) as stitched:
                    if not model_available(stitched, spec.model):
                        continue
                    member_days, member_dates = load_time_axis(stitched)
                    values = model_series(stitched, spec.model)
                    baseline_at_member = interp_reference(baseline_days, baseline_values, member_days)
                    member = {
                        "run_id": int(row.run_id),
                        "dates": member_dates,
                        "values": values,
                        "baseline_at_member": baseline_at_member,
                        "diff_baseline": values - baseline_at_member,
                    }
                    if has_obs:
                        obs_at_member = interp_reference(obs_days, obs_native, member_days)
                        member["obs_at_member"] = obs_at_member
                        member["diff_obs"] = values - obs_at_member
                    members.append(member)

            if not members:
                continue

            for member in members:
                if has_obs:
                    comparison = "observation"
                    row_stats = score(member["values"], member["obs_at_member"])
                else:
                    comparison = "stitched_baseline"
                    row_stats = score(member["values"], member["baseline_at_member"])
                rows.append(
                    {
                        "baseline_label": "stitched_baseline",
                        "variable": spec.model,
                        "run_id": member["run_id"],
                        "comparison": comparison,
                        "observation": ",".join(spec.obs_terms),
                        "description": spec.description,
                        "units": spec.units,
                        **row_stats,
                    }
                )

            data[spec.model] = {
                "spec": spec,
                "has_obs": has_obs,
                "baseline_days": baseline_days,
                "baseline_dates": baseline_dates,
                "baseline_values": baseline_values,
                "obs_dates": obs_dates,
                "obs_native": obs_native,
                "baseline_diff_obs": baseline_diff_obs,
                "baseline_stats": baseline_stats,
                "members": members,
            }

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(["comparison", "variable", "rmse", "run_id"]).reset_index(drop=True)
    return data, summary


def export_pngs(data: dict[str, dict], out_dir: Path, batch_label: str) -> list[Path]:
    fig_dir = out_dir / batch_label
    fig_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, d in data.items():
        spec = d["spec"]
        fig, axes = plt.subplots(
            2,
            1,
            figsize=(12, 7),
            sharex=True,
            gridspec_kw={"height_ratios": [2.1, 1.0], "hspace": 0.08},
        )
        if d["has_obs"]:
            axes[0].plot(d["obs_dates"], d["obs_native"], color="0.20", lw=1.1, alpha=0.72, label="observation")
        axes[0].plot(d["baseline_dates"], d["baseline_values"], color="#145DA0", lw=2.0, label="stitched baseline")
        for member in d["members"]:
            axes[0].plot(member["dates"], member["values"], lw=0.9, alpha=0.55, label=f"qmc {member['run_id']:03d}")
        axes[0].set_ylabel(f"{name} ({spec.units})" if spec.units else name)
        axes[0].legend(loc="best", frameon=False, ncols=2, fontsize=8)
        axes[0].grid(True, alpha=0.25)

        if d["has_obs"]:
            axes[1].plot(
                d["baseline_dates"],
                d["baseline_diff_obs"],
                color="#C2410C",
                lw=1.4,
                label="stitched baseline - observation",
            )
            for member in d["members"]:
                axes[1].plot(member["dates"], member["diff_obs"], lw=0.75, alpha=0.45)
            diff_label = "model - obs"
        else:
            for member in d["members"]:
                axes[1].plot(member["dates"], member["diff_baseline"], lw=0.85, alpha=0.50)
            diff_label = "qmc - stitched baseline"
        axes[1].axhline(0, color="black", lw=0.8)
        axes[1].set_ylabel(f"{diff_label} ({spec.units})" if spec.units else diff_label)
        axes[1].set_xlabel("Time")
        axes[1].grid(True, alpha=0.25)

        run_ids = [m["run_id"] for m in d["members"]]
        if d["has_obs"]:
            s = d["baseline_stats"]
            subtitle = (
                f"{spec.description} | stitched baseline bias={s['bias']:.4g} {spec.units}, "
                f"RMSE={s['rmse']:.4g}, n={s['n']}"
            )
            title = f"{name}: observation, stitched baseline, QMC stitched runs {min(run_ids):03d}-{max(run_ids):03d}"
        else:
            subtitle = f"{spec.description} | lower panel is QMC - stitched baseline"
            title = f"{name}: stitched baseline, QMC stitched runs {min(run_ids):03d}-{max(run_ids):03d}"
        fig.suptitle(f"{title}\n{subtitle}", x=0.02, ha="left")
        fig.autofmt_xdate(rotation=0)
        fig.subplots_adjust(top=0.86, left=0.08, right=0.98, bottom=0.10)

        out = fig_dir / f"{name}_{batch_label}_observation_stitched_baseline_qmc.png"
        fig.savefig(out, dpi=160, bbox_inches="tight")
        plt.close(fig)
        paths.append(out)
    return paths


def main() -> None:
    args = parse_args()
    stitched_dir = Path(args.stitched_dir).expanduser().resolve()
    baseline_file = Path(args.baseline_file).expanduser().resolve()
    observation_file = Path(args.observation_file).expanduser().resolve()
    obs_map = Path(args.obs_map).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else stitched_dir / "batch_figures_stitched_baseline"

    if not baseline_file.exists():
        raise FileNotFoundError(baseline_file)
    if not observation_file.exists():
        raise FileNotFoundError(observation_file)

    files = discover_qmc_files(stitched_dir)
    n_batches = math.ceil(len(files) / args.batch_size)
    batch_indices = range(n_batches) if args.all_batches else [args.batch_index]
    summaries = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for batch_index in batch_indices:
        batch_files = select_batch(files, args.batch_size, batch_index)
        batch_label = f"batch{batch_index:02d}"
        data, summary = load_batch(baseline_file, observation_file, obs_map, batch_files, args.variables)
        paths = export_pngs(data, out_dir, batch_label)
        summary.insert(0, "batch_index", batch_index)
        summary_out = out_dir / f"surface_summary_{batch_label}.csv"
        summary.to_csv(summary_out, index=False)
        summaries.append(summary)
        print(f"{batch_label}: runs {batch_files['run_id'].tolist()} -> {len(paths)} figures")
        print(summary_out)

    combined = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    if args.all_batches:
        combined_out = out_dir / "surface_summary_all_batches.csv"
        combined.to_csv(combined_out, index=False)
        print(combined_out)


if __name__ == "__main__":
    main()
