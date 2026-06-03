#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
manifest="$ROOT/e3sm_scm_qmc_run_scripts/qmc_run_script_manifest.csv"
status_csv="$ROOT/qmc_design/e3sm_scm_qmc_run_status.csv"
log_dir="$ROOT/qmc_design/run_logs"

mkdir -p "$log_dir"

if [ ! -f "$status_csv" ]; then
  echo "case,script,status,start_time,end_time,exit_code,log_file" > "$status_csv"
fi

tail -n +2 "$manifest" | while IFS=, read -r case script source
do
  if grep -q "^${case},${script},success," "$status_csv"; then
    echo "SKIP already successful: $case"
    continue
  fi
  if grep -q "^${case},${script},failed," "$status_csv"; then
    echo "SKIP previously failed: $case"
    continue
  fi

  start_time=$(date '+%Y-%m-%d %H:%M:%S')
  log_file="${log_dir}/${case}.log"
  echo "===== RUNNING ${case} at ${start_time} ====="

  if [[ "$script" != /* ]]; then
    script="$ROOT/$script"
  fi

  "$script" > "$log_file" 2>&1 < /dev/null
  rc=$?

  end_time=$(date '+%Y-%m-%d %H:%M:%S')
  if grep -q "RUN FAIL\\|case.run error\\|model execution error" "$log_file"; then
    run_state="failed"
  elif [ "$rc" -eq 0 ]; then
    run_state="success"
  else
    run_state="failed"
  fi

  echo "${case},${script},${run_state},${start_time},${end_time},${rc},${log_file}" >> "$status_csv"
  echo "===== FINISHED ${case} status=${run_state} rc=${rc} at ${end_time} ====="

  if [ "$run_state" = "failed" ]; then
    echo "Stopping after failure: $case"
    exit 1
  fi
done
