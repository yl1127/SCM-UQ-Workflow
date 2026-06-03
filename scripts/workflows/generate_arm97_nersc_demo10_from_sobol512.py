#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from datetime import timedelta
from pathlib import Path
import os
from typing import Any

from generate_arm97_experiment import (
    BASELINE_START,
    KEEP_HOURS,
    PLATFORMS,
    SEGMENT_COUNT,
    SEGMENT_RUN_HOURS,
    SEGMENT_START,
    SEGMENT_STRIDE_HOURS,
    SPINUP_HOURS,
    load_params,
    render_script,
    seconds_of_day,
    write_csv,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE_CSV = (
    ROOT
    / "arm97_experiments/arm97_sobol512_segmented/mac/design/arm97_sobol512_segmented_samples.csv"
)
DEFAULT_OUT_ROOT = ROOT / "arm97_experiments/arm97_sobol512_segmented/nersc/demo10"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate NERSC scripts for the first 10 samples of the existing ARM97 Sobol-512 design."
    )
    parser.add_argument("--sample-csv", default=str(DEFAULT_SAMPLE_CSV))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--params", default=str(ROOT / "configs/params_arm97_core.yaml"))
    parser.add_argument("--template", default=str(PLATFORMS["nersc"]["template"]))
    parser.add_argument("--sample-start", type=int, default=0)
    parser.add_argument("--n-samples", type=int, default=10)
    parser.add_argument("--case-prefix", default="nersc_ARM97_arm97_sobol512_segmented")
    parser.add_argument("--experiment", default="arm97_sobol512_segmented_demo10")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_selected_samples(path: Path, sample_start: int, n_samples: int) -> list[dict[str, Any]]:
    selected_indices = set(range(sample_start, sample_start + n_samples))
    with path.open(newline="") as f:
        rows = [row for row in csv.DictReader(f) if int(row["sample_index"]) in selected_indices]
    rows.sort(key=lambda row: int(row["sample_index"]))
    if len(rows) != n_samples:
        found = [int(row["sample_index"]) for row in rows]
        raise ValueError(f"expected {n_samples} samples from {sample_start}; found {found}")
    return rows


def write_setup_script(path: Path, manifest_name: str) -> None:
    path.write_text(
        f"""#!/bin/bash -el

SCRIPT_DIR=$(cd "${{SLURM_SUBMIT_DIR:-$(dirname "${{BASH_SOURCE[0]}}")}}" && pwd)
MANIFEST="${{SCRIPT_DIR}}/{manifest_name}"
STATUS_CSV="${{SCRIPT_DIR}}/nersc_demo10_setup_status.csv"
MAX_SETUP_JOBS="${{MAX_SETUP_JOBS:-8}}"
export TEMPLATE_EXE_NERSC="${{TEMPLATE_EXE_NERSC:-/pscratch/sd/y/yunlong/SCM_runs/nersc_ARM97_reusable_baseline/build/e3sm.exe}}"

echo "case,script,status,start_epoch,end_epoch,wall_seconds" > "${{STATUS_CSV}}"

run_setup() {{
  local case_name="$1"
  local script="$2"
  local start
  local end
  local status

  start=$(date +%s)
  status=success
  csh "${{SCRIPT_DIR}}/scripts/${{script}}" || status=failed
  end=$(date +%s)
  echo "${{case_name}},${{script}},${{status}},${{start}},${{end}},$((end-start))" >> "${{STATUS_CSV}}"
  [[ "${{status}}" == "success" ]]
}}

while IFS=, read -r experiment platform sample_index sample_case case_name segment_index script start_datetime start_date start_seconds stop_option stop_n spinup_hours keep_hours keep_start keep_end; do
  while (( $(jobs -pr | wc -l | tr -d ' ') >= MAX_SETUP_JOBS )); do
    sleep 2
  done
  run_setup "${{case_name}}" "$(basename "${{script}}")" &
done < <(tail -n +2 "${{MANIFEST}}")

rc=0
for job in $(jobs -p); do
  wait "${{job}}" || rc=1
done

echo "Wrote ${{STATUS_CSV}}"
exit "${{rc}}"
"""
    )
    path.chmod(0o755)


