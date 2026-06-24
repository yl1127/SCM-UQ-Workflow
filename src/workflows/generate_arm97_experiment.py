#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]

PLATFORMS = {
    "mac": {
        "template": ROOT / "src/workflows/MAC_ARM97_reuse_baseline.csh",
        "case_prefix": "mac_ARM97",
        "script_dir_prefix": "e3sm_scm_mac",
    },
    "nersc": {
        "template": ROOT / "src/workflows/ARM97_reuse_baseline.csh",
        "case_prefix": "nersc_ARM97",
        "script_dir_prefix": "e3sm_scm_nersc",
    },
}

BASELINE_START = datetime(1997, 6, 19, 23, 29, 45)

# Stitched convention:
# - start one 36-hour segment per day at the same time of day,
# - discard the first 12 hours as segment spin-up,
# - keep the following 24 hours for stitching.
# With SEGMENT_START = BASELINE_START - 12h, each kept window begins at the
# baseline output-window time of day, which keeps daily stitching boundaries
# consistent for diagnostics.
SEGMENT_START = BASELINE_START - timedelta(hours=12)
SEGMENT_COUNT = 26
SEGMENT_STRIDE_HOURS = 24
SEGMENT_RUN_HOURS = 36
SPINUP_HOURS = 12
KEEP_HOURS = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate ARM97 SCM experiment scripts for Mac or NERSC."
    )
    parser.add_argument("--platform", choices=sorted(PLATFORMS), default="mac")
    parser.add_argument("--experiment", required=True)
    parser.add_argument(
        "--design",
        choices=["baseline", "lhs", "halton", "sobol", "digitalnetb2", "qmc-digitalnetb2", "oat"],
        default="lhs",
    )
    parser.add_argument("--n-samples", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260520)
    parser.add_argument("--params", default=str(ROOT / "configs/params_arm97_core.yaml"))
    parser.add_argument("--template")
    parser.add_argument("--out-root", default=str(ROOT / "arm97_experiments"))
    parser.add_argument("--case-prefix")
    parser.add_argument(
        "--segment-mode",
        choices=["52x1.5day", "full26day"],
        default="52x1.5day",
    )
    parser.add_argument(
        "--include-baseline",
        action="store_true",
        help="Add one baseline sample before the perturbed samples.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing scripts for this experiment.",
    )
    return parser.parse_args()


def load_params(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        data = yaml.safe_load(f)
    params = data.get("parameters", [])
    if not params:
        raise ValueError(f"no parameters found in {path}")
    for param in params:
        for key in ("name", "baseline", "lower", "upper", "format"):
            if key not in param:
                raise ValueError(f"parameter entry missing {key}: {param}")
        if float(param["lower"]) > float(param["upper"]):
            raise ValueError(f"lower > upper for {param['name']}")
    return params


def replace_one(text: str, pattern: str, replacement: str) -> str:
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"expected one replacement for pattern: {pattern}")
    return text


