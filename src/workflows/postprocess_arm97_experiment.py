#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import os
import shutil
import subprocess
from typing import Any

import numpy as np
import pandas as pd

try:
    from netCDF4 import Dataset, date2num, num2date
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing Python package netCDF4. Install it with:\n"
        "  python3 -m pip install -r requirements.txt"
    ) from exc


ROOT = Path(__file__).resolve().parents[2]

SCALAR_VARS = [
    "TREFHT",
    "TMQ",
    "CLDTOT",
    "FSNS",
    "FLNS",
    "LHFLX",
    "SHFLX",
    "PS",
    "TS",
]
PROFILE_VARS = ["T", "Q", "CLOUD", "CLDICE", "CLDLIQ"]
PRECIP_VARS = ["PRECC", "PRECL"]
GOOD_STATUSES = {"success", "skipped_existing_success"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stitch segmented ARM97 SCM experiment outputs by sample."
    )
    parser.add_argument(
        "--experiment-dir",
        required=True,
        help="Experiment platform directory, for example arm97_experiments_0602/.../mac.",
    )
    parser.add_argument("--manifest", help="Script manifest CSV. Defaults to design/*_script_manifest.csv.")
    parser.add_argument("--samples", help="Samples CSV. Defaults to design/*_samples.csv.")
    parser.add_argument("--status", help="Run status CSV. Defaults to design/experiment_run_status.csv.")
    parser.add_argument("--scm-runs", default=os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
    parser.add_argument("--stitched-dir", help="Output directory for stitched NetCDF files.")
    parser.add_argument("--metrics-dir", help="Output directory for metrics CSVs.")
    parser.add_argument(
        "--stitch-backend",
        choices=["python", "nco"],
        default="python",
        help="Use Python NetCDF copying or NCO ncks/ncrcat for segment stitching.",
    )
    parser.add_argument("--ncks", default=os.environ.get("NCKS"), help="Path to ncks. Defaults to PATH lookup.")
    parser.add_argument("--ncrcat", default=os.environ.get("NCRCAT"), help="Path to ncrcat. Defaults to PATH lookup.")
    parser.add_argument(
        "--keep-nco-temp",
        action="store_true",
        help="Keep temporary NCO segment files under stitched/_nco_segments.",
    )
    parser.add_argument(
        "--allow-missing-status",
        action="store_true",
        help="Skip status validation and rely on history files being present.",
    )
    return parser.parse_args()


def one_match(pattern: str, root: Path, *, exclude: tuple[str, ...] = ()) -> Path:
    matches = [path for path in sorted(root.glob(pattern)) if not any(token in path.name for token in exclude)]
    if len(matches) != 1:
        raise SystemExit(f"expected one match for {root / pattern}, found {len(matches)}")
    return matches[0]


def output_datetimes(ds: Dataset) -> list[datetime]:
    time = ds.variables["time"]
    units = getattr(time, "units")
    calendar = getattr(time, "calendar", "standard")
    dates = num2date(time[:], units=units, calendar=calendar, only_use_cftime_datetimes=False)
    return [datetime(d.year, d.month, d.day, d.hour, d.minute, d.second) for d in dates]


def values_as_datetimes(ds: Dataset, name: str, values: np.ndarray) -> np.ndarray:
    var = ds.variables[name]
    time_var = ds.variables["time"]
    units = getattr(var, "units", getattr(time_var, "units"))
    calendar = getattr(var, "calendar", getattr(time_var, "calendar", "standard"))
    flat = np.asarray(values).reshape(-1)
    dates = num2date(flat, units=units, calendar=calendar, only_use_cftime_datetimes=False)
    return np.asarray(
        [datetime(d.year, d.month, d.day, d.hour, d.minute, d.second) for d in dates],
        dtype=object,
    ).reshape(np.asarray(values).shape)


def history_file(scm_runs: Path, case_name: str) -> Path:
    run_dir = scm_runs / case_name / "run"
    files = sorted(run_dir.glob("*.eam.h0.*.nc"))
    if not files:
        raise FileNotFoundError(f"missing history file for {case_name}: {run_dir}")
    return files[-1]


def create_output(first: Dataset, out_path: Path, time_len: int, sample_case: str) -> Dataset:
    if out_path.exists():
        out_path.unlink()
    out = Dataset(out_path, "w", format=first.data_model)

    for name, dim in first.dimensions.items():
        out.createDimension(name, time_len if name == "time" else len(dim))

    for name, value in first.__dict__.items():
        setattr(out, name, value)
    out.setncattr("sample_case", sample_case)
    out.setncattr(
        "segment_stitching",
        "26 daily 36h segment runs; first 12h discarded; final 24h kept from each segment; duplicate boundary times removed",
    )

    for name, var in first.variables.items():
        kwargs: dict[str, Any] = {}
        fill_value = getattr(var, "_FillValue", None)
        if fill_value is not None:
            kwargs["fill_value"] = fill_value
        out_var = out.createVariable(name, var.datatype, var.dimensions, **kwargs)
        for attr in var.ncattrs():
            if attr == "_FillValue":
                continue
            out_var.setncattr(attr, var.getncattr(attr))
    return out


def copy_static_variables(first: Dataset, out: Dataset) -> None:
    for name, var in first.variables.items():
        if "time" not in var.dimensions:
            out.variables[name][:] = var[:]


def copy_time_records(src: Dataset, out: Dataset, src_indices: list[int], out_start: int) -> None:
    out_time = out.variables["time"]
    out_time_units = getattr(out_time, "units")
    out_calendar = getattr(out_time, "calendar", "standard")

    for name, var in src.variables.items():
        if "time" not in var.dimensions:
            continue
        axis = var.dimensions.index("time")
        data = np.take(var[:], src_indices, axis=axis)
        if name == "time":
            dts = output_datetimes(src)
            data = np.asarray(
                date2num([dts[i] for i in src_indices], units=out_time_units, calendar=out_calendar)
            )
        elif name == "time_bnds":
            dts = values_as_datetimes(src, name, data)
            data = np.asarray(
                date2num(dts.reshape(-1).tolist(), units=out_time_units, calendar=out_calendar)
            ).reshape(data.shape)
        target = [slice(None)] * data.ndim
        target[axis] = slice(out_start, out_start + len(src_indices))
        out.variables[name][tuple(target)] = data


def selected_records_for_sample(
    scm_runs: Path, sample_manifest: pd.DataFrame
) -> list[tuple[str, Path, list[int]]]:
    selected: list[tuple[str, Path, list[int]]] = []
    seen: set[datetime] = set()
    for _, row in sample_manifest.sort_values("segment_index").iterrows():
        case_name = str(row["case"])
        keep_start = datetime.fromisoformat(str(row["keep_start_datetime"]))
        keep_end = datetime.fromisoformat(str(row["keep_end_datetime"]))
        path = history_file(scm_runs, case_name)
        with Dataset(path) as ds:
            dts = output_datetimes(ds)
        indices = []
        for i, dt in enumerate(dts):
            if keep_start <= dt <= keep_end and dt not in seen:
                indices.append(i)
                seen.add(dt)
        if not indices:
            raise RuntimeError(f"no keep records selected for {case_name}")
        selected.append((case_name, path, indices))
    return selected


def stitch_sample(scm_runs: Path, stitched_dir: Path, sample_case: str, sample_manifest: pd.DataFrame) -> Path:
    out_path = stitched_dir / f"{sample_case}_stitched_26day.nc"
    selected = selected_records_for_sample(scm_runs, sample_manifest)
    total_records = sum(len(indices) for _, _, indices in selected)

    with Dataset(selected[0][1]) as first:
        out = create_output(first, out_path, total_records, sample_case)
        copy_static_variables(first, out)
        out.close()

    offset = 0
    with Dataset(out_path, "a") as out:
        for _, path, indices in selected:
            with Dataset(path) as src:
                copy_time_records(src, out, indices, offset)
            offset += len(indices)
    return out_path


def resolve_executable(name: str, explicit_path: str | None) -> str:
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return str(path)
        raise SystemExit(f"{name} not found: {explicit_path}")
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise SystemExit(f"{name} not found on PATH. Set --{name} or ${name.upper()}.")


def run_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        joined = " ".join(command)
        raise SystemExit(f"command failed with exit code {exc.returncode}: {joined}") from exc


def consecutive_range(indices: list[int], case_name: str) -> tuple[int, int]:
    start = indices[0]
    end = indices[-1]
    expected = list(range(start, end + 1))
    if indices != expected:
        raise RuntimeError(
            f"NCO backend requires consecutive time records for {case_name}; got {indices[:5]}...{indices[-5:]}"
        )
    return start, end


def stitch_sample_nco(
    scm_runs: Path,
    stitched_dir: Path,
    sample_case: str,
    sample_manifest: pd.DataFrame,
    *,
    ncks: str,
    ncrcat: str,
    keep_temp: bool,
) -> Path:
    out_path = stitched_dir / f"{sample_case}_stitched_26day.nc"
    selected = selected_records_for_sample(scm_runs, sample_manifest)
    temp_dir = stitched_dir / "_nco_segments" / sample_case
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    segment_files: list[Path] = []
    for segment_number, (case_name, history_path, indices) in enumerate(selected):
        start, end = consecutive_range(indices, case_name)
        segment_path = temp_dir / f"{segment_number:03d}_{case_name}_keep.nc"
        run_command(
            [
                ncks,
                "-O",
                "--mk_rec_dmn",
                "time",
                "-d",
                f"time,{start},{end}",
                str(history_path),
                str(segment_path),
            ]
        )
        segment_files.append(segment_path)

    if out_path.exists():
        out_path.unlink()
    run_command([ncrcat, "-O", *[str(path) for path in segment_files], str(out_path)])

    with Dataset(out_path, "a") as out:
        out.setncattr("sample_case", sample_case)
        out.setncattr(
            "segment_stitching",
            "NCO ncks/ncrcat; 26 daily 36h segment runs; first 12h discarded; "
            "final 24h kept from each segment; duplicate boundary times removed",
        )

    if not keep_temp:
        shutil.rmtree(temp_dir)
        if not any(temp_dir.parent.iterdir()):
            temp_dir.parent.rmdir()
    return out_path


def as_float_array(ds: Dataset, var_name: str) -> np.ma.MaskedArray:
    return np.ma.masked_invalid(np.ma.asarray(ds.variables[var_name][:], dtype=float))


def add_basic_stats(metrics: dict[str, Any], name: str, data: np.ma.MaskedArray) -> None:
    compressed = data.compressed()
    if compressed.size == 0:
        return
    metrics[f"{name}_mean"] = float(np.mean(compressed))
    metrics[f"{name}_std"] = float(np.std(compressed))
    metrics[f"{name}_min"] = float(np.min(compressed))
    metrics[f"{name}_max"] = float(np.max(compressed))


def extract_metrics(sample_index: int, sample_case: str, path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "sample_index": sample_index,
        "case": sample_case,
        "stitched_file": str(path),
    }
    with Dataset(path) as ds:
        dts = output_datetimes(ds)
        metrics["time_records"] = len(dts)
        metrics["time_start"] = dts[0].isoformat(sep=" ")
        metrics["time_end"] = dts[-1].isoformat(sep=" ")

        for var in SCALAR_VARS:
            if var in ds.variables:
                add_basic_stats(metrics, var, as_float_array(ds, var))
        for var in PROFILE_VARS:
            if var in ds.variables:
                add_basic_stats(metrics, var, as_float_array(ds, var))
        for var in PRECIP_VARS:
            if var in ds.variables:
                data = as_float_array(ds, var)
                add_basic_stats(metrics, var, data)
                metrics[f"{var}_mean_mm_day"] = float(np.ma.mean(data) * 86400.0 * 1000.0)
        if all(var in ds.variables for var in PRECIP_VARS):
            prect = as_float_array(ds, "PRECC") + as_float_array(ds, "PRECL")
            add_basic_stats(metrics, "PRECT", prect)
            metrics["PRECT_mean_mm_day"] = float(np.ma.mean(prect) * 86400.0 * 1000.0)
    return metrics


def validate_status(status_path: Path, manifest: pd.DataFrame, allow_missing_status: bool) -> None:
    if allow_missing_status:
        return
    if not status_path.exists():
        raise SystemExit(f"missing status CSV: {status_path}")
    status = pd.read_csv(status_path)
    manifest_cases = set(manifest["case"].astype(str))
    status = status[status["case"].astype(str).isin(manifest_cases)]
    if len(status) != len(manifest_cases):
        raise SystemExit(f"status rows do not match manifest: {len(status)} vs {len(manifest_cases)}")
    bad = status[~status["status"].astype(str).isin(GOOD_STATUSES)]
    if not bad.empty:
        raise SystemExit(f"refusing to stitch non-success cases:\n{bad[['case', 'status']].to_string(index=False)}")


def main() -> None:
    args = parse_args()
    experiment_dir = Path(args.experiment_dir).resolve()
    design_dir = experiment_dir / "design"
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else one_match("*_script_manifest.csv", design_dir, exclude=("_sample",))
    )
    samples_path = Path(args.samples) if args.samples else one_match("*_samples.csv", design_dir)
    status_path = Path(args.status) if args.status else design_dir / "experiment_run_status.csv"
    scm_runs = Path(args.scm_runs)
    stitched_dir = Path(args.stitched_dir) if args.stitched_dir else experiment_dir / "stitched"
    metrics_dir = Path(args.metrics_dir) if args.metrics_dir else experiment_dir / "metrics"

    stitched_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(manifest_path)
    samples = pd.read_csv(samples_path)
    validate_status(status_path, manifest, args.allow_missing_status)

    ncks = ncrcat = None
    if args.stitch_backend == "nco":
        ncks = resolve_executable("ncks", args.ncks)
        ncrcat = resolve_executable("ncrcat", args.ncrcat)

    metrics_rows = []
    for sample_index in sorted(manifest["sample_index"].unique()):
        sample_manifest = manifest[manifest["sample_index"] == sample_index]
        sample_case = str(sample_manifest["sample_case"].iloc[0])
        if args.stitch_backend == "nco":
            assert ncks is not None
            assert ncrcat is not None
            out_path = stitch_sample_nco(
                scm_runs,
                stitched_dir,
                sample_case,
                sample_manifest,
                ncks=ncks,
                ncrcat=ncrcat,
                keep_temp=args.keep_nco_temp,
            )
        else:
            out_path = stitch_sample(scm_runs, stitched_dir, sample_case, sample_manifest)
        metrics_rows.append(extract_metrics(int(sample_index), sample_case, out_path))
        print(f"stitched sample {int(sample_index):03d}: {out_path}")

    metrics = pd.DataFrame(metrics_rows)
    metrics_csv = metrics_dir / f"{experiment_dir.parent.name}_{experiment_dir.name}_metrics.csv"
    param_response_csv = metrics_dir / f"{experiment_dir.parent.name}_{experiment_dir.name}_parameter_response.csv"
    metrics.to_csv(metrics_csv, index=False)

    merged = samples.merge(metrics, on=["sample_index", "case"], how="left")
    merged.to_csv(param_response_csv, index=False)

    print(f"metrics: {metrics_csv}")
    print(f"parameter-response table: {param_response_csv}")


if __name__ == "__main__":
    main()
