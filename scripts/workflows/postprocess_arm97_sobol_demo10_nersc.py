#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os

import pandas as pd

import postprocess_arm97_sobol_demo10 as base


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "arm97_experiments/arm97_sobol512_segmented/nersc/demo10"
DESIGN_DIR = EXPERIMENT_DIR / "design"
MANIFEST = DESIGN_DIR / "arm97_sobol512_segmented_demo10_nersc_script_manifest.csv"
SAMPLES = DESIGN_DIR / "arm97_sobol512_segmented_demo10_nersc_samples.csv"
SCM_RUNS = EXPERIMENT_DIR / "SCM_runs_download"
STITCHED_DIR = EXPERIMENT_DIR / "stitched"
METRICS_DIR = EXPERIMENT_DIR / "metrics"
METRICS_CSV = METRICS_DIR / "arm97_sobol512_demo10_nersc_metrics.csv"
PARAM_RESPONSE_CSV = METRICS_DIR / "arm97_sobol512_demo10_nersc_parameter_response.csv"


def configure_base() -> None:
    base.EXPERIMENT_DIR = EXPERIMENT_DIR
    base.DESIGN_DIR = DESIGN_DIR
    base.MANIFEST = MANIFEST
    base.SAMPLES = SAMPLES
    base.SCM_RUNS = SCM_RUNS
    base.STITCHED_DIR = STITCHED_DIR
    base.METRICS_DIR = METRICS_DIR
    base.METRICS_CSV = METRICS_CSV
    base.PARAM_RESPONSE_CSV = PARAM_RESPONSE_CSV


def validate_downloaded_history(manifest: pd.DataFrame) -> None:
    missing = []
    for case_name in manifest["case"].astype(str):
        run_dir = SCM_RUNS / case_name / "run"
        if not list(run_dir.glob("*.eam.h0.*.nc")):
            missing.append(case_name)
    if missing:
        preview = "\n".join(missing[:20])
        raise SystemExit(f"missing {len(missing)} history files under {SCM_RUNS}:\n{preview}")


def main() -> None:
    configure_base()
    STITCHED_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(MANIFEST)
    validate_downloaded_history(manifest)

    sample_table = pd.read_csv(SAMPLES)
    sample_indices = sorted(manifest["sample_index"].unique())
    metrics_rows = []
    for sample_index in sample_indices:
        sample_manifest = manifest[manifest["sample_index"] == sample_index]
        sample_case = str(sample_manifest["sample_case"].iloc[0])
        out_path = base.stitch_sample(sample_case, sample_manifest)
        metrics_rows.append(base.extract_metrics(int(sample_index), sample_case, out_path))
        print(f"stitched sample {sample_index:03d}: {out_path}")

    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(METRICS_CSV, index=False)

    demo_samples = sample_table[sample_table["sample_index"].isin(sample_indices)].copy()
    merged = demo_samples.merge(metrics, on=["sample_index", "case"], how="left")
    merged.to_csv(PARAM_RESPONSE_CSV, index=False)

    print(f"metrics: {METRICS_CSV}")
    print(f"parameter-response table: {PARAM_RESPONSE_CSV}")


if __name__ == "__main__":
    main()
