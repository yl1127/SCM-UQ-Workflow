#!/bin/bash -el

# Build one ARM97 SCM baseline executable on NERSC for later reuse by generated
# segmented experiments. This script creates the E3SM case and runs case.build,
# but intentionally does not submit or run the model.

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BASELINE_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
TEMPLATE_CSH="${BASELINE_DIR}/scm_ARM97_baseline.csh"

if [[ -z "${PSCRATCH:-}" && -z "${SCM_RUNS:-}" ]]; then
  echo "ERROR: set SCM_RUNS, or run on NERSC where PSCRATCH is available." >&2
  exit 2
fi

if [[ -z "${E3SM_CODE_DIR:-}" ]]; then
  echo "ERROR: set E3SM_CODE_DIR to your E3SM checkout on NERSC." >&2
  exit 2
fi

export SCM_RUNS="${SCM_RUNS:-${PSCRATCH}/SCM_runs}"
export BASELINE_CASE="${BASELINE_CASE:-nersc_ARM97_reusable_baseline}"
export NERSC_PROJECT="${NERSC_PROJECT:-m2136}"

CASE_DIR="${SCM_RUNS}/${BASELINE_CASE}"
TEMPLATE_EXE_NERSC="${CASE_DIR}/build/e3sm.exe"
GENERATED_CSH="${SCRIPT_DIR}/${BASELINE_CASE}.build_only.csh"

if [[ -x "${TEMPLATE_EXE_NERSC}" ]]; then
  echo "Reusable executable already exists:"
  echo "  ${TEMPLATE_EXE_NERSC}"
  echo
  echo "Use it with:"
  echo "  export TEMPLATE_EXE_NERSC=\"${TEMPLATE_EXE_NERSC}\""
  exit 0
fi

if [[ -d "${CASE_DIR}/case_scripts" ]]; then
  echo "ERROR: case already exists but no executable was found:" >&2
  echo "  ${CASE_DIR}" >&2
  echo "Choose a new BASELINE_CASE or inspect/remove the existing case manually." >&2
  exit 2
fi

python3 - "${TEMPLATE_CSH}" "${GENERATED_CSH}" "${BASELINE_CASE}" "${NERSC_PROJECT}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

template = Path(sys.argv[1])
out = Path(sys.argv[2])
case_name = sys.argv[3]
project = sys.argv[4]

text = template.read_text()

replacements = [
    (
        r"^\s*setenv casename .*$",
        f"  setenv casename {case_name}",
    ),
    (
        r"^\s*if \(! \$\?SCM_RUNS\) setenv SCM_RUNS .*$",
        "  if (! $?SCM_RUNS) setenv SCM_RUNS $PSCRATCH/SCM_runs",
    ),
    (
        r"^\s*if \(! \$\?E3SM_CODE_DIR\) setenv E3SM_CODE_DIR .*$",
        "  if (! $?E3SM_CODE_DIR) then\n"
        '    echo "ERROR: set E3SM_CODE_DIR to your E3SM checkout on NERSC."\n'
        "    exit 2\n"
        "  endif",
    ),
    (
        r"^\s*setenv machine .*$",
        "  setenv machine pm-cpu",
    ),
    (
        r"^\s*setenv projectname .*$",
        f"  setenv projectname {project}",
    ),
    (
        r"^\s*# module load python.*$",
        "  # NERSC modules should be loaded before invoking this script if needed.",
    ),
    (
        r"^\s*set input_data_dir = `\./xmlquery DIN_LOC_ROOT -value`$",
        "  set input_data_dir = /global/cfs/cdirs/e3sm/inputdata",
    ),
]

for pattern, replacement in replacements:
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"expected one replacement for pattern: {pattern}")

build_only = """# Build the case and stop after producing a reusable executable.
  ./case.build
  if ($status != 0) exit 1
  if (! -e $case_build_dir/e3sm.exe) then
    echo "ERROR: expected executable was not produced: $case_build_dir/e3sm.exe"
    exit 1
  endif
  echo "Reusable NERSC executable: $case_build_dir/e3sm.exe"
  exit
"""

text, count = re.subn(
    r"# Build the case\s*\n\s*\./case\.build\s*\n\n# Submit case to queue if set, else submit.*?\n\s*exit\s*$",
    build_only,
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise SystemExit("failed to replace final build-and-submit block")

out.write_text(text)
out.chmod(0o755)
PY

echo "Generated build-only csh script:"
echo "  ${GENERATED_CSH}"
echo
echo "Building baseline case:"
echo "  case: ${BASELINE_CASE}"
echo "  SCM_RUNS: ${SCM_RUNS}"
echo "  E3SM_CODE_DIR: ${E3SM_CODE_DIR}"
echo "  NERSC_PROJECT: ${NERSC_PROJECT}"
echo

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  csh -n "${GENERATED_CSH}"
  echo "DRY_RUN=1: generated script passed csh syntax check; build was not run."
  exit 0
fi

csh "${GENERATED_CSH}"

if [[ ! -x "${TEMPLATE_EXE_NERSC}" ]]; then
  echo "ERROR: build finished but executable is missing or not executable:" >&2
  echo "  ${TEMPLATE_EXE_NERSC}" >&2
  exit 1
fi

echo
echo "Reusable executable built:"
echo "  ${TEMPLATE_EXE_NERSC}"
echo
echo "Use it for later NERSC reuse-build runs with:"
echo "  export TEMPLATE_EXE_NERSC=\"${TEMPLATE_EXE_NERSC}\""
