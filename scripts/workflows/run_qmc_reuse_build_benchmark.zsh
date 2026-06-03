#!/bin/zsh
set -eu

export PATH="${SCM_UQ_EXTRA_PATH:-/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin}:"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$ROOT/e3sm_scm_qmc_run_scripts_reuse_build"
OUT="$ROOT/qmc_design/reuse_build_benchmark_walltime.csv"

cases=(
  qmc_ARM97_reuse_000
  qmc_ARM97_reuse_001
  qmc_ARM97_reuse_002
  qmc_ARM97_reuse_003
)

echo "case,status,start_epoch,end_epoch,wall_seconds,script" > "$OUT"

for case in "${cases[@]}"; do
  script="$SCRIPT_DIR/${case}.csh"
  start=$(date +%s)
  run_status="success"
  if [[ ! -x "$script" ]]; then
    run_status="missing_script"
  elif [[ -e "/" ]]; then
    run_status="case_already_exists"
  else
    csh "$script" || run_status="failed"
  fi
  end=$(date +%s)
  echo "$case,$run_status,$start,$end,$(( end - start )),$script" >> "$OUT"
done

echo "$OUT"
