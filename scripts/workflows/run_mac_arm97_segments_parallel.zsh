#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/e3sm_scm_mac_arm97_segment_scripts/mac_arm97_segment_script_manifest.csv"
STATUS="$ROOT/mac_arm97_segment_design/mac_arm97_segment_run_status.csv"
SCM_RUNS="${SCM_RUNS:-/path/to/SCM_runs}"
MAX_JOBS="${MAX_JOBS:-52}"

mkdir -p "$(dirname "$STATUS")"

if [[ ! -e "$MANIFEST" ]]; then
  echo "ERROR: missing manifest: $MANIFEST" >&2
  echo "Run: python3 generate_mac_arm97_segment_scripts.py" >&2
  exit 2
fi

if [[ ! -e "$STATUS" ]]; then
  echo "case,script,status,start_epoch,end_epoch,wall_seconds,history_file,log_file" > "$STATUS"
fi

already_recorded() {
  local case_name="$1"
  awk -F, -v c="$case_name" 'NR > 1 && $1 == c { found = 1 } END { exit found ? 0 : 1 }' "$STATUS"
}

history_file_for_case() {
  local case_name="$1"
  local case_dir="$SCM_RUNS/$case_name"
  find "$case_dir/run" -maxdepth 1 -type f -name '*.eam.h0.*.nc' 2>/dev/null | sort | tail -n 1
}

run_one_case() {
  local case_name="$1"
  local script="$2"
  local script_path="$script"
  local case_dir="$SCM_RUNS/$case_name"
  local log_dir="$ROOT/mac_arm97_segment_design/run_logs"
  local log_file="$log_dir/${case_name}.log"
  local start_epoch end_epoch history_file run_status

  mkdir -p "$log_dir"
  start_epoch=$(date +%s)
  run_status="success"
  history_file=""

  if already_recorded "$case_name"; then
    return 0
  fi

  history_file="$(history_file_for_case "$case_name")"
  if [[ -n "$history_file" && -s "$history_file" ]]; then
    run_status="skipped_existing_success"
  elif [[ -e "$case_dir" ]]; then
    run_status="skipped_existing_case_dir"
  else
    if [[ "$script_path" != /* ]]; then
      script_path="$ROOT/$script_path"
    fi
    csh "$script_path" > "$log_file" 2>&1 || run_status="failed"
    history_file="$(history_file_for_case "$case_name")"
    if [[ "$run_status" == "success" && ( -z "$history_file" || ! -s "$history_file" ) ]]; then
      run_status="failed_no_history"
    fi
  fi

  end_epoch=$(date +%s)
  print -r -- "$case_name,$script,$run_status,$start_epoch,$end_epoch,$((end_epoch - start_epoch)),$history_file,$log_file" >> "$STATUS"
}

{
  read -r header
  while IFS=, read -r segment_index case_name script start_datetime start_date start_seconds stop_option stop_n spinup_hours keep_hours keep_start keep_end baseline_start; do
    while (( $(jobs -pr | wc -l | tr -d ' ') >= MAX_JOBS )); do
      sleep 2
    done
    run_one_case "$case_name" "$script" &
  done
} < "$MANIFEST"

wait
echo "$STATUS"
