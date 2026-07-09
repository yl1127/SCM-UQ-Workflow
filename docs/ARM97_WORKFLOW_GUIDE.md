# ARM97 SCM-UQ Workflow Guide

This document expands the README workflow diagram into concrete files, options,
outputs, and notes. It reflects the current rebuilt repository layout:

```text
configs/
scripts_baseline/
src/workflows/
notebooks/
cases/
```

## 0. Environment And Local Paths

Files:

- `configs/env.example`
- `.env` at repository root, local only and ignored by git

Setup:

```sh
cp configs/env.example .env
source .env
```

Important variables:

- `SCM_RUNS`: root directory where E3SM SCM cases are created.
- `E3SM_CODE_DIR`: E3SM checkout containing `cime/scripts`.
- `ARM97_IOP_FILE`: ARM97 IOP forcing/observation NetCDF.
- `SCM_UQ_EXTRA_PATH`: optional compiler/runtime path additions.
- `TEMPLATE_EXE`, `TEMPLATE_EXE_MAC`, `TEMPLATE_EXE_NERSC`: optional later reuse-build executables.

Current-stage note:

- Baseline and reusable executable paths can stay empty while validating the plain ARM97 SCM workflow.
- The IOP file used by the current notebook/post-processing is `scripts_baseline/ARM97_iopfile_4scam.nc`.
- For E3SM runtime, the IOP file must also be available under E3SM inputdata at `atm/cam/scam/iop/ARM97_iopfile_4scam.nc`.

## 1. Choose Parameters And Sampling Strategy

Files:

- `configs/params_arm97_core.yaml`
- `src/workflows/generate_arm97_experiment.py`

Parameter file structure:

```yaml
parameters:
  - name: clubb_C1
    baseline: 1.335
    lower: 1.0
    upper: 5.0
    format: float
```

Required parameter fields:

- `name`: exact EAM namelist variable name.
- `baseline`: default or baseline value.
- `lower`, `upper`: perturbation bounds.
- `format`: formatting style used when rendering C-shell scripts.

Supported `format` values in the generator:

- `float`: compact floating-point string.
- `D0`: Fortran double with `D0` suffix.
- `D`: Fortran exponent using `D`.
- `E`: uppercase scientific notation.
- `e`: lowercase scientific notation.
- `int`: rounded integer.

Sampling options in `generate_arm97_experiment.py`:

- `baseline`: only baseline sample.
- `lhs`: Latin hypercube.
- `halton`: simple Halton sequence.
- `sobol`: SciPy Sobol.
- `digitalnetb2` or `qmc-digitalnetb2`: QMCPy DigitalNetB2.
- `oat`: one-at-a-time low/high perturbations around 0.5 normalized values.

Notes:

- Parameter names are case-sensitive for EAM namelist validation. For example, local EAM accepts `clubb_C1`, not `clubb_c1`.
- `digitalnetb2` requires `qmcpy`; `sobol` requires `scipy`.
- Non-power-of-two DigitalNetB2 sample counts are generated at the next power of two and truncated.
- `--include-baseline` prepends a baseline sample before perturbed samples.

## 2. Generate Experiment Design

File:

- `src/workflows/generate_arm97_experiment.py`

Typical command:

```sh
python3 src/workflows/generate_arm97_experiment.py \
  --platform mac \
  --experiment arm97_qmc_demo \
  --design digitalnetb2 \
  --n-samples 8 \
  --seed 20260602 \
  --params configs/params_arm97_core.yaml \
  --segment-mode 52x1.5day \
  --out-root arm97_experiments \
  --case-prefix mac_ARM97_demo \
  --overwrite
```

Important options:

- `--platform`: `mac` or `nersc`.
- `--experiment`: experiment name used in output paths and CSV filenames.
- `--design`: sampling strategy.
- `--n-samples`: number of perturbed samples.
- `--seed`: random/QMC seed.
- `--params`: parameter YAML.
- `--out-root`: root output directory for generated experiment scripts.
- `--case-prefix`: case-name prefix.
- `--segment-mode`: `52x1.5day` or `full26day`.
- `--overwrite`: allow replacing already generated scripts.

Outputs:

