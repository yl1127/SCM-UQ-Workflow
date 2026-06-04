# Postprocess and QC Tools

These tools convert raw model histories into stitched files, metrics, QC tables,
and sensitivity analysis outputs.

| Tool | Purpose | Main outputs |
| --- | --- | --- |
| `scripts/workflows/stitch_mac_arm97_segments.py` | Stitch standalone Mac ARM97 segment history files. | `mac_arm97_segment_design/mac_ARM97_26day_stitched_from_segments.nc` |
| `scripts/workflows/postprocess_arm97_experiment.py` | Stitch any generated ARM97 segmented experiment by sample and extract metrics. | Experiment-local `stitched/`, `metrics/` |
| `scripts/workflows/postprocess_arm97_sobol_demo10.py` | Stitch demo10 Mac segmented runs and extract metrics. | `arm97_experiments/arm97_sobol512_segmented/mac/stitched/`, `metrics/` |
| `scripts/workflows/postprocess_arm97_sobol_demo10_nersc.py` | Postprocess downloaded NERSC demo10 histories. | `arm97_experiments/arm97_sobol512_segmented/nersc/demo10/stitched/`, `metrics/` |
| `scripts/workflows/qc_arm97_sobol_demo10.py` | QC Mac demo10 parameter responses and metrics. | `arm97_experiments/arm97_sobol512_segmented/mac/qc/demo10/` |
| `scripts/workflows/qc_arm97_sobol_demo10_nersc.py` | QC NERSC demo10 parameter responses and metrics. | `arm97_experiments/arm97_sobol512_segmented/nersc/demo10/qc/` |
| `scripts/workflows/analyze_qmc_results.py` | Analyze QMC SCM responses and selected sensitive parameters. | `qmc_analysis/` |
| `scripts/workflows/analyze_oat8_sensitive_results.py` | Analyze OAT8 sensitivity response metrics. | `oat8_analysis/` |
| `scripts/workflows/analyze_e3sm_scm_stage1.py` | Analyze stage1 SCM runs. | `analysis_outputs/` |
