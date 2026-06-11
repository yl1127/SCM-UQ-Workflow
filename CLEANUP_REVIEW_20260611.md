# Cleanup Review 2026-06-11

Generated or local-only workflow artifacts were moved to:

`_cleanup_review_20260611/generated/`

The cleanup directory is ignored by Git via `_cleanup_review_*/`.

Moved candidates:

- `.local_cache/` - local matplotlib/font cache.
- `scripts/__pycache__/` - Python bytecode cache.
- `scripts/workflows/__pycache__/` - Python bytecode cache.
- `baseline_arm97_comparison/` - generated comparison CSVs and figures.
- `arm97_experiments_0602/` - generated ARM97 experiment outputs, logs, stitched NetCDF files, and figures.
- `e3sm_scm_run_scripts_baseline/baseline-output/` - generated E3SM build/run output and baseline history.

Full file inventory:

`_cleanup_review_20260611/cleanup_manifest.csv`

Restore examples:

```bash
mv _cleanup_review_20260611/generated/arm97_experiments_0602 .
mv _cleanup_review_20260611/generated/baseline_arm97_comparison .
mv _cleanup_review_20260611/generated/e3sm_scm_run_scripts_baseline/baseline-output e3sm_scm_run_scripts_baseline/
```

Notes:

- No tracked files were moved into the cleanup directory.
- The default comparison scripts expect local generated data paths; restore or regenerate those outputs before rerunning analyses that need baseline history or stitched NetCDF files.