```text
<out-root>/<experiment>/<platform>/design/*_samples.csv
<out-root>/<experiment>/<platform>/design/*_script_manifest.csv
<out-root>/<experiment>/<platform>/scripts/*.csh
```

Current repository layout:

- Generator templates are under `src/workflows/`.
- The Mac platform default is `scripts_baseline/run_e3sm_scm_ARM97_0706.csh`.
- Pass `--template src/workflows/MAC_ARM97_reuse_baseline.csh` or `--template src/workflows/ARM97_reuse_baseline.csh` only when you want to override the platform default.

## 3. Choose The Platform

Files:

- `scripts_baseline/run_e3sm_scm_ARM97_0706.csh`
- `src/workflows/MAC_ARM97_reuse_baseline.csh`
- `src/workflows/ARM97_reuse_baseline.csh`
- `scripts_baseline/run_e3sm_scm_ARM97_prect_cosp.csh`

Platform affects:

- CIME `machine`.
- Project/account settings.
- Batch vs local `--no-batch` execution.
- Reusable executable compatibility.
- Compiler/runtime `PATH`.

Mac notes:

- `machine` should be `Mac` for local Mac runs.
- `submit_to_queue false` should use `case.submit --no-batch`.
- `SCM_UQ_EXTRA_PATH` may be needed for compilers and runtime tools.

NERSC notes:

- Reusable executables are platform-specific. A Mac `e3sm.exe` cannot be used on NERSC.
- NERSC normally uses batch submission and an NERSC-built reusable executable if reuse-build is enabled.

## 4. Stitched Setting

Files:

- `src/workflows/generate_arm97_experiment.py`
- `src/workflows/run_arm97_experiment_segments_parallel.zsh`
- `src/workflows/postprocess_arm97_experiment.py`

Modes:

- `full26day`: one complete 26-day case per sample.
- `52x1.5day`: segmented stitched mode.

Current stitched convention:

- Segment count: 26 for the 26-day ARM97 window.
- Each segment length: 36 hours.
- Segment start stride: 24 hours, so restart points occur at the same time each day.
- Spinup discarded: first 12 hours of each segment.
- Kept window: final 24 hours of each segment.
- Stitching boundaries are aligned to the same time each day, starting from the baseline ARM97 output-window time.
- Duplicate boundary times must be removed during stitching.

Important caution:

- Confirm the generator manifest columns `spinup_hours`, `keep_hours`, `keep_start`, and `keep_end` before large runs.
- Do not assume every old script or old generated experiment uses the same stitched convention.
- For time-sensitive comparisons, always validate the final stitched time axis before plotting.

## 5. Render Scripts

Files:

- `src/workflows/generate_arm97_experiment.py`
- Template C-shell scripts under `src/workflows/`
- Minimal single-case scripts under `scripts_baseline/`

What rendering does:

- Replaces `casename`.
- Replaces `startdate`, `start_in_sec`, `stop_option`, `stop_n`.
- Replaces selected EAM parameter namelist values.
- Writes one C-shell script per case or segment.
- Writes a CSV manifest used by runners.

Key outputs:

```text
*_script_manifest.csv
*_samples.csv
*.csh rendered case scripts
```

Notes:

- Rendered scripts are plain C-shell scripts that call CIME commands.
- If the template lacks a parameter line, rendering will fail because the replacement pattern cannot be found.
- Keep script templates close to the E3SM version being used; namelist variable names can change across E3SM versions.

## 6. Run SCM Cases

Files:

- `scripts_baseline/run_e3sm_scm_ARM97.csh`
- `scripts_baseline/run_e3sm_scm_ARM97_prect_cosp.csh`
- `cases/run_e3sm_scm_ARM97/run_e3sm_scm_ARM97.csh`
- `src/workflows/run_arm97_experiment_segments_parallel.zsh`

Minimal single-case command:

```sh
source .env
CASE_DIR="cases/run_e3sm_scm_ARM97"
./"$CASE_DIR/run_e3sm_scm_ARM97.csh"
```

Segmented batch command:

```sh
source .env
MANIFEST=<experiment>/<platform>/design/<experiment>_script_manifest.csv \
STATUS=<experiment>/<platform>/design/experiment_run_status.csv \
MAX_JOBS=10 \
./src/workflows/run_arm97_experiment_segments_parallel.zsh
```

