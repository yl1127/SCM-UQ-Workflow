# Run Control Tools

These tools launch or benchmark E3SM SCM cases.

| Tool | Purpose | Status/log outputs |
| --- | --- | --- |
| `scripts/workflows/run_qmc_e3sm_scm_scripts.zsh` | Run original QMC scripts sequentially and stop on failure. | `qmc_design/e3sm_scm_qmc_run_status.csv`, `qmc_design/run_logs/` |
| `scripts/workflows/run_qmc_reuse_build_scripts.zsh` | Run QMC reuse-build cases. | `qmc_design/e3sm_scm_qmc_reuse_build_run_status.csv` |
| `scripts/workflows/run_qmc_reuse_build_benchmark.zsh` | Benchmark selected reuse-build cases. | `qmc_design/reuse_build_benchmark_walltime.csv` |
| `scripts/workflows/run_oat8_sensitive_reuse_build_scripts.zsh` | Run OAT8 sensitivity reuse-build cases. | `oat8_sensitive_design/oat8_sensitive_reuse_build_run_status.csv` |
| `scripts/workflows/run_mac_arm97_segments_parallel.zsh` | Run standalone Mac ARM97 segments in parallel. | `mac_arm97_segment_design/mac_arm97_segment_run_status.csv` |
| `scripts/workflows/run_arm97_experiment_segments_parallel.zsh` | General segmented manifest runner. | Manifest-local `experiment_run_status.csv`, `run_logs/` |
| `scripts/workflows/run_mac_scm_parallel_benchmark.zsh` | Benchmark local Mac SCM parallelism. | `mac_parallel_benchmark/` |

Set the external E3SM run directory with:

```sh
export SCM_RUNS="/path/to/SCM_runs"
```
