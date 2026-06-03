#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE="$ROOT/scripts/workflows/MAC_ARM97_reuse_baseline.csh"
BENCH_ROOT="$ROOT/mac_parallel_benchmark"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
SCRIPT_DIR="$BENCH_ROOT/scripts/$RUN_ID"
LOG_DIR="$BENCH_ROOT/logs/$RUN_ID"
RESULTS="$BENCH_ROOT/mac_scm_parallel_benchmark_results_${RUN_ID}.csv"
SCM_RUNS="${SCM_RUNS:-/path/to/SCM_runs}"
OPENBLAS_LIB="/opt/homebrew/opt/openblas/lib/libopenblas.0.dylib"

if (($# > 0)); then
  CONCURRENCY_LIST=("$@")
else
  CONCURRENCY_LIST=(6 8 10 12)
fi

mkdir -p "$SCRIPT_DIR" "$LOG_DIR"

if [[ ! -e "$OPENBLAS_LIB" ]]; then
  echo "ERROR: OpenBLAS dylib not found: $OPENBLAS_LIB" >&2
  exit 2
fi

echo "run_id,concurrency,round_start_epoch,round_end_epoch,round_wall_seconds,success_count,failed_count,case_names" > "$RESULTS"

make_case_script() {
  local case_name="$1"
  local out_script="$SCRIPT_DIR/${case_name}.csh"

  perl -pe "s/setenv casename .*/setenv casename ${case_name}/" "$TEMPLATE" > "$out_script"
  perl -0pi -e 's/ln -sf \$template_exe \$case_build_dir\/e3sm\.exe/cp \$template_exe \$case_build_dir\/e3sm.exe\n  install_name_tool -change \@rpath\/libopenblas.0.dylib \/opt\/homebrew\/opt\/openblas\/lib\/libopenblas.0.dylib \$case_build_dir\/e3sm.exe/' "$out_script"
  chmod +x "$out_script"
  echo "$out_script"
}

case_succeeded() {
  local case_name="$1"
  local case_dir="$SCM_RUNS/$case_name"
  local history_file="$case_dir/run/case_scripts.eam.h0.1997-06-19-84585.nc"
  [[ -s "$history_file" ]] && return 0
  [[ -e "$case_dir/case_scripts/CaseStatus" ]] && grep -q "case.run success" "$case_dir/case_scripts/CaseStatus"
}

for concurrency in "${CONCURRENCY_LIST[@]}"; do
  round_tag="p$(printf '%02d' "$concurrency")"
  case_names=()
  pids=()

  echo "== Benchmark round: concurrency=$concurrency =="
  round_start=$(date +%s)

  for idx in $(seq 0 $((concurrency - 1))); do
    case_name="macbench_${RUN_ID}_${round_tag}_$(printf '%02d' "$idx")"
    case_names+=("$case_name")
    case_dir="$SCM_RUNS/$case_name"

    if [[ -e "$case_dir" ]]; then
      echo "ERROR: refusing to reuse existing case directory: $case_dir" >&2
      exit 2
    fi

    script_path="$(make_case_script "$case_name")"
    log_path="$LOG_DIR/${case_name}.log"
    csh "$script_path" > "$log_path" 2>&1 &
    pids+=("$!")
    sleep 2
  done

  failed_processes=0
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
      failed_processes=$((failed_processes + 1))
    fi
  done

  round_end=$(date +%s)
  success_count=0
  failed_count=0

  for case_name in "${case_names[@]}"; do
    if case_succeeded "$case_name"; then
      success_count=$((success_count + 1))
    else
      failed_count=$((failed_count + 1))
    fi
  done

  joined_cases="${(j:|:)case_names}"
  echo "$RUN_ID,$concurrency,$round_start,$round_end,$((round_end - round_start)),$success_count,$failed_count,$joined_cases" >> "$RESULTS"
  echo "concurrency=$concurrency wall_seconds=$((round_end - round_start)) success=$success_count failed=$failed_count process_failures=$failed_processes"
done

echo "$RESULTS"