Runner options through environment variables:

- `MANIFEST`: required path to rendered script manifest.
- `SCM_RUNS`: case root; usually from `.env`.
- `MAX_JOBS`: maximum concurrent C-shell case scripts.
- `STATUS`: status CSV path; defaults next to manifest.
- `LOG_DIR`: per-case log directory; defaults next to manifest.
- `GROUP_BY_SAMPLE`: when `true`, waits between sample groups.

Runner statuses:

- `success`: script ran and history file exists.
- `skipped_existing_success`: history file already exists.
- `skipped_existing_case_dir`: case directory exists but no completed history file was found.
- `failed`: C-shell script returned non-zero.
- `failed_no_history`: script returned success but no history file was found.

Output locations:

```text
$SCM_RUNS/<case>/case_scripts/
$SCM_RUNS/<case>/build/
$SCM_RUNS/<case>/run/*.eam.h0.*.nc
```

Notes:

- Existing case directories can block reruns. Rename or remove only when you are sure they are disposable.
- Build logs are under `$SCM_RUNS/<case>/build`.
- Runtime logs are under `$SCM_RUNS/<case>/run`.
- Compressed logs need `gzip -cd` or `gzcat`.
- Use `case_scripts/CaseStatus` to confirm `case.build success`, `model execution success`, and `case.run success`.

## 7. Post Processing

Files:

- `src/workflows/postprocess_arm97_experiment.py`
- `cases/run_e3sm_scm_ARM97/`

For stitched experiments:

```sh
python3 src/workflows/postprocess_arm97_experiment.py \
  --experiment-dir <experiment>/<platform> \
  --manifest <experiment>/<platform>/design/<experiment>_script_manifest.csv \
  --samples <experiment>/<platform>/design/<experiment>_samples.csv \
  --status <experiment>/<platform>/design/experiment_run_status.csv \
  --scm-runs "$SCM_RUNS" \
  --stitch-backend nco
```

Recommended backend:

- `--stitch-backend nco`: use NCO `ncks` to slice each segment by computed
  `time` indices and `ncrcat` to concatenate along the record dimension.
- `--stitch-backend python`: legacy fallback that copies NetCDF records with
  Python.

If NCO is not on `PATH`, set `NCKS` and `NCRCAT`, or pass
`--ncks /path/to/ncks --ncrcat /path/to/ncrcat`.

Outputs:

```text
<experiment>/<platform>/stitched/*_stitched_26day.nc
<experiment>/<platform>/metrics/*_metrics.csv
<experiment>/<platform>/metrics/*_parameter_response.csv
```

For professor-recommended NCO time-window post-processing:

Files generated in this repository:

```text
cases/run_e3sm_scm_ARM97/arm97_model_ready.nc
cases/run_e3sm_scm_ARM97/arm97_iop_observation_model_window_nco.nc
```

Commands used:

```sh
CASE_DIR="cases/run_e3sm_scm_ARM97"
MODEL="$(ls -t "$SCM_RUNS/e3sm_scm_ARM97/run"/*.eam.h0.*.nc | head -n 1)"
OBS="scripts_baseline/ARM97_iopfile_4scam.nc"
NCKS="${NCKS:-ncks}"

"$NCKS" -O "$MODEL" "$CASE_DIR/arm97_model_ready.nc"
"$NCKS" -O -d time,72,1944 "$OBS" "$CASE_DIR/arm97_iop_observation_model_window_nco.nc"
```

Notes:

- NCO preserves NetCDF dimensions, record variables, and metadata better than ad hoc array concatenation.
- For stitched experiments, Python still reads the manifest and finds the exact
  keep-window indices, but NCO performs the actual time-dimension slicing and
  concatenation.
- The current observation slice is selected by absolute overlap with the model run using `bdate + tsec`.
- Model time range: `1997-06-19 23:29:45` to `1997-07-15 23:29:45`.
- Observation slice range: `1997-06-19 23:29:45.937500` to `1997-07-15 23:29:46`.

## 8. Extract Metrics And Response Tables

File:

- `src/workflows/postprocess_arm97_experiment.py`

Metrics currently extracted by `postprocess_arm97_experiment.py`:

