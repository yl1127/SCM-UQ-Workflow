from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
OUT = ROOT / "qmc_design"

CASES = ["000", "001", "002", "003"]


EVENT_PATTERNS = {
    "case_build_start": "case.build starting",
    "case_build_success": "case.build success",
    "case_run_start": "case.run starting",
    "model_start": "model execution starting",
    "model_success": "model execution success",
    "case_run_success": "case.run success",
    "case_submit_success": "case.submit success",
}


def parse_case_status(case: str) -> dict[str, datetime]:
    path = RUN_ROOT / case / "case_scripts" / "CaseStatus"
    text = path.read_text()
    events: dict[str, datetime] = {}
    for line in text.splitlines():
        match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}): (.*)$", line)
        if not match:
            continue
        when = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        message = match.group(2)
        for event, marker in EVENT_PATTERNS.items():
            if marker in message:
                events[event] = when
    return events


def seconds_between(events: dict[str, datetime], start: str, end: str):
    if start not in events or end not in events:
        return None
    return int((events[end] - events[start]).total_seconds())


def history_exists(case: str) -> bool:
    return bool(list((RUN_ROOT / case / "run").glob("*.eam.h0.*.nc")))


def main():
    wall = pd.read_csv(OUT / "reuse_build_benchmark_walltime.csv")
    rows = []

    for suffix in CASES:
        old_case = f"qmc_ARM97_{suffix}"
        reuse_case = f"qmc_ARM97_reuse_{suffix}"
        old_events = parse_case_status(old_case)
        reuse_events = parse_case_status(reuse_case)
        reuse_wall = int(wall.loc[wall["case"].eq(reuse_case), "wall_seconds"].iloc[0])

        old_build = seconds_between(old_events, "case_build_start", "case_build_success")
        old_model = seconds_between(old_events, "model_start", "model_success")
        old_build_to_submit = seconds_between(
            old_events, "case_build_start", "case_submit_success"
        )
        reuse_model = seconds_between(reuse_events, "model_start", "model_success")
        reuse_run_to_submit = seconds_between(
            reuse_events, "case_run_start", "case_submit_success"
        )

        rows.append(
            {
                "original_case": old_case,
                "reuse_case": reuse_case,
                "old_build_seconds": old_build,
                "old_model_seconds": old_model,
                "old_build_to_submit_seconds": old_build_to_submit,
                "reuse_build_seconds": 0,
                "reuse_model_seconds": reuse_model,
                "reuse_case_run_to_submit_seconds": reuse_run_to_submit,
                "reuse_script_wall_seconds": reuse_wall,
                "saved_vs_old_build_to_submit_seconds": old_build_to_submit
                - reuse_wall,
                "speedup_vs_old_build_to_submit": old_build_to_submit / reuse_wall,
                "old_history_exists": history_exists(old_case),
                "reuse_history_exists": history_exists(reuse_case),
                "reuse_used_symlink_exe": (
                    RUN_ROOT / reuse_case / "build" / "e3sm.exe"
                ).is_symlink(),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "reuse_build_timing_comparison.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "n_cases": len(df),
                "mean_old_build_seconds": df["old_build_seconds"].mean(),
                "mean_old_model_seconds": df["old_model_seconds"].mean(),
                "mean_old_build_to_submit_seconds": df[
                    "old_build_to_submit_seconds"
                ].mean(),
                "mean_reuse_model_seconds": df["reuse_model_seconds"].mean(),
                "mean_reuse_script_wall_seconds": df[
                    "reuse_script_wall_seconds"
                ].mean(),
                "mean_saved_seconds": df[
                    "saved_vs_old_build_to_submit_seconds"
                ].mean(),
                "mean_speedup": df["speedup_vs_old_build_to_submit"].mean(),
                "total_old_build_to_submit_seconds": df[
                    "old_build_to_submit_seconds"
                ].sum(),
                "total_reuse_script_wall_seconds": df[
                    "reuse_script_wall_seconds"
                ].sum(),
                "total_saved_seconds": df[
                    "saved_vs_old_build_to_submit_seconds"
                ].sum(),
            }
        ]
    )
    summary.to_csv(OUT / "reuse_build_timing_summary.csv", index=False)

    print(df.to_string(index=False))
    print()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
