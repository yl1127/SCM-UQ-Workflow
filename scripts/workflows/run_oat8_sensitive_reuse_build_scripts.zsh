#!/bin/zsh
set -eu

export PATH="${SCM_UQ_EXTRA_PATH:-/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin}:"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/e3sm_scm_oat8_sensitive_reuse_build_scripts/oat8_sensitive_reuse_build_script_manifest.csv"
STATUS="$ROOT/oat8_sensitive_design/oat8_sensitive_reuse_build_run_status.csv"

if [[ ! -e "$STATUS" ]]; then
  echo "case,script,varied_parameter,relative_perturbation_percent,status,start_epoch,end_epoch,wall_seconds" > "$STATUS"
fi

tail -n +2 "$MANIFEST" | while IFS=, read -r case script varied_parameter relative_perturbation relative_perturbation_percent varied_value_numeric varied_value_fortran template_exe reuse_build; do
  if awk -F, -v c="$case" 'NR > 1 && $1 == c { found = 1 } END { exit found ? 0 : 1 }' "$STATUS"; then
    continue
  fi

  case_dir="/"
  history_file="$case_dir/run/case_scripts.eam.h0.1997-06-19-84585.nc"
  start=$(date +%s)
  run_status="success"

  if [[ -e "$history_file" ]]; then
    run_status="skipped_existing_success"
  elif [[ -e "$case_dir" ]]; then
    run_status="skipped_existing_case_dir"
  else
    csh "$ROOT/$script" < /dev/null || run_status="failed"
  fi

  end=$(date +%s)
  echo "$case,$script,$varied_parameter,$relative_perturbation_percent,$run_status,$start,$end,$(( end - start ))" >> "$STATUS"
done

echo "$STATUS"
