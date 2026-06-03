#!/usr/bin/env python3
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import os
from typing import Any

import numpy as np
import pandas as pd

try:
    from netCDF4 import Dataset, date2num, num2date
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing Python package netCDF4. Install it with:\n"
        "  python3 -m pip install --user netCDF4"
    ) from exc


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "arm97_experiments/arm97_sobol512_segmented/mac"
DESIGN_DIR = EXPERIMENT_DIR / "design"
MANIFEST = DESIGN_DIR / "arm97_sobol512_segmented_demo10_manifest.csv"
SAMPLES = DESIGN_DIR / "arm97_sobol512_segmented_samples.csv"
STATUS = DESIGN_DIR / "experiment_run_status.csv"
SCM_RUNS = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
STITCHED_DIR = EXPERIMENT_DIR / "stitched/demo10"
METRICS_DIR = EXPERIMENT_DIR / "metrics"
METRICS_CSV = METRICS_DIR / "arm97_sobol512_demo10_metrics.csv"
PARAM_RESPONSE_CSV = METRICS_DIR / "arm97_sobol512_demo10_parameter_response.csv"

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


def history_file(case_name: str) -> Path:
    run_dir = SCM_RUNS / case_name / "run"
    files = sorted(run_dir.glob("*.eam.h0.*.nc"))
    if not files:
        raise FileNotFoundError(f"missing history file for {case_name}: {run_dir}")
    return files[-1]


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
        "52 segment runs; first 24h discarded; final 12h kept from each segment; duplicate boundary times removed",
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


def selected_records_for_sample(sample_manifest: pd.DataFrame) -> list[tuple[str, Path, list[int]]]:
    selected: list[tuple[str, Path, list[int]]] = []
    seen: set[datetime] = set()
    for _, row in sample_manifest.sort_values("segment_index").iterrows():
        case_name = str(row["case"])
        keep_start = datetime.fromisoformat(str(row["keep_start_datetime"]))
        keep_end = datetime.fromisoformat(str(row["keep_end_datetime"]))
        path = history_file(case_name)
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


def stitch_sample(sample_case: str, sample_manifest: pd.DataFrame) -> Path:
    out_path = STITCHED_DIR / f"{sample_case}_stitched_26day.nc"
    selected = selected_records_for_sample(sample_manifest)
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


def as_float_array(ds: Dataset, var_name: str) -> np.ma.MaskedArray:
    data = np.ma.asarray(ds.variables[var_name][:], dtype=float)
    return np.ma.masked_invalid(data)


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


def validate_status() -> None:
    status = pd.read_csv(STATUS)
    manifest = pd.read_csv(MANIFEST)
    demo_cases = set(manifest["case"].astype(str))
    status = status[status["case"].astype(str).isin(demo_cases)]
    if len(status) != len(demo_cases):
        raise SystemExit(f"status rows do not match manifest: {len(status)} vs {len(demo_cases)}")
    bad = status[status["status"] != "success"]
    if not bad.empty:
        raise SystemExit(f"refusing to stitch non-success cases:\n{bad[['case', 'status']].to_string(index=False)}")


def main() -> None:
    STITCHED_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    validate_status()

    manifest = pd.read_csv(MANIFEST)
    sample_table = pd.read_csv(SAMPLES)
    sample_indices = sorted(manifest["sample_index"].unique())
    metrics_rows = []
    for sample_index in sample_indices:
        sample_manifest = manifest[manifest["sample_index"] == sample_index]
        sample_case = str(sample_manifest["sample_case"].iloc[0])
        out_path = stitch_sample(sample_case, sample_manifest)
        metrics_rows.append(extract_metrics(int(sample_index), sample_case, out_path))
        print(f"stitched sample {sample_index:03d}: {out_path}")

    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(METRICS_CSV, index=False)

    demo_samples = sample_table[sample_table["sample_index"].isin(sample_indices)].copy()
    merged = demo_samples.merge(metrics, on=["sample_index", "case"], how="left")
    merged.to_csv(PARAM_RESPONSE_CSV, index=False)

    print(f"metrics: {METRICS_CSV}")
    print(f"parameter-response table: {PARAM_RESPONSE_CSV}")


if __name__ == "__main__":
    main()
