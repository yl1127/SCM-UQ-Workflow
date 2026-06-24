#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="${MANIFEST:-}"
SCM_RUNS="${SCM_RUNS:-/path/to/SCM_runs}"
MAX_JOBS="${MAX_JOBS:-52}"
GROUP_BY_SAMPLE="${GROUP_BY_SAMPLE:-true}"

if [[ -z "$MANIFEST" ]]; then
  echo "Usage: MANIFEST=/path/to/experiment_script_manifest.csv $0" >&2
  echo "Optional: SCM_RUNS=/path/to/SCM_runs MAX_JOBS=52" >&2
  exit 2
fi

if [[ ! -e "$MANIFEST" ]]; then
  echo "ERROR: missing manifest: $MANIFEST" >&2
  exit 2
fi

MANIFEST_DIR="$(cd "$(dirname "$MANIFEST")" && pwd)"
STATUS="${STATUS:-$MANIFEST_DIR/experiment_run_status.csv}"
LOG_DIR="${LOG_DIR:-$MANIFEST_DIR/run_logs}"

mkdir -p "$(dirname "$STATUS")" "$LOG_DIR"

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
  local log_file="$LOG_DIR/${case_name}.log"
  local start_epoch end_epoch history_file run_status

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

current_sample=""
launched_in_group=0

{
  read -r header
  while IFS=, read -r experiment platform sample_index sample_case case_name segment_index script start_datetime start_date start_seconds stop_option stop_n spinup_hours keep_hours keep_start keep_end rest; do
    if [[ "$GROUP_BY_SAMPLE" == "true" && -n "$current_sample" && "$sample_index" != "$current_sample" ]]; then
      wait
      launched_in_group=0
    fi
    current_sample="$sample_index"

    while (( launched_in_group >= MAX_JOBS )); do
      wait
      launched_in_group=0
    done

    run_one_case "$case_name" "$script" < /dev/null &
    launched_in_group=$((launched_in_group + 1))
  done
} < "$MANIFEST"

wait
echo "$STATUS"
