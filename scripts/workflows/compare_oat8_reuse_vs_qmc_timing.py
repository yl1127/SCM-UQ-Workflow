#!/usr/bin/env python3
from __future__ import annotations

import glob
import gzip
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


WORKDIR = Path(__file__).resolve().parents[2]
SCM_RUNS = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))

OAT_STATUS = WORKDIR / "oat8_sensitive_design/oat8_sensitive_reuse_build_run_status.csv"
OAT_DESIGN = WORKDIR / "oat8_sensitive_design/oat8_sensitive_64_design.csv"
QMC_STATUS = WORKDIR / "qmc_design/e3sm_scm_qmc_run_status.csv"

OUTDIR = WORKDIR / "oat8_sensitive_design"
CHECKED = OUTDIR / "oat8_sensitive_reuse_build_run_status_checked.csv"
COMPARISON = OUTDIR / "oat8_vs_original_qmc_timing_comparison.csv"
SUMMARY = OUTDIR / "oat8_vs_original_qmc_timing_summary.csv"
ANOMALIES = OUTDIR / "oat8_run_anomalies.csv"
REPORT = WORKDIR / "oat8_reuse_build_timing_report.md"


STATUS_TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}):? (.+)$")


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def case_status_text(case: str) -> str:
    path = SCM_RUNS / case / "case_scripts/CaseStatus"
    if not path.exists():
        return ""
    return path.read_text(errors="replace")


def newest_e3sm_log(case: str) -> tuple[Path | None, str]:
    run_dir = SCM_RUNS / case / "run"
    logs = sorted(glob.glob(str(run_dir / "e3sm.log.*")), key=os.path.getmtime)
    if not logs:
        return None, ""
    path = Path(logs[-1])
    if path.suffix == ".gz":
        return path, gzip.open(path, "rt", errors="replace").read()
    return path, path.read_text(errors="replace")


def has_history_file(case: str) -> bool:
    pattern = SCM_RUNS / case / "run" / "*.eam.h0.*.nc"
    return bool(glob.glob(str(pattern)))


def exe_reuse_state(case: str) -> str:
    exe = SCM_RUNS / case / "build/e3sm.exe"
    if not exe.exists():
        return "missing"
    if exe.is_symlink():
        return f"symlink->{os.readlink(exe)}"
    return "regular_file"


def case_status_elapsed(case: str) -> dict[str, float | str | None]:
    text = case_status_text(case)
    parsed: list[tuple[datetime, str]] = []
    for line in text.splitlines():
        match = STATUS_TIME_RE.match(line.strip())
        if match:
            parsed.append((parse_dt(match.group(1)), match.group(2)))

    def first_time(needle: str) -> datetime | None:
        for stamp, msg in parsed:
            if needle in msg:
                return stamp
        return None

    def last_time(needle: str) -> datetime | None:
        for stamp, msg in reversed(parsed):
            if needle in msg:
                return stamp
        return None

    start = first_time("case.submit starting")
    build_start = first_time("case.build starting")
    build_done = first_time("case.build success")
    submit_done = last_time("case.submit success")
    run_start = last_time("case.run starting")
    run_success = last_time("case.run success")
    run_error = last_time("case.run error")
    model_error = last_time("model execution error")
    latest_error = max([t for t in [run_error, model_error] if t is not None], default=None)

    return {
        "case_status_wall_seconds": (submit_done - start).total_seconds() if start and submit_done else None,
        "case_build_seconds": (build_done - build_start).total_seconds() if build_start and build_done else None,
        "case_run_seconds": (run_success - run_start).total_seconds() if run_start and run_success else None,
        "case_status_has_run_fail": bool(latest_error and (run_success is None or latest_error > run_success)),
        "case_status_has_run_success": bool(run_success and (latest_error is None or run_success > latest_error)),
    }


def actual_status(case: str) -> dict[str, object]:
    status_text = case_status_text(case)
    log_path, log_text = newest_e3sm_log(case)
    history = has_history_file(case)
    abnormal_log = any(
        phrase in log_text
        for phrase in [
            "exited improperly",
            "RUN FAIL",
            "ERROR:",
            "Traceback",
            "MPI_ABORT",
        ]
    )
    elapsed = case_status_elapsed(case)
    case_fail = bool(elapsed["case_status_has_run_fail"])
    case_success = bool(elapsed["case_status_has_run_success"])

    if case_fail or abnormal_log:
        checked = "run_fail_or_mpi_abnormal"
    elif case_success and history:
        checked = "success"
    elif history:
        checked = "history_exists_status_unclear"
    else:
        checked = "missing_history_or_incomplete"

    return {
        "checked_status": checked,
        "history_file_exists": history,
        "case_status_has_run_fail": case_fail,
        "case_status_has_run_success": case_success,
        "e3sm_log": str(log_path) if log_path else "",
        "e3sm_log_has_abnormal": abnormal_log,
        "build_exe_state": exe_reuse_state(case),
    }


def summarize(label: str, df: pd.DataFrame, seconds_col: str) -> dict[str, object]:
    values = pd.to_numeric(df[seconds_col], errors="coerce").dropna()
    return {
        "experiment_set": label,
        "n_cases": len(df),
        "n_with_time": len(values),
        "n_checked_success": int((df.get("checked_status", pd.Series(dtype=str)) == "success").sum()),
        "n_checked_anomaly": int((df.get("checked_status", pd.Series(dtype=str)) != "success").sum())
        if "checked_status" in df
        else "",
        "total_seconds": float(values.sum()) if len(values) else None,
        "total_hours": float(values.sum() / 3600) if len(values) else None,
        "mean_seconds": float(values.mean()) if len(values) else None,
        "median_seconds": float(values.median()) if len(values) else None,
        "min_seconds": float(values.min()) if len(values) else None,
        "max_seconds": float(values.max()) if len(values) else None,
    }


