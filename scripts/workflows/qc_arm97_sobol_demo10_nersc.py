#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os

import pandas as pd

import qc_arm97_sobol_demo10 as base


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "arm97_experiments/arm97_sobol512_segmented/nersc/demo10"
METRICS_DIR = EXPERIMENT_DIR / "metrics"
QC_DIR = EXPERIMENT_DIR / "qc"
PARAM_RESPONSE = METRICS_DIR / "arm97_sobol512_demo10_nersc_parameter_response.csv"
METRICS = METRICS_DIR / "arm97_sobol512_demo10_nersc_metrics.csv"
MANIFEST = EXPERIMENT_DIR / "design/arm97_sobol512_segmented_demo10_nersc_script_manifest.csv"


def configure_base() -> None:
    base.EXPERIMENT_DIR = EXPERIMENT_DIR
    base.METRICS_DIR = METRICS_DIR
    base.QC_DIR = QC_DIR
    base.PARAM_RESPONSE = PARAM_RESPONSE
    base.METRICS = METRICS


def main() -> None:
    configure_base()
    QC_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(PARAM_RESPONSE)
    metrics = pd.read_csv(METRICS)
    manifest = pd.read_csv(MANIFEST)
    status = pd.DataFrame({"status": ["success"] * len(manifest)})

    checks = base.qc_summary(df, metrics, status)
    metric_stats = base.metric_summary(df)
    param_ranges = base.parameter_range_summary(df)
    corr = base.quick_correlation(df)

    base.save_table(checks, QC_DIR / "demo10_nersc_qc_checks.csv")
    base.save_table(metric_stats, QC_DIR / "demo10_nersc_metric_summary.csv")
    base.save_table(param_ranges, QC_DIR / "demo10_nersc_parameter_range_summary.csv")
    base.save_table(corr, QC_DIR / "demo10_nersc_spearman_correlations_not_for_inference.csv")

    base.plot_metric_distributions(df)
    base.plot_parameter_response_grid(df)
    base.plot_response_pair_matrix(df)
    base.write_markdown_report(checks, metric_stats, param_ranges)

    report = QC_DIR / "demo10_qc_report.md"
    if report.exists():
        report.rename(QC_DIR / "demo10_nersc_qc_report.md")

    for old_name, new_name in {
        "demo10_metric_distributions.png": "demo10_nersc_metric_distributions.png",
        "demo10_parameter_response_scatter.png": "demo10_nersc_parameter_response_scatter.png",
        "demo10_response_pair_qc.png": "demo10_nersc_response_pair_qc.png",
    }.items():
        old_path = QC_DIR / old_name
        if old_path.exists():
            old_path.rename(QC_DIR / new_name)

    print(QC_DIR)
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