def seconds_of_day(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second


def format_value(value: float, style: str) -> str:
    if style == "D0":
        return f"{value:.8g}D0"
    if style == "D":
        return f"{value:.8e}".replace("e", "D")
    if style == "E":
        return f"{value:.8E}"
    if style == "e":
        return f"{value:.8e}"
    if style == "int":
        return str(int(round(value)))
    return f"{value:.8g}"


def van_der_corput(index: int, base: int) -> float:
    result = 0.0
    denominator = 1.0
    while index:
        index, remainder = divmod(index, base)
        denominator *= base
        result += remainder / denominator
    return result


def first_primes(n: int) -> list[int]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < n:
        is_prime = True
        limit = int(math.sqrt(candidate)) + 1
        for prime in primes:
            if prime > limit:
                break
            if candidate % prime == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(candidate)
        candidate += 1
    return primes


def next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def unit_design(design: str, n_samples: int, n_dim: int, seed: int) -> tuple[list[list[float]], str]:
    if design == "baseline":
        return [], "baseline"
    if design == "halton":
        primes = first_primes(n_dim)
        rows = [
            [van_der_corput(i + 1, primes[j]) for j in range(n_dim)]
            for i in range(n_samples)
        ]
        return rows, "halton"
    if design == "lhs":
        rng = random.Random(seed)
        columns = []
        for _ in range(n_dim):
            values = [(i + rng.random()) / n_samples for i in range(n_samples)]
            rng.shuffle(values)
            columns.append(values)
        return [[columns[j][i] for j in range(n_dim)] for i in range(n_samples)], "lhs"
    if design == "sobol":
        try:
            from scipy.stats import qmc  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "sobol design requires scipy. Use --design halton for a no-dependency QMC pilot, "
                "or install scipy before generating Sobol samples."
            ) from exc
        sampler = qmc.Sobol(d=n_dim, scramble=True, seed=seed)
        if n_samples > 0 and n_samples & (n_samples - 1) == 0:
            rows = sampler.random_base2(m=int(math.log2(n_samples)))
        else:
            rows = sampler.random(n_samples)
        return rows.tolist(), "scipy.stats.qmc.Sobol"
    if design in {"digitalnetb2", "qmc-digitalnetb2"}:
        try:
            import qmcpy as qp  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "digitalnetb2 design requires qmcpy. Install requirements.txt before generating samples."
            ) from exc
        sampler = qp.DigitalNetB2(dimension=n_dim, seed=seed)
        n_draw = next_power_of_two(n_samples)
        rows = sampler(n_draw)[:n_samples]
        sampler_name = "QMCPy DigitalNetB2"
        if n_draw != n_samples:
            sampler_name += f" (generated {n_draw}, truncated to {n_samples})"
        return rows.tolist(), sampler_name
    if design == "oat":
        lows = [[0.0 if i == j else 0.5 for j in range(n_dim)] for i in range(n_dim)]
        highs = [[1.0 if i == j else 0.5 for j in range(n_dim)] for i in range(n_dim)]
        return lows + highs, "oat_low_high"
    raise ValueError(design)


def make_samples(
    params: list[dict[str, Any]], design: str, n_samples: int, seed: int, include_baseline: bool
) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    if include_baseline or design == "baseline":
        baseline = {
            "sample_index": 0,
            "sample_kind": "baseline",
        }
        for param in params:
            value = float(param["baseline"])
            baseline[param["name"]] = format_value(value, param["format"])
            baseline[f"{param['name']}_numeric"] = value
        rows.append(baseline)

    units, sampler_name = unit_design(design, n_samples, len(params), seed)
    offset = len(rows)
    for i, unit_row in enumerate(units):
        sample = {
            "sample_index": offset + i,
            "sample_kind": design,
        }
        for param, unit in zip(params, unit_row):
            low = float(param["lower"])
            high = float(param["upper"])
            value = low + unit * (high - low)
            sample[param["name"]] = format_value(value, param["format"])
            sample[f"{param['name']}_numeric"] = value
        rows.append(sample)
    return rows, sampler_name


