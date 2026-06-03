# Template Scripts

Template scripts used by the workflow generators:

| Template | Used by |
| --- | --- |
| `scripts/workflows/MAC_ARM97_reuse_baseline.csh` | Mac segmented ARM97 generators and benchmarks. |
| `scripts/workflows/ARM97_reuse_baseline.csh` | NERSC segmented ARM97 generator. |
| `e3sm_scm_stage1_run_scripts/scm_ARM97_baseline.csh` | Original QMC, QMC reuse-build, and OAT8 reuse-build generators. |

Generated `.csh` scripts live in:

```text
e3sm_scm_qmc_run_scripts/
e3sm_scm_qmc_run_scripts_reuse_build/
e3sm_scm_oat8_sensitive_reuse_build_scripts/
e3sm_scm_mac_arm97_segment_scripts/
arm97_experiments/*/*/scripts/
```
