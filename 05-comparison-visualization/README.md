# Comparison and Visualization Tools

These tools compare model output against baselines, observations, or timing
records, and generate figures and summary CSVs.

| Tool | Purpose | Main outputs |
| --- | --- | --- |
| `scripts/workflows/compare_arm97_baseline_vs_observation.py` | Compare baseline ARM97 SCM output with the ARM97 observation file. | `baseline_arm97_comparison/` |
| `scripts/workflows/compare_mac_arm97_stitched_vs_baseline.py` | Compare stitched Mac ARM97 run against baseline output. | `mac_arm97_segment_design/comparison/` |
| `scripts/workflows/plot_mac_arm97_stitched_vs_baseline.py` | Plot stitched-vs-baseline differences. | `mac_arm97_segment_design/comparison/figures/` |
| `scripts/workflows/plot_mac_arm97_stitched_vs_observation.py` | Plot stitched output against ARM97 observations. | `mac_arm97_segment_design/comparison/figures_observation/` |
| `scripts/workflows/compare_oat8_reuse_vs_qmc_timing.py` | Compare OAT8 reuse-build timing against original QMC timing. | `oat8_sensitive_design/`, `docs/reports/oat8_reuse_build_timing_report.md` |
| `scripts/workflows/compare_qmc_reuse_build_timing.py` | Parse CaseStatus timing for QMC reuse-build tests. | `qmc_design/` |
