#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "arm97_experiments/arm97_sobol512_segmented/mac"
METRICS_DIR = EXPERIMENT_DIR / "metrics"
QC_DIR = EXPERIMENT_DIR / "qc/demo10"
PARAM_RESPONSE = METRICS_DIR / "arm97_sobol512_demo10_parameter_response.csv"
METRICS = METRICS_DIR / "arm97_sobol512_demo10_metrics.csv"
STATUS = EXPERIMENT_DIR / "design/experiment_run_status.csv"
PARAMS = [
    "clubb_C1_numeric",
    "clubb_C8_numeric",
    "clubb_gamma_coef_numeric",
    "clubb_c_K10_numeric",
    "cldfrc_dp1_numeric",
    "cldfrc2m_rhmaxi_numeric",
    "ice_sed_ai_numeric",
    "zmconv_dmpdz_numeric",
    "zmconv_c0_lnd_numeric",
    "zmconv_c0_ocn_numeric",
]
RESPONSES = [
    "TREFHT_mean",
    "TMQ_mean",
    "CLDTOT_mean",
    "FSNS_mean",
    "FLNS_mean",
    "PRECT_mean_mm_day",
]


def save_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def qc_summary(df: pd.DataFrame, metrics: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    checks = []
    checks.append(
        {
            "check": "parameter_response_rows",
            "value": len(df),
            "expected": 10,
            "status": "pass" if len(df) == 10 else "fail",
        }
    )
    checks.append(
        {
            "check": "metrics_rows",
            "value": len(metrics),
            "expected": 10,
            "status": "pass" if len(metrics) == 10 else "fail",
        }
    )
    checks.append(
        {
            "check": "status_success_rows",
            "value": int((status["status"] == "success").sum()),
            "expected": 520,
            "status": "pass" if int((status["status"] == "success").sum()) == 520 else "fail",
        }
    )
    checks.append(
        {
            "check": "status_failed_rows",
            "value": int((status["status"] != "success").sum()),
            "expected": 0,
            "status": "pass" if int((status["status"] != "success").sum()) == 0 else "fail",
        }
    )
    checks.append(
        {
            "check": "time_records_all_1249",
            "value": int((df["time_records"] == 1249).sum()),
            "expected": 10,
            "status": "pass" if bool((df["time_records"] == 1249).all()) else "fail",
        }
    )
    checks.append(
        {
            "check": "time_start_consistent",
            "value": df["time_start"].nunique(),
            "expected": 1,
            "status": "pass" if df["time_start"].nunique() == 1 else "fail",
        }
    )
    checks.append(
        {
            "check": "time_end_consistent",
            "value": df["time_end"].nunique(),
            "expected": 1,
            "status": "pass" if df["time_end"].nunique() == 1 else "fail",
        }
    )
    numeric = df.select_dtypes(include=[np.number])
    checks.append(
        {
            "check": "numeric_missing_values",
            "value": int(numeric.isna().sum().sum()),
            "expected": 0,
            "status": "pass" if int(numeric.isna().sum().sum()) == 0 else "fail",
        }
    )
    checks.append(
        {
            "check": "numeric_infinite_values",
            "value": int(np.isinf(numeric.to_numpy()).sum()),
            "expected": 0,
            "status": "pass" if int(np.isinf(numeric.to_numpy()).sum()) == 0 else "fail",
        }
    )
    checks.append(
        {
            "check": "cldtot_mean_range",
            "value": f"{df['CLDTOT_mean'].min():.6g} to {df['CLDTOT_mean'].max():.6g}",
            "expected": "0 to 1",
            "status": "pass" if df["CLDTOT_mean"].between(0, 1).all() else "fail",
        }
    )
    checks.append(
        {
            "check": "prect_nonnegative_mean",
            "value": float(df["PRECT_mean_mm_day"].min()),
            "expected": ">= 0",
            "status": "pass" if (df["PRECT_mean_mm_day"] >= 0).all() else "fail",
        }
    )
    return pd.DataFrame(checks)


def metric_summary(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in RESPONSES if c in df.columns]
    rows = []
    for col in cols:
        s = df[col]
        rows.append(
            {
                "metric": col,
                "min": s.min(),
                "mean": s.mean(),
                "max": s.max(),
                "std": s.std(ddof=0),
                "range": s.max() - s.min(),
            }
        )
    return pd.DataFrame(rows)


def parameter_range_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in PARAMS:
        s = df[col]
        rows.append(
            {
                "parameter": col,
                "min_in_demo10": s.min(),
                "max_in_demo10": s.max(),
                "mean_in_demo10": s.mean(),
            }
        )
    return pd.DataFrame(rows)


def quick_correlation(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for param in PARAMS:
        for response in RESPONSES:
            if df[param].nunique() <= 1 or df[response].nunique() <= 1:
                corr = np.nan
            else:
                corr = float(df[[param, response]].corr(method="spearman").iloc[0, 1])
            rows.append({"parameter": param, "response": response, "spearman_demo10": corr})
    return pd.DataFrame(rows)


def plot_metric_distributions(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), constrained_layout=True)
    for ax, col in zip(axes.ravel(), RESPONSES):
        ax.hist(df[col], bins=min(6, len(df)), color="#4c78a8", edgecolor="white")
        ax.set_title(col)
        ax.set_xlabel(col)
        ax.set_ylabel("count")
    fig.suptitle("ARM97 demo10 scalar metric distributions")
    fig.savefig(QC_DIR / "demo10_metric_distributions.png", dpi=180)
    plt.close(fig)


def plot_parameter_response_grid(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(len(RESPONSES), len(PARAMS), figsize=(24, 13), constrained_layout=True)
    for i, response in enumerate(RESPONSES):
        for j, param in enumerate(PARAMS):
            ax = axes[i, j]
            ax.scatter(df[param], df[response], s=22, color="#2f6f7e", alpha=0.85)
            if i == 0:
                ax.set_title(param.replace("_numeric", ""), fontsize=8)
            if j == 0:
                ax.set_ylabel(response, fontsize=8)
            else:
                ax.set_yticklabels([])
            ax.tick_params(axis="both", labelsize=6)
    fig.suptitle("ARM97 demo10 parameter-response scatter matrix")
    fig.savefig(QC_DIR / "demo10_parameter_response_scatter.png", dpi=180)
    plt.close(fig)


def plot_response_pair_matrix(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(len(RESPONSES), len(RESPONSES), figsize=(13, 13), constrained_layout=True)
    for i, y in enumerate(RESPONSES):
        for j, x in enumerate(RESPONSES):
            ax = axes[i, j]
            if i == j:
                ax.hist(df[x], bins=min(6, len(df)), color="#72b7b2", edgecolor="white")
            else:
                ax.scatter(df[x], df[y], s=24, color="#8c6d31", alpha=0.85)
            if i == len(RESPONSES) - 1:
                ax.set_xlabel(x, fontsize=7)
            else:
                ax.set_xticklabels([])
            if j == 0:
                ax.set_ylabel(y, fontsize=7)
            else:
                ax.set_yticklabels([])
            ax.tick_params(axis="both", labelsize=6)
    fig.suptitle("ARM97 demo10 response-response QC")
    fig.savefig(QC_DIR / "demo10_response_pair_qc.png", dpi=180)
    plt.close(fig)


def write_markdown_report(checks: pd.DataFrame, metrics: pd.DataFrame, ranges: pd.DataFrame) -> None:
    def markdown_table(df: pd.DataFrame) -> str:
        text_df = df.copy()
        for col in text_df.columns:
            text_df[col] = text_df[col].map(lambda x: f"{x:.6g}" if isinstance(x, float) else str(x))
        lines = []
        columns = list(text_df.columns)
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for _, row in text_df.iterrows():
            lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
        return "\n".join(lines)

    report = QC_DIR / "demo10_qc_report.md"
    failed = checks[checks["status"] != "pass"]
    with report.open("w") as f:
        f.write("# ARM97 Sobol512 Demo10 QC Report\n\n")
        f.write("## Overall Status\n\n")
        f.write("PASS\n\n" if failed.empty else "FAIL\n\n")
        f.write("## Checks\n\n")
        f.write(markdown_table(checks))
        f.write("\n\n## Metric Summary\n\n")
        f.write(markdown_table(metrics))
        f.write("\n\n## Parameter Range Summary\n\n")
        f.write(markdown_table(ranges))
        f.write("\n\n## Figures\n\n")
        f.write("- `demo10_metric_distributions.png`\n")
        f.write("- `demo10_parameter_response_scatter.png`\n")
        f.write("- `demo10_response_pair_qc.png`\n")


def main() -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PARAM_RESPONSE)
    metrics = pd.read_csv(METRICS)
    status = pd.read_csv(STATUS)
    status = status[status["case"].astype(str).str.contains("mac_ARM97_arm97_sobol512_segmented_00")]

    checks = qc_summary(df, metrics, status)
    metric_stats = metric_summary(df)
    param_ranges = parameter_range_summary(df)
    corr = quick_correlation(df)

    save_table(checks, QC_DIR / "demo10_qc_checks.csv")
    save_table(metric_stats, QC_DIR / "demo10_metric_summary.csv")
    save_table(param_ranges, QC_DIR / "demo10_parameter_range_summary.csv")
    save_table(corr, QC_DIR / "demo10_spearman_correlations_not_for_inference.csv")

    plot_metric_distributions(df)
    plot_parameter_response_grid(df)
    plot_response_pair_matrix(df)
    write_markdown_report(checks, metric_stats, param_ranges)

    print(QC_DIR)
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
