from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "scripts/workflows/MAC_ARM97_reuse_baseline.csh"
OUT_SCRIPT_DIR = ROOT / "e3sm_scm_mac_arm97_segment_scripts"
OUT_DESIGN_DIR = ROOT / "mac_arm97_segment_design"
MANIFEST = OUT_SCRIPT_DIR / "mac_arm97_segment_script_manifest.csv"

CASE_PREFIX = "mac_ARM97_seg"
BASELINE_START = datetime(1997, 6, 19, 23, 29, 45)
SEGMENT_START = BASELINE_START - timedelta(days=1)
SEGMENT_COUNT = 52
SEGMENT_STRIDE = timedelta(hours=12)
SEGMENT_RUN_HOURS = 36
SPINUP_HOURS = 24
KEEP_HOURS = 12


def replace_one(text: str, pattern: str, replacement: str) -> str:
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"expected one replacement for pattern: {pattern}")
    return text


def seconds_of_day(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second


def render_script(template: str, row: dict[str, object]) -> str:
    text = template
    text = replace_one(
        text,
        r"^\s*setenv casename .*$",
        f"  setenv casename {row['case']}",
    )
    text = replace_one(
        text,
        r"^\s*set startdate = .*$",
        f"  set startdate = {row['start_date']} # Segment start date",
    )
    text = replace_one(
        text,
        r"^\s*set start_in_sec = .*$",
        f"  set start_in_sec = {row['start_seconds']} # Segment start time in seconds",
    )
    text = replace_one(
        text,
        r"^\s*set stop_option = .*$",
        "  set stop_option = nhours",
    )
    text = replace_one(
        text,
        r"^\s*set stop_n = .*$",
        f"  set stop_n = {SEGMENT_RUN_HOURS}",
    )
    return text


def main() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)

    OUT_SCRIPT_DIR.mkdir(exist_ok=True)
    OUT_DESIGN_DIR.mkdir(exist_ok=True)

    template = TEMPLATE.read_text()
    rows = []
    for idx in range(SEGMENT_COUNT):
        start = SEGMENT_START + idx * SEGMENT_STRIDE
        spinup_end = start + timedelta(hours=SPINUP_HOURS)
        end = start + timedelta(hours=SEGMENT_RUN_HOURS)
        keep_end = spinup_end + timedelta(hours=KEEP_HOURS)
        if keep_end != end:
            raise RuntimeError("segment keep window does not end at segment end")

        case = f"{CASE_PREFIX}_{idx:03d}"
        script = OUT_SCRIPT_DIR / f"{case}.csh"
        row = {
            "segment_index": idx,
            "case": case,
            "script": str(script),
            "start_datetime": start.isoformat(sep=" "),
            "start_date": start.strftime("%Y-%m-%d"),
            "start_seconds": seconds_of_day(start),
            "stop_option": "nhours",
            "stop_n": SEGMENT_RUN_HOURS,
            "spinup_hours": SPINUP_HOURS,
            "keep_hours": KEEP_HOURS,
            "keep_start_datetime": spinup_end.isoformat(sep=" "),
            "keep_end_datetime": end.isoformat(sep=" "),
            "baseline_start_datetime": BASELINE_START.isoformat(sep=" "),
        }
        script.write_text(render_script(template, row))
        script.chmod(0o755)
        rows.append(row)

    manifest = pd.DataFrame(rows)
    manifest.to_csv(MANIFEST, index=False)
    manifest.to_csv(OUT_DESIGN_DIR / "mac_arm97_segment_design.csv", index=False)

    print(f"generated segment scripts: {len(manifest)}")
    print(MANIFEST)


if __name__ == "__main__":
    main()
