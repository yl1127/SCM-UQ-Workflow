# SCM-UQ Workflow

Workflow tools for ARM97 E3SM single-column model uncertainty quantification
experiments. This repository contains the code, templates, configuration, and
documentation needed to regenerate designs, render E3SM case scripts, launch
runs, postprocess outputs, run QC, and build notebooks/figures/decks.

It intentionally does not include generated model output, downloaded NetCDF
history files, E3SM source code, or machine-local inputdata.

## Workflow Stages

1. `01-design-generation/` - QMC, OAT, ARM97, and segmented experiment design tools.
2. `02-case-generation/` - tools that render E3SM case scripts and manifests.
3. `03-run-control/` - local Mac and NERSC run orchestration helpers.
4. `04-postprocess-qc/` - stitching, metrics extraction, QC, and sensitivity analysis tools.
5. `05-comparison-visualization/` - comparison and plotting scripts.
6. `06-notebook-tools/` - scripts that generate interactive notebooks.
7. `07-presentation/` - deck-building tool.
8. `templates/` - notes about E3SM template scripts used by generators.
9. `manifests/` - machine-readable tool inventory.

## Install

Python dependencies:

```sh
python3 -m pip install -r requirements.txt
```

or with conda:

```sh
conda env create -f environment.yml
conda activate scm-uq-workflow
```

Presentation generation uses Node:

```sh
npm install
```

## Configure

Copy the environment example and set paths for your machine:

```sh
cp examples/env.example .env
source .env
```

Important variables:

- `SCM_RUNS` - directory containing E3SM SCM case directories.
- `E3SM_CODE_DIR` - E3SM source checkout used by generated case scripts.
- `ARM97_IOP_FILE` - ARM97 IOP forcing/observation NetCDF file.
- `TEMPLATE_EXE` - optional pre-built E3SM executable for reuse-build workflows.
- `SCM_UQ_EXTRA_PATH` - optional compiler/runtime binary path additions.

## Run

Run commands from this repository root:

```sh
python3 scripts/workflows/generate_arm97_experiment.py --help
python3 scripts/workflows/generate_qmc64_segmented_scripts.py --help
./scripts/workflows/run_arm97_experiment_segments_parallel.zsh
```

The workflow scripts compute the repository root from their own location, but
running from the root keeps relative output paths and logs predictable.

## Example: 14-Parameter QMC Stitched Scripts

This example generates ARM97 Mac scripts for:

- 14 PPE tuning parameters with explicit lower/upper ranges transcribed from
  `tuning-parameters-from-PPE-paper copy.docx`.
- QMC sampling with `QMCPy DigitalNetB2`, matching the first QMC method used in
  this project.
- Stitched workflow mode, meaning each sample is split into 52 overlapping
  36-hour segment scripts intended for later stitching.
- `14 * 50 = 700` QMC samples.
- Fixed seed: `20260602`.

The parameter range file is:

```text
examples/params_arm97_14.yaml
```

The YAML maps the PPE paper names to E3SM namelist names used by the templates,
for example `dp1 -> cldfrc_dp1`, `dmpdz -> zmconv_dmpdz`,
`gamma_coef -> clubb_gamma_coef`, and `c6rt -> clubb_C6rt`.

Generate the scripts:

```sh
python3 scripts/workflows/generate_arm97_experiment.py \
  --platform mac \
  --experiment arm97_qmc14x50_stitched_seed20260602 \
  --design digitalnetb2 \
  --n-samples 700 \
  --seed 20260602 \
  --params examples/params_arm97_14.yaml \
  --segment-mode 52x1.5day \
  --out-root arm97_experiments \
  --case-prefix mac_ARM97_qmc14x50
```

Expected generated files:

```text
arm97_experiments/arm97_qmc14x50_stitched_seed20260602/mac/design/arm97_qmc14x50_stitched_seed20260602_samples.csv
arm97_experiments/arm97_qmc14x50_stitched_seed20260602/mac/design/arm97_qmc14x50_stitched_seed20260602_script_manifest.csv
arm97_experiments/arm97_qmc14x50_stitched_seed20260602/mac/scripts/*.csh
```

Expected counts:

```text
samples: 700
segment scripts: 700 * 52 = 36400
seed column in samples CSV: 20260602
sampler column in samples CSV: QMCPy DigitalNetB2
```