def write_run_script(path: Path, manifest_name: str) -> None:
    path.write_text(
        f"""#!/bin/bash -el

#SBATCH --account=m2136
#SBATCH --job-name=arm97.demo10
#SBATCH --output=arm97.demo10.%j.out
#SBATCH --error=arm97.demo10.%j.err
#SBATCH --nodes=1
#SBATCH --qos=regular
#SBATCH --time=04:00:00
#SBATCH --exclusive
#SBATCH --constraint=cpu

SCRIPT_DIR=$(cd "${{SLURM_SUBMIT_DIR:-$(dirname "${{BASH_SOURCE[0]}}")}}" && pwd)
MANIFEST="${{SCRIPT_DIR}}/{manifest_name}"
CASE_ROOT="${{CASE_ROOT:-${{PSCRATCH}}/SCM_runs}}"
MAX_CONCURRENT="${{MAX_CONCURRENT:-120}}"
TIMING_CSV="${{SCRIPT_DIR}}/nersc_demo10_run_timing.${{SLURM_JOB_ID:-manual}}.csv"

echo "case,start_epoch,end_epoch,wall_seconds,exit_code,log_file" > "${{TIMING_CSV}}"

run_case() {{
  local case_name="$1"
  local case_dir="${{CASE_ROOT}}/${{case_name}}/case_scripts"
  local log_file="${{case_dir}}/${{case_name}}.bundle.log"
  local start
  local end
  local rc

  start=$(date +%s)
  cd "${{case_dir}}"
  python ./case.submit --no-batch > "${{log_file}}" 2>&1
  rc=$?
  end=$(date +%s)
  echo "${{case_name}},${{start}},${{end}},$((end-start)),${{rc}},${{log_file}}" >> "${{TIMING_CSV}}"
  return "${{rc}}"
}}

while IFS=, read -r experiment platform sample_index sample_case case_name segment_index script start_datetime start_date start_seconds stop_option stop_n spinup_hours keep_hours keep_start keep_end; do
  while (( $(jobs -pr | wc -l | tr -d ' ') >= MAX_CONCURRENT )); do
    sleep 2
  done
  run_case "${{case_name}}" &
done < <(tail -n +2 "${{MANIFEST}}")

rc=0
for job in $(jobs -p); do
  wait "${{job}}" || rc=1
done

echo "TIMING_CSV=${{TIMING_CSV}}"
exit "${{rc}}"
"""
    )
    path.chmod(0o755)


def write_readme(path: Path, script_count: int, sample_count: int) -> None:
    path.write_text(
        f"""# ARM97 Sobol-512 demo10 on NERSC

This directory contains NERSC scripts for the first {sample_count} samples from the existing
`arm97_sobol512_segmented` Sobol-512 design. Each sample is split into 52 independent
1.5-day SCM segment cases, for {script_count} total cases.

## Files

- `design/arm97_sobol512_segmented_demo10_nersc_samples.csv`
- `design/arm97_sobol512_segmented_demo10_nersc_script_manifest.csv`
- `scripts/*.csh`
- `setup_cases_nersc.sh`
- `run_bundle_nersc.sh`

## NERSC usage

Copy this `demo10` directory to NERSC, then run:

```bash
cd demo10
MAX_SETUP_JOBS=8 ./setup_cases_nersc.sh
sbatch run_bundle_nersc.sh
```

The per-case scripts use `$SCM_RUNS` if set, otherwise `$PSCRATCH/SCM_runs`,
and link `$TEMPLATE_EXE` if set, otherwise `$TEMPLATE_EXE_NERSC`. By default,
`TEMPLATE_EXE_NERSC` points to:

```bash
/pscratch/sd/y/yunlong/SCM_runs/nersc_ARM97_reusable_baseline/build/e3sm.exe
```
"""
    )


def main() -> None:
    args = parse_args()
    sample_csv = Path(args.sample_csv)
    template_path = Path(args.template)
    out_root = Path(args.out_root)
    script_dir = out_root / "scripts"
    design_dir = out_root / "design"
    manifest_name = "design/arm97_sobol512_segmented_demo10_nersc_script_manifest.csv"

    if script_dir.exists() and any(script_dir.glob("*.csh")) and not args.overwrite:
        raise FileExistsError(f"{script_dir} already has scripts; use --overwrite")

    params = load_params(Path(args.params))
    template = template_path.read_text()
    samples = load_selected_samples(sample_csv, args.sample_start, args.n_samples)

    script_dir.mkdir(parents=True, exist_ok=True)
    design_dir.mkdir(parents=True, exist_ok=True)

    sample_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []

    for sample in samples:
        sample_index = int(sample["sample_index"])
        sample_case = f"{args.case_prefix}_{sample_index:03d}"
        sample_row = {
            **sample,
            "experiment": args.experiment,
            "platform": "nersc",
            "case": sample_case,
            "source_case": sample.get("case", ""),
        }
        sample_rows.append(sample_row)

        for segment_index in range(SEGMENT_COUNT):
            start = SEGMENT_START + timedelta(hours=SEGMENT_STRIDE_HOURS * segment_index)
            keep_start = start + timedelta(hours=SPINUP_HOURS)
            keep_end = keep_start + timedelta(hours=KEEP_HOURS)
            case_name = f"{sample_case}_seg_{segment_index:03d}"
            script_path = script_dir / f"{case_name}.csh"
            script_path.write_text(
                render_script(
                    template,
                    case_name,
                    params,
                    sample,
                    start,
                    "nhours",
                    SEGMENT_RUN_HOURS,
                )
            )
            script_path.chmod(0o755)
            manifest_rows.append(
                {
                    "experiment": args.experiment,
                    "platform": "nersc",
                    "sample_index": sample_index,
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
                }
            )

    write_csv(design_dir / "arm97_sobol512_segmented_demo10_nersc_samples.csv", sample_rows)
    write_csv(design_dir / Path(manifest_name).name, manifest_rows)
    write_csv(script_dir / Path(manifest_name).name, manifest_rows)
    write_setup_script(out_root / "setup_cases_nersc.sh", manifest_name)
    write_run_script(out_root / "run_bundle_nersc.sh", manifest_name)
    write_readme(out_root / "README.md", len(manifest_rows), len(sample_rows))

    print(f"samples: {len(sample_rows)}")
    print(f"scripts: {len(manifest_rows)}")
    print(out_root)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
