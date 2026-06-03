# Design Generation Tools

These tools create parameter samples, design CSVs, and experiment definitions.

| Tool | Purpose | Main outputs |
| --- | --- | --- |
| `scripts/workflows/generate_e3sm_scm_qmc_design.py` | Build the original 64-sample QMC parameter design. | `qmc_design/` |
| `scripts/workflows/generate_oat8_sensitive_reuse_build_design_and_scripts.py` | Build OAT8 sensitivity design and matching reuse-build case scripts. | `oat8_sensitive_design/`, `e3sm_scm_oat8_sensitive_reuse_build_scripts/` |
| `scripts/workflows/generate_arm97_experiment.py` | General ARM97 segmented experiment generator for Mac or NERSC. | `arm97_experiments/` |
| `scripts/workflows/generate_qmc64_segmented_scripts.py` | Convert the QMC64 design into segmented ARM97 scripts. | `arm97_experiments/qmc64_segmented/` |
| `scripts/workflows/generate_arm97_nersc_demo10_from_sobol512.py` | Build NERSC demo10 scripts from the existing Sobol-512 design. | `arm97_experiments/arm97_sobol512_segmented/nersc/demo10/` |
| `scripts/workflows/generate_mac_arm97_segment_scripts.py` | Build standalone Mac ARM97 segment scripts. | `e3sm_scm_mac_arm97_segment_scripts/`, `mac_arm97_segment_design/` |

Shared parameter config:

```text
configs/params_arm97_core.yaml
```
