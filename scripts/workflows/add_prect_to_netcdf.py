#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from netCDF4 import Dataset


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATTERNS = [
    "e3sm_scm_run_scripts_baseline/baseline-output/scm_ARM97_baseline/run/*.eam.h0.*.nc",
    "arm97_experiments_0602/*/mac/stitched/*_stitched_26day.nc",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add PRECT=PRECC+PRECL to existing E3SM SCM NetCDF files.")
    parser.add_argument("files", nargs="*", type=Path, help="Specific NetCDF files to update.")
    parser.add_argument(
        "--default-set",
        action="store_true",
        help="Update the repository's baseline and ARM97 stitched output files.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report actions without modifying files.")
    return parser.parse_args()


def default_files() -> list[Path]:
    files: list[Path] = []
    for pattern in DEFAULT_PATTERNS:
        files.extend(ROOT.glob(pattern))
    return sorted(set(files))


def add_prect(path: Path, dry_run: bool) -> str:
    with Dataset(path, "r" if dry_run else "a") as ds:
        if "PRECT" in ds.variables:
            return "exists"
        if "PRECC" not in ds.variables or "PRECL" not in ds.variables:
            return "missing PRECC/PRECL"

        precc = ds.variables["PRECC"]
        precl = ds.variables["PRECL"]
        if precc.dimensions != precl.dimensions or precc.shape != precl.shape:
            return "shape mismatch"
        if dry_run:
            return "would add"

        fill_value = getattr(precc, "_FillValue", None)
        kwargs = {"fill_value": fill_value} if fill_value is not None else {}
        prect = ds.createVariable("PRECT", precc.datatype, precc.dimensions, **kwargs)
        prect.setncattr("long_name", "Total precipitation rate (PRECC+PRECL)")
        prect.setncattr("units", getattr(precc, "units", "m/s"))
        prect.setncattr("source", "Added by add_prect_to_netcdf.py as PRECC+PRECL")
        prect[:] = np.ma.asarray(precc[:], dtype=np.float64) + np.ma.asarray(precl[:], dtype=np.float64)
        return "added"


def main() -> None:
    args = parse_args()
    files = [path.expanduser().resolve() for path in args.files]
    if args.default_set:
        files.extend(path.resolve() for path in default_files())
    files = sorted(set(files))
    if not files:
        raise SystemExit("No files selected. Pass files or use --default-set.")

    counts: dict[str, int] = {}
    for path in files:
        if not path.exists():
            status = "missing file"
        else:
            status = add_prect(path, args.dry_run)
        counts[status] = counts.get(status, 0) + 1
        print(f"{status}: {path}")

    print("summary:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