def render_script(
    template: str,
    case_name: str,
    params: list[dict[str, Any]],
    sample: dict[str, Any],
    start: datetime,
    stop_option: str,
    stop_n: int,
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
    text = replace_one(text, r"^\s*set stop_option = .*$", f"  set stop_option = {stop_option}")
    text = replace_one(text, r"^\s*set stop_n = .*$", f"  set stop_n = {stop_n}")
    for param in params:
        name = param["name"]
        text = replace_one(
            text,
            rf"^(\s*){re.escape(name)}\s*=.*$",
            rf"\g<1>{name} = {sample[name]}",
        )
    return text


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


def write_nersc_setup_script(path: Path, manifest_rel: str) -> None:
    path.write_text(
        f"""#!/bin/bash -el

SCRIPT_DIR=$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)
MANIFEST="${{SCRIPT_DIR}}/{manifest_rel}"
STATUS_CSV="${{SCRIPT_DIR}}/nersc_setup_status.csv"
MAX_SETUP_JOBS="${{MAX_SETUP_JOBS:-8}}"

export SCM_RUNS="${{SCM_RUNS:-${{PSCRATCH}}/SCM_runs}}"
export TEMPLATE_EXE_NERSC="${{TEMPLATE_EXE_NERSC:-/pscratch/sd/y/yunlong/SCM_runs/nersc_ARM97_reusable_baseline/build/e3sm.exe}}"

if [[ -z "${{E3SM_CODE_DIR:-}}" ]]; then
  echo "ERROR: set E3SM_CODE_DIR to your E3SM checkout on NERSC." >&2
  exit 2
fi

if [[ -z "${{TEMPLATE_EXE:-}}" && -n "${{TEMPLATE_EXE_NERSC:-}}" ]]; then
  export TEMPLATE_EXE="${{TEMPLATE_EXE_NERSC}}"
fi

if [[ -z "${{TEMPLATE_EXE:-}}" ]]; then
  echo "ERROR: set TEMPLATE_EXE to a pre-built E3SM executable for reuse-build runs." >&2
  exit 2
fi

echo "case,script,status,start_epoch,end_epoch,wall_seconds" > "${{STATUS_CSV}}"

run_setup() {{
  local case_name="$1"
  local script_path="$2"
  local script_name
  local start
  local end
  local status

  script_name=$(basename "${{script_path}}")
  start=$(date +%s)
  status=success
  csh "${{SCRIPT_DIR}}/scripts/${{script_name}}" || status=failed
  end=$(date +%s)
  echo "${{case_name}},${{script_name}},${{status}},${{start}},${{end}},$((end-start))" >> "${{STATUS_CSV}}"
  [[ "${{status}}" == "success" ]]
}}

tail -n +2 "${{MANIFEST}}" | while IFS=, read -r experiment platform sample_index sample_case case_name segment_index script start_datetime start_date start_seconds stop_option stop_n spinup_hours keep_hours keep_start keep_end rest; do
  while (( $(jobs -pr | wc -l | tr -d ' ') >= MAX_SETUP_JOBS )); do
    sleep 2
  done
  run_setup "${{case_name}}" "${{script}}" &
done

rc=0
for job in $(jobs -p); do
  wait "${{job}}" || rc=1
done

echo "Wrote ${{STATUS_CSV}}"
exit "${{rc}}"
"""
    )
    path.chmod(0o755)


def write_nersc_run_script(path: Path, manifest_rel: str, experiment: str) -> None:
    path.write_text(
        f"""#!/bin/bash -el

#SBATCH --account=m2136
#SBATCH --job-name={experiment[:32]}
#SBATCH --output={experiment}.%j.out
#SBATCH --error={experiment}.%j.err
#SBATCH --nodes=1
#SBATCH --qos=regular
#SBATCH --time=04:00:00
#SBATCH --exclusive
#SBATCH --constraint=cpu

SCRIPT_DIR=$(cd "${{SLURM_SUBMIT_DIR:-$(dirname "${{BASH_SOURCE[0]}}")}}" && pwd)
MANIFEST="${{SCRIPT_DIR}}/{manifest_rel}"
CASE_ROOT="${{SCM_RUNS:-${{PSCRATCH}}/SCM_runs}}"
MAX_CONCURRENT="${{MAX_CONCURRENT:-120}}"
TIMING_CSV="${{SCRIPT_DIR}}/nersc_run_timing.${{SLURM_JOB_ID:-manual}}.csv"

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

tail -n +2 "${{MANIFEST}}" | while IFS=, read -r experiment platform sample_index sample_case case_name segment_index script start_datetime start_date start_seconds stop_option stop_n spinup_hours keep_hours keep_start keep_end rest; do
  while (( $(jobs -pr | wc -l | tr -d ' ') >= MAX_CONCURRENT )); do
    sleep 2
  done
  run_case "${{case_name}}" &
done

rc=0
for job in $(jobs -p); do
  wait "${{job}}" || rc=1
done

echo "TIMING_CSV=${{TIMING_CSV}}"
exit "${{rc}}"
"""
    )
    path.chmod(0o755)


def main() -> None:
    args = parse_args()
    platform = PLATFORMS[args.platform]
    template_path = Path(args.template) if args.template else platform["template"]
    if not template_path.exists():
        raise FileNotFoundError(template_path)
    params = load_params(Path(args.params))
    samples, sampler_name = make_samples(
        params, args.design, args.n_samples, args.seed, args.include_baseline
    )

    experiment = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.experiment.strip())
    if not experiment:
        raise ValueError("empty experiment name")
    case_prefix = args.case_prefix or f"{platform['case_prefix']}_{experiment}"
    out_root = Path(args.out_root) / experiment / args.platform
    script_dir = out_root / "scripts"
    design_dir = out_root / "design"
    if script_dir.exists() and any(script_dir.glob("*.csh")) and not args.overwrite:
        raise FileExistsError(f"{script_dir} already has scripts; use --overwrite")
    script_dir.mkdir(parents=True, exist_ok=True)
    design_dir.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text()
    manifest_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    for sample in samples:
        sample_index = int(sample["sample_index"])
        sample_case = f"{case_prefix}_{sample_index:03d}"
        sample_row = {
            "experiment": experiment,
            "platform": args.platform,
            "case": sample_case,
            "design": args.design,
            "sampler": sampler_name,
            "seed": args.seed,
            **sample,
        }
        sample_rows.append(sample_row)

        if args.segment_mode == "full26day":
            starts = [(None, BASELINE_START)]
            stop_option = "ndays"
            stop_n = 26
        else:
            starts = [
                (idx, SEGMENT_START + timedelta(hours=SEGMENT_STRIDE_HOURS * idx))
                for idx in range(SEGMENT_COUNT)
            ]
            stop_option = "nhours"
            stop_n = SEGMENT_RUN_HOURS

        for segment_index, start in starts:
            if segment_index is None:
                case_name = sample_case
                script_name = f"{case_name}.csh"
                keep_start = BASELINE_START
                keep_end = BASELINE_START + timedelta(days=26)
            else:
                case_name = f"{sample_case}_seg_{segment_index:03d}"
                script_name = f"{case_name}.csh"
                keep_start = start + timedelta(hours=SPINUP_HOURS)
                keep_end = keep_start + timedelta(hours=KEEP_HOURS)
            script_path = script_dir / script_name
            script_path.write_text(
                render_script(template, case_name, params, sample, start, stop_option, stop_n)
            )
            script_path.chmod(0o755)
            manifest_rows.append(
                {
                    "experiment": experiment,
                    "platform": args.platform,
                    "sample_index": sample_index,
                    "sample_case": sample_case,
                    "case": case_name,
                    "segment_index": "" if segment_index is None else segment_index,
                    "script": str(script_path),
                    "start_datetime": start.isoformat(sep=" "),
                    "start_date": f"{start:%Y-%m-%d}",
                    "start_seconds": seconds_of_day(start),
                    "stop_option": stop_option,
                    "stop_n": stop_n,
                    "spinup_hours": "" if segment_index is None else SPINUP_HOURS,
                    "keep_hours": "" if segment_index is None else KEEP_HOURS,
                    "keep_start_datetime": keep_start.isoformat(sep=" "),
                    "keep_end_datetime": keep_end.isoformat(sep=" "),
                }
            )

    write_csv(design_dir / f"{experiment}_samples.csv", sample_rows)
    write_csv(design_dir / f"{experiment}_script_manifest.csv", manifest_rows)
    write_csv(script_dir / f"{experiment}_script_manifest.csv", manifest_rows)
    if args.platform == "nersc":
        manifest_rel = f"design/{experiment}_script_manifest.csv"
        write_nersc_setup_script(out_root / "setup_cases_nersc.sh", manifest_rel)
        write_nersc_run_script(out_root / "run_bundle_nersc.sh", manifest_rel, experiment)
    print(f"experiment: {experiment}")
    print(f"platform: {args.platform}")
    print(f"samples: {len(sample_rows)}")
    print(f"scripts: {len(manifest_rows)}")
    print(design_dir / f"{experiment}_script_manifest.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
