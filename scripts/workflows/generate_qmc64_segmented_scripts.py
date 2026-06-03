#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESIGN = ROOT / "qmc_design/e3sm_scm_qmc_64_design.csv"
DEFAULT_TEMPLATE = ROOT / "scripts/workflows/MAC_ARM97_reuse_baseline.csh"
DEFAULT_OUT_ROOT = ROOT / "arm97_experiments/qmc64_segmented/mac"
DEFAULT_TEMPLATE_EXE = Path(
    os.environ.get("SCM_RUNS", "/path/to/SCM_runs") + "/"
    "mac_ARM97_arm97_sobol512_segmented_001_seg_011/build/e3sm.exe"
)

BASELINE_START = datetime(1997, 6, 19, 23, 29, 45)
SEGMENT_START = BASELINE_START - timedelta(days=1)
SEGMENT_COUNT = 52
SEGMENT_STRIDE_HOURS = 12
SEGMENT_RUN_HOURS = 36
SPINUP_HOURS = 24
KEEP_HOURS = 12

METADATA_COLUMNS = {"case", "qmc_index", "qmc_sampler", "qmc_seed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate 52-segment stitched ARM97 scripts from the existing 64-case QMC design."
    )
    parser.add_argument("--design", default=str(DEFAULT_DESIGN))
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--experiment", default="qmc64_segmented")
    parser.add_argument("--case-prefix", default="mac_ARM97_qmc64_segmented")
    parser.add_argument("--template-exe", default=str(DEFAULT_TEMPLATE_EXE))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def seconds_of_day(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second


def replace_one(text: str, pattern: str, replacement: str) -> str:
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"expected one replacement for pattern: {pattern}")
    return text


def replace_assignment(text: str, name: str, value: str) -> str:
    pattern = rf"^(\s*(?:set\s+)?{re.escape(name)}\s*=\s*).*$"
    replacement = rf"\g<1>{value}"
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"expected one assignment replacement for {name}")
    return text


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def qmc_parameter_columns(row: dict[str, str]) -> list[str]:
    return [
        name
        for name in row
        if name not in METADATA_COLUMNS and not name.endswith("_numeric")
    ]


def render_script(
    template: str,
    case_name: str,
    sample: dict[str, str],
    param_columns: list[str],
    start: datetime,
    template_exe: Path,
) -> str:
    text = template
    text = replace_one(text, r"^\s*setenv casename .*$", f"  setenv casename {case_name}")
    text = replace_one(
        text,
        r"^\s*set startdate = .*$",
        f"  set startdate = {start:%Y-%m-%d} # Experiment start date",
    )
    text = replace_one(
        text,
        r"^\s*set start_in_sec = .*$",
        f"  set start_in_sec = {seconds_of_day(start)} # Experiment start time in seconds",
    )
    text = replace_one(text, r"^\s*set stop_option = .*$", "  set stop_option = nhours")
    text = replace_one(text, r"^\s*set stop_n = .*$", f"  set stop_n = {SEGMENT_RUN_HOURS}")
    text = replace_one(
        text,
        r"^\s*set template_exe = .*$",
        f"  set template_exe = {template_exe}",
    )

    for name in param_columns:
        text = replace_assignment(text, name, sample[name])

    return text


def main() -> None:
    args = parse_args()
    design_path = Path(args.design)
    template_path = Path(args.template)
    template_exe = Path(args.template_exe)
    out_root = Path(args.out_root)
    script_dir = out_root / "scripts"
    design_dir = out_root / "design"

    if not design_path.exists():
        raise FileNotFoundError(design_path)
    if not template_path.exists():
        raise FileNotFoundError(template_path)
    if not template_exe.exists():
        raise FileNotFoundError(template_exe)
    if script_dir.exists() and any(script_dir.glob("*.csh")) and not args.overwrite:
        raise FileExistsError(f"{script_dir} already has scripts; use --overwrite")

    script_dir.mkdir(parents=True, exist_ok=True)
    design_dir.mkdir(parents=True, exist_ok=True)

    samples = read_csv(design_path)
    if len(samples) != 64:
        raise RuntimeError(f"expected 64 QMC samples, found {len(samples)}")
    param_columns = qmc_parameter_columns(samples[0])
    template = template_path.read_text()

    manifest_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []

    for sample_pos, sample in enumerate(samples):
        qmc_index = int(sample["qmc_index"])
        source_case = sample["case"]
        sample_case = f"{args.case_prefix}_{qmc_index:03d}"
        sample_rows.append(
            {
                "experiment": args.experiment,
                "platform": "mac",
                "sample_index": qmc_index,
                "sample_case": sample_case,
                "source_case": source_case,
                "source_qmc_index": qmc_index,
                "qmc_sampler": sample.get("qmc_sampler", ""),
                "qmc_seed": sample.get("qmc_seed", ""),
                **sample,
            }
        )

        if sample_pos != qmc_index:
            raise RuntimeError(f"QMC rows must be ordered by qmc_index: row {sample_pos}, qmc_index {qmc_index}")

        for segment_index in range(SEGMENT_COUNT):
            start = SEGMENT_START + timedelta(hours=SEGMENT_STRIDE_HOURS * segment_index)
            keep_start = start + timedelta(hours=SPINUP_HOURS)
            keep_end = keep_start + timedelta(hours=KEEP_HOURS)
            case_name = f"{sample_case}_seg_{segment_index:03d}"
            script_path = script_dir / f"{case_name}.csh"
            script_path.write_text(
                render_script(template, case_name, sample, param_columns, start, template_exe)
            )
            script_path.chmod(0o755)
            manifest_rows.append(
                {
                    "experiment": args.experiment,
                    "platform": "mac",
                    "sample_index": qmc_index,
                    "sample_case": sample_case,
                    "case": case_name,
                    "segment_index": segment_index,
                    "script": str(script_path),
                    "start_datetime": start.isoformat(sep=" "),
                    "start_date": f"{start:%Y-%m-%d}",
                    "start_seconds": seconds_of_day(start),
                    "stop_option": "nhours",
                    "stop_n": SEGMENT_RUN_HOURS,
                    "spinup_hours": SPINUP_HOURS,
                    "keep_hours": KEEP_HOURS,
                    "keep_start_datetime": keep_start.isoformat(sep=" "),
                    "keep_end_datetime": keep_end.isoformat(sep=" "),
                    "baseline_start_datetime": BASELINE_START.isoformat(sep=" "),
                    "source_case": source_case,
                }
            )

    write_csv(design_dir / f"{args.experiment}_samples.csv", sample_rows)
    write_csv(design_dir / f"{args.experiment}_script_manifest.csv", manifest_rows)
    write_csv(script_dir / f"{args.experiment}_script_manifest.csv", manifest_rows)

    print(f"experiment: {args.experiment}")
    print(f"samples: {len(sample_rows)}")
    print(f"segments_per_sample: {SEGMENT_COUNT}")
    print(f"scripts: {len(manifest_rows)}")
    print(design_dir / f"{args.experiment}_script_manifest.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
