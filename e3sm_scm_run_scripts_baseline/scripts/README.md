# NERSC Reusable Baseline Build

Use `build_nersc_reusable_e3sm.sh` on NERSC to build one ARM97 SCM baseline
case and keep its `build/e3sm.exe` for later reuse by generated segmented
experiments.

Example:

```sh
cd e3sm_scm_run_scripts_baseline/scripts
export E3SM_CODE_DIR="/path/to/E3SM"
export SCM_RUNS="${PSCRATCH}/SCM_runs"
export BASELINE_CASE="nersc_ARM97_reusable_baseline"
export NERSC_PROJECT="m2136"
./build_nersc_reusable_e3sm.sh
```

To check script generation without creating or building an E3SM case:

```sh
DRY_RUN=1 ./build_nersc_reusable_e3sm.sh
```

When the build succeeds, the script prints the reusable executable path:

```sh
export TEMPLATE_EXE_NERSC="${SCM_RUNS}/nersc_ARM97_reusable_baseline/build/e3sm.exe"
```

Use that `TEMPLATE_EXE_NERSC` value before running NERSC setup scripts generated
by `scripts/workflows/generate_arm97_experiment.py`.

The Mac baseline executable in this repository is a macOS arm64 binary and is
not usable on NERSC. This script produces the separate Linux/NERSC executable
needed for NERSC reuse-build workflows.