def main() -> None:
    oat = pd.read_csv(OAT_STATUS)
    design = pd.read_csv(OAT_DESIGN)[
        [
            "case",
            "varied_parameter",
            "level_index",
            "relative_perturbation",
            "relative_perturbation_percent",
            "baseline_numeric",
            "varied_value_numeric",
            "varied_value_fortran",
        ]
    ]
    oat = oat.merge(design, on=["case", "varied_parameter", "relative_perturbation_percent"], how="left")

    checked_rows = []
    for case in oat["case"]:
        checked_rows.append({**case_status_elapsed(case), **actual_status(case)})
    checked = pd.concat([oat.reset_index(drop=True), pd.DataFrame(checked_rows)], axis=1)
    checked.to_csv(CHECKED, index=False)

    qmc = pd.read_csv(QMC_STATUS)
    qmc = qmc[qmc["case"].str.match(r"qmc_ARM97_\d{3}$")].copy()
    qmc["wall_seconds"] = (
        pd.to_datetime(qmc["end_time"]) - pd.to_datetime(qmc["start_time"])
    ).dt.total_seconds()
    qmc_checked_rows = []
    for case in qmc["case"]:
        qmc_checked_rows.append({**case_status_elapsed(case), **actual_status(case)})
    qmc_checked = pd.concat([qmc.reset_index(drop=True), pd.DataFrame(qmc_checked_rows)], axis=1)

    comparison = pd.concat(
        [
            qmc_checked.assign(experiment_set="original_qmc_build_each_case"),
            checked.assign(experiment_set="oat8_reuse_prebuilt_e3sm_exe"),
        ],
        ignore_index=True,
        sort=False,
    )
    comparison.to_csv(COMPARISON, index=False)

    summary = pd.DataFrame(
        [
            summarize("original_qmc_build_each_case_all_64", qmc_checked, "wall_seconds"),
            summarize(
                "original_qmc_build_each_case_success_only",
                qmc_checked[qmc_checked["checked_status"] == "success"],
                "wall_seconds",
            ),
            summarize("oat8_reuse_prebuilt_e3sm_exe_all_64", checked, "wall_seconds"),
            summarize(
                "oat8_reuse_prebuilt_e3sm_exe_success_only",
                checked[checked["checked_status"] == "success"],
                "wall_seconds",
            ),
        ]
    )
    baseline_all = summary.loc[
        summary["experiment_set"] == "original_qmc_build_each_case_all_64", "mean_seconds"
    ].iloc[0]
    baseline_success = summary.loc[
        summary["experiment_set"] == "original_qmc_build_each_case_success_only", "mean_seconds"
    ].iloc[0]
    summary["mean_speedup_vs_original_qmc_all_64"] = baseline_all / summary["mean_seconds"]
    summary["mean_seconds_saved_vs_original_qmc_all_64"] = baseline_all - summary["mean_seconds"]
    summary["mean_speedup_vs_original_qmc_success_only"] = baseline_success / summary["mean_seconds"]
    summary["mean_seconds_saved_vs_original_qmc_success_only"] = baseline_success - summary["mean_seconds"]
    summary.to_csv(SUMMARY, index=False)

    anomalies = comparison[comparison.get("checked_status", "") != "success"].copy()
    anomalies.to_csv(ANOMALIES, index=False)

    oat_by_param = (
        checked.groupby(["varied_parameter", "checked_status"])
        .size()
        .reset_index(name="n_cases")
        .sort_values(["varied_parameter", "checked_status"])
    )

    lines = [
        "# OAT8 reuse-build timing report",
        "",
        "This report compares the new 64 one-at-a-time sensitive-parameter cases using a reused pre-built `e3sm.exe` against the earlier 64 QMC scripts that rebuilt each case.",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False, floatfmt=".2f"),
        "",
        "## OAT8 checked status by parameter",
        "",
        oat_by_param.to_markdown(index=False),
        "",
        "## Notes",
        "",
        "- `wall_seconds` is measured by the wrapper/runner around each script.",
        "- `checked_status` is re-evaluated from `CaseStatus`, the newest `e3sm.log.*`, history-file existence, and the `build/e3sm.exe` reuse state.",
        "- The old QMC and new OAT8 designs are different parameter designs, so timing is a workflow comparison, not a physics comparison.",
        "",
        "## Output files",
        "",
        f"- `{CHECKED.relative_to(WORKDIR)}`",
        f"- `{COMPARISON.relative_to(WORKDIR)}`",
        f"- `{SUMMARY.relative_to(WORKDIR)}`",
        f"- `{ANOMALIES.relative_to(WORKDIR)}`",
    ]
    REPORT.write_text("\n".join(lines) + "\n")

    print(summary.to_string(index=False))
    print()
    print("anomalies")
    print(anomalies[["experiment_set", "case", "checked_status", "wall_seconds", "e3sm_log"]].to_string(index=False))
    print()
    print(REPORT)


if __name__ == "__main__":
    main()
