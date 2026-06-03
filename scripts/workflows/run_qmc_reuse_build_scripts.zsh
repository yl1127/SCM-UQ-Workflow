#!/bin/zsh
set -eu

export PATH="${SCM_UQ_EXTRA_PATH:-/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin}:"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/e3sm_scm_qmc_run_scripts_reuse_build/qmc_reuse_build_run_script_manifest.csv"
STATUS="$ROOT/qmc_design/e3sm_scm_qmc_reuse_build_run_status.csv"

echo "case,script,status,start_epoch,end_epoch,wall_seconds" > "$STATUS"

tail -n +2 "$MANIFEST" | while IFS=, read -r original_case reuse_case script source template_exe reuse_build; do
  case_dir="/"
  start=$(date +%s)
  run_status="success"

  if [[ "$reuse_case" == "qmc_ARM97_reuse_baseline" ]]; then
    run_status="skipped_template_baseline"
  elif [[ -e "$case_dir/run/case_scripts.eam.h0.1997-06-19-84585.nc" ]]; then
    run_status="skipped_existing_success"
  elif [[ -e "$case_dir" ]]; then
    run_status="skipped_existing_case_dir"
  else
    csh "$ROOT/$script" || run_status="failed"
  fi

  end=$(date +%s)
  echo "$reuse_case,$script,$run_status,$start,$end,$(( end - start ))" >> "$STATUS"
done

echo "$STATUS"