- Scalar statistics for `TREFHT`, `TMQ`, `CLDTOT`, `FSNS`, `FLNS`, `LHFLX`, `SHFLX`, `PS`, `TS`.
- Profile statistics for `T`, `Q`, `CLOUD`, `CLDICE`, `CLDLIQ`.
- Precipitation statistics for `PRECC`, `PRECL`, and derived `PRECT` when both are present.

Outputs:

- Metrics CSV: one row per sample.
- Parameter-response CSV: sample design merged with metrics.

Notes:

- The current `PRECT/COSP` single-case run writes `PRECT` directly via `fincl1 = 'PRECT'`.
- Older metrics code may expect `PRECC + PRECL`; update metrics extraction before applying it to direct-`PRECT` outputs.

## 9. Compare, Visualize, And Interpret Results

Files:

- `cases/run_e3sm_scm_ARM97/ARM97_model_output_vs_observation_all_variables.ipynb`
- `notebooks/ARM97_model_output_vs_observation_all_variables.ipynb`
- `notebooks/observed_variable_pairs.csv`
- `notebooks/model_output_variables.csv`
- `notebooks/iop_observation_variables.csv`

Current recommended notebook:

```text
cases/run_e3sm_scm_ARM97/ARM97_model_output_vs_observation_all_variables.ipynb
```

Current notebook inputs:

```text
cases/run_e3sm_scm_ARM97/arm97_model_ready.nc
cases/run_e3sm_scm_ARM97/arm97_iop_observation_model_window_nco.nc
```

Static notebook outputs:

```text
cases/run_e3sm_scm_ARM97/notebook_outputs/arm97_model_output_vs_observation_all_variables/*.csv
cases/run_e3sm_scm_ARM97/notebook_outputs/arm97_model_output_vs_observation_all_variables/*.pdf
```

Time-alignment rule:

- Do not align observation with `tsec - tsec[0]`.
- Use `bdate + tsec` for observation absolute time.
- The old approach shifts observation by about one day for ARM97 and can make precipitation peaks look lagged.

Plotting notes:

- In Plotly, later traces are drawn on top of earlier traces.
- To keep observation visible, add model traces first and observation traces afterward.
- Legend order can be controlled independently with `legendrank`.
- For precipitation, consider using a thicker observation line or markers because both model and observation contain sharp peaks.

## 10. Reusable Compiled Model

Files:

- `scripts_baseline/run_e3sm_scm_ARM97_0706.csh`
- `src/workflows/MAC_ARM97_reuse_baseline.csh`
- `src/workflows/ARM97_reuse_baseline.csh`

Purpose:

- Avoid rebuilding E3SM for every case by linking or copying a compatible pre-built `e3sm.exe`.

Environment variables:

- `TEMPLATE_EXE`
- `TEMPLATE_EXE_MAC`
- `TEMPLATE_EXE_NERSC`

Notes:

- Reusable executables are platform-specific.
- A Mac executable cannot run on NERSC.
- Reuse-build should be added after the plain workflow is validated.
- Ensure the executable is built from the same E3SM checkout/configuration expected by the generated scripts.

## 11. Common Checks

Check a model output file:

```sh
ncdump -h cases/run_e3sm_scm_ARM97/arm97_model_ready.nc | sed -n '1,80p'
```

Check observation time range by inspecting the NetCDF header:

```sh
ncdump -h cases/run_e3sm_scm_ARM97/arm97_iop_observation_model_window_nco.nc | sed -n '1,80p'
```

Check run status:

```sh
sed -n '1,220p' "$SCM_RUNS/<case>/case_scripts/CaseStatus"
```

Check history files:

```sh
ls -lh "$SCM_RUNS/<case>/run"/*.eam.h0.*.nc
```

Check compressed logs:

```sh
gzip -cd "$SCM_RUNS/<case>/run/e3sm.log."*.gz | tail -80
```

## 12. Known Current Caveats

- The rebuilt layout uses only the core workflow files under `src/workflows`.
- `.DS_Store` files are present in several folders and should not be treated as workflow inputs.
- `.env` is local and must not be committed.
- Time alignment is a first-order scientific issue for ARM97 precipitation. Always verify `bdate + tsec` before interpreting precipitation lag.
- NCO post-processing currently uses a temporary conda environment at `/private/tmp/scm-uq-nco`.
