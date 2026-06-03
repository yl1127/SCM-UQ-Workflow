# Case Generation Tools

These tools render concrete E3SM `.csh` case scripts from design CSVs and
template scripts.

| Tool | Purpose | Templates |
| --- | --- | --- |
| `scripts/workflows/generate_e3sm_scm_qmc_run_scripts.py` | Generate baseline QMC case scripts. | `e3sm_scm_stage1_run_scripts/scm_ARM97_baseline.csh` |
| `scripts/workflows/generate_e3sm_scm_qmc_reuse_build_run_scripts.py` | Generate QMC reuse-build case scripts. | `e3sm_scm_stage1_run_scripts/scm_ARM97_baseline.csh` |
| `scripts/workflows/generate_oat8_sensitive_reuse_build_design_and_scripts.py` | Generate OAT sensitivity case scripts and manifest. | `e3sm_scm_stage1_run_scripts/scm_ARM97_baseline.csh` |
| `scripts/workflows/generate_arm97_experiment.py` | Generate segmented Mac or NERSC scripts. | `scripts/workflows/MAC_ARM97_reuse_baseline.csh`, `scripts/workflows/ARM97_reuse_baseline.csh` |
| `scripts/workflows/generate_qmc64_segmented_scripts.py` | Generate segmented scripts from QMC64 design. | `scripts/workflows/MAC_ARM97_reuse_baseline.csh` |

Generated script directories are kept at the repository root:

```text
e3sm_scm_qmc_run_scripts/
e3sm_scm_qmc_run_scripts_reuse_build/
e3sm_scm_oat8_sensitive_reuse_build_scripts/
e3sm_scm_mac_arm97_segment_scripts/
arm97_experiments/
```
