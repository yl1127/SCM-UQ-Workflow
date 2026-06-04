# SCM-UQ Commands

Run these from the repository root unless noted otherwise.

## Design and Case Generation

```sh
python3 scripts/workflows/generate_e3sm_scm_qmc_design.py
python3 scripts/workflows/generate_e3sm_scm_qmc_run_scripts.py
python3 scripts/workflows/generate_e3sm_scm_qmc_reuse_build_run_scripts.py
python3 scripts/workflows/generate_oat8_sensitive_reuse_build_design_and_scripts.py
python3 scripts/workflows/generate_mac_arm97_segment_scripts.py
python3 scripts/workflows/generate_qmc64_segmented_scripts.py --help
python3 scripts/workflows/generate_arm97_experiment.py --help
python3 scripts/workflows/generate_arm97_nersc_demo10_from_sobol512.py --help
```

## Run Control

```sh
./scripts/workflows/run_qmc_e3sm_scm_scripts.zsh
./scripts/workflows/run_qmc_reuse_build_scripts.zsh
./scripts/workflows/run_qmc_reuse_build_benchmark.zsh
./scripts/workflows/run_oat8_sensitive_reuse_build_scripts.zsh
./scripts/workflows/run_mac_arm97_segments_parallel.zsh
MANIFEST="arm97_experiments/qmc64_segmented/mac/design/qmc64_segmented_script_manifest.csv" ./scripts/workflows/run_arm97_experiment_segments_parallel.zsh
./scripts/workflows/run_mac_scm_parallel_benchmark.zsh
```

## Postprocess and QC

```sh
python3 scripts/workflows/stitch_mac_arm97_segments.py
python3 scripts/workflows/postprocess_arm97_experiment.py --help
python3 scripts/workflows/postprocess_arm97_sobol_demo10.py
python3 scripts/workflows/postprocess_arm97_sobol_demo10_nersc.py
python3 scripts/workflows/qc_arm97_sobol_demo10.py
python3 scripts/workflows/qc_arm97_sobol_demo10_nersc.py
python3 scripts/workflows/analyze_qmc_results.py
python3 scripts/workflows/analyze_oat8_sensitive_results.py
python3 scripts/workflows/analyze_e3sm_scm_stage1.py
```

## Comparison and Visualization

```sh
python3 scripts/workflows/compare_arm97_baseline_vs_observation.py
python3 scripts/workflows/compare_mac_arm97_stitched_vs_baseline.py
python3 scripts/workflows/compare_oat8_reuse_vs_qmc_timing.py
python3 scripts/workflows/compare_qmc_reuse_build_timing.py
python3 scripts/workflows/plot_mac_arm97_stitched_vs_baseline.py
python3 scripts/workflows/plot_mac_arm97_stitched_vs_observation.py
```
