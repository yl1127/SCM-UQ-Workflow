from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
import sys

import numpy as np
import pandas as pd

try:
    from netCDF4 import Dataset, date2num, num2date
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing Python package netCDF4. Install it with:\n"
        "  python3 -m pip install --user netCDF4\n"
        "Then rerun this script."
    ) from exc


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "e3sm_scm_mac_arm97_segment_scripts/mac_arm97_segment_script_manifest.csv"
STATUS = ROOT / "mac_arm97_segment_design/mac_arm97_segment_run_status.csv"
OUT = ROOT / "mac_arm97_segment_design/mac_ARM97_26day_stitched_from_segments.nc"
SCM_RUNS = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))


def history_file(case_name: str) -> Path:
    run_dir = SCM_RUNS / case_name / "run"
    files = sorted(run_dir.glob("*.eam.h0.*.nc"))
    if not files:
        raise FileNotFoundError(f"missing history file for {case_name}: {run_dir}")
    return files[-1]


def output_datetimes(ds: Dataset) -> list[datetime]:
    time = ds.variables["time"]
    values = time[:]
    units = getattr(time, "units")
    calendar = getattr(time, "calendar", "standard")
    dates = num2date(values, units=units, calendar=calendar, only_use_cftime_datetimes=False)
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


def create_output(first: Dataset, out_path: Path, time_len: int) -> Dataset:
    if out_path.exists():
        out_path.unlink()
    out = Dataset(out_path, "w", format=first.data_model)

    for name, dim in first.dimensions.items():
        out.createDimension(name, time_len if name == "time" else len(dim))

    for name, value in first.__dict__.items():
        setattr(out, name, value)
    out.setncattr("segment_stitching", "52 segment runs; first 24h discarded; final 12h kept from each segment; duplicate boundary times removed")

    for name, var in first.variables.items():
        fill_value = getattr(var, "_FillValue", None)
        kwargs = {}
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


def main() -> None:
    manifest = pd.read_csv(MANIFEST)
    if STATUS.exists():
        status = pd.read_csv(STATUS)
        failed = status[status["status"].astype(str).str.startswith("failed")]
        if not failed.empty:
            raise SystemExit(f"Refusing to stitch with failed cases:\n{failed[['case', 'status']].to_string(index=False)}")

    selected: list[tuple[str, Path, list[int]]] = []
    seen = set()
    for _, row in manifest.sort_values("segment_index").iterrows():
        case_name = row["case"]
        keep_start = datetime.fromisoformat(row["keep_start_datetime"])
        keep_end = datetime.fromisoformat(row["keep_end_datetime"])
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

    total_records = sum(len(indices) for _, _, indices in selected)
    with Dataset(selected[0][1]) as first:
        out = create_output(first, OUT, total_records)
        copy_static_variables(first, out)

    offset = 0
    with Dataset(OUT, "a") as out:
        for case_name, path, indices in selected:
            with Dataset(path) as src:
                copy_time_records(src, out, indices, offset)
            offset += len(indices)

    print(f"stitched records: {total_records}")
    print(OUT)


if __name__ == "__main__":
    main()