Run the generated segment scripts with the manifest runner:

```sh
export SCM_RUNS="/path/to/SCM_runs"

MANIFEST="arm97_experiments/arm97_qmc14x50_stitched_seed20260602/mac/design/arm97_qmc14x50_stitched_seed20260602_script_manifest.csv" \
MAX_JOBS=52 \
./scripts/workflows/run_arm97_experiment_segments_parallel.zsh
```

Notes:

- `--segment-mode 52x1.5day` is the stitched workflow mode. It generates
  52 segment scripts per QMC sample, with metadata columns showing the kept
  12-hour window for each segment.
- `--segment-mode full26day` generates one 26-day script per sample and does
  not require stitching.
- `--design digitalnetb2` uses `qmcpy.DigitalNetB2`, the same QMC sampler family
  used by the original `qmc_design/e3sm_scm_qmc_64_design.csv` workflow.
- The command above uses 700 samples because the requested design is `14 * 50`.
- QMCPy `DigitalNetB2` natively draws powers of two. If `--n-samples` is not a
  power of two, the generator draws the next power of two and truncates to the
  requested count. For example, `--n-samples 70` draws 128 points and keeps the
  first 70.

## NERSC Small-Batch Test Before Full Run

Before running the full 70-sample experiment on NERSC, generate a small test
with the same 14-parameter design, sampler, seed, and stitched segment mode.
This example uses 2 samples, so it creates `2 * 52 = 104` segment cases.

Generate the NERSC smoke-test scripts:

```sh
python3 scripts/workflows/generate_arm97_experiment.py \
  --platform nersc \
  --experiment arm97_qmc14x5_nersc_smoke2_seed20260602 \
  --design digitalnetb2 \
  --n-samples 2 \
  --seed 20260602 \
  --params examples/params_arm97_14.yaml \
  --segment-mode 52x1.5day \
  --out-root nersc_experiments_0602 \
  --case-prefix nersc_ARM97_qmc14x5_smoke
```

The generated NERSC run directory is:

```text
nersc_experiments_0602/arm97_qmc14x5_nersc_smoke2_seed20260602/nersc/
```

On NERSC, from that generated directory, set machine-specific paths:

```sh
export SCM_RUNS="${PSCRATCH}/SCM_runs"
export E3SM_CODE_DIR="/path/to/E3SM"
export TEMPLATE_EXE="/path/to/baseline/build/e3sm.exe"
```

Set up the E3SM cases:

```sh
MAX_SETUP_JOBS=8 ./setup_cases_nersc.sh
```

Submit the smoke-test bundle:

```sh
sbatch --export=ALL,MAX_CONCURRENT=104 run_bundle_nersc.sh
```

After the smoke test succeeds, generate the full 70-sample NERSC batch:

```sh
python3 scripts/workflows/generate_arm97_experiment.py \
  --platform nersc \
  --experiment arm97_qmc14x5_nersc_seed20260602 \
  --design digitalnetb2 \
  --n-samples 70 \
  --seed 20260602 \
  --params examples/params_arm97_14.yaml \
  --segment-mode 52x1.5day \
  --out-root nersc_experiments_0602 \
  --case-prefix nersc_ARM97_qmc14x5
```

Then run the full batch from:

```text
nersc_experiments_0602/arm97_qmc14x5_nersc_seed20260602/nersc/
```

For the full run, start with:

```sh
MAX_SETUP_JOBS=8 ./setup_cases_nersc.sh
sbatch --export=ALL,MAX_CONCURRENT=120 run_bundle_nersc.sh
```

The generated `run_bundle_nersc.sh` uses one CPU node, `regular` QOS, and a
4-hour walltime by default. Edit the `#SBATCH --account`, `#SBATCH --time`, and
`MAX_CONCURRENT` settings if your NERSC project or queue behavior requires it.

## Quick Links

- Full tool inventory: `manifests/tools.csv`
- One-page command reference: `00-overview/COMMANDS.md`
- Workflow scripts: `scripts/workflows/`
- Notebook builders: `scripts/`
- GitHub release checklist: `docs/GITHUB_RELEASE_CHECKLIST.md`

## License

No license has been selected in this folder yet. Add a license before publishing
if you want others to have explicit reuse rights.
