from pathlib import Path
import os
import re

import numpy as np
import pandas as pd


TEMPLATE = Path("e3sm_scm_stage1_run_scripts/scm_ARM97_baseline.csh")
BASELINE = Path("qmc_design/e3sm_scm_qmc_baseline.csv")
SELECTED = Path("qmc_analysis/qmc_selected_8_sensitive_parameters.csv")
OUT_DESIGN_DIR = Path("oat8_sensitive_design")
OUT_SCRIPT_DIR = Path("e3sm_scm_oat8_sensitive_reuse_build_scripts")

CASE_PREFIX = "oat8_ARM97"
TEMPLATE_EXE = Path(
    os.environ.get("TEMPLATE_EXE", "/path/to/baseline/build/e3sm.exe")
)

PERTURBATIONS = [-1.0, -0.75, -0.50, -0.25, 0.25, 0.50, 0.75, 1.0]

PARAMS = [
    "ice_sed_ai",
    "cldfrc_dp1",
    "clubb_ice_deep",
    "clubb_ice_sh",
    "clubb_liq_deep",
    "clubb_liq_sh",
    "clubb_C2rt",
    "zmconv_c0_lnd",
    "zmconv_c0_ocn",
    "zmconv_dmpdz",
    "zmconv_ke",
    "effgw_oro",
    "seasalt_emis_scale",
    "dust_emis_fact",
    "clubb_gamma_coef",
    "clubb_C8",
    "cldfrc2m_rhmaxi",
    "clubb_c_K10",
    "effgw_beres",
    "do_tms",
    "so4_sz_thresh_icenuc",
    "n_so4_monolayers_pcage",
    "micro_mg_accre_enhan_fac",
    "zmconv_tiedke_add",
    "zmconv_cape_cin",
    "zmconv_mx_bot_lyr_adj",
    "taubgnd",
    "clubb_C1",
    "raytau0",
    "prc_coef1",
    "prc_exp",
    "prc_exp1",
    "se_ftype",
    "clubb_C14",
]


def replace_line(text, pattern, replacement):
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"expected one replacement for pattern: {pattern}")
    return new_text


def format_fortran(value: float, baseline_text: str) -> str:
    if baseline_text in {".true.", ".false."}:
        return baseline_text
    if re.fullmatch(r"[-+]?\d+", str(baseline_text)):
        return str(int(round(value)))

    use_d = "D" in str(baseline_text).upper()
    if value == 0:
        return "0D0" if use_d else "0"

    abs_value = abs(value)
    if abs_value < 1e-3 or abs_value >= 1e4:
        text = f"{value:.8e}"
    else:
        text = f"{value:.10g}"

    if use_d:
        text = text.replace("e", "D").replace("E", "D")
        if "D" not in text:
            text = f"{text}D0"
    return text


def replace_build_with_reuse(text):
    block = f"""# Reuse a pre-built executable from the baseline case; skip rebuilding the model.
  set template_exe = {TEMPLATE_EXE}
  if (! -e $template_exe) then
    echo "ERROR: template executable not found: $template_exe"
    exit 1
  endif
  mkdir -p $case_build_dir
  ln -sf $template_exe $case_build_dir/e3sm.exe
  ./xmlchange BUILD_COMPLETE=TRUE"""
    return replace_line(text, r"^# Build the case\s*\n\s*\./case\.build", block)


def render_script(template, row):
    text = template
    case = row["case"]
    text = replace_line(text, r"^\s*setenv casename .*$", f"  setenv casename {case}")
    text = replace_line(
        text,
        r"^\s*set micro_nccons_val = .*$",
        f"  set micro_nccons_val = {row['micro_nccons_val']} # cons_droplet value for liquid",
    )
    text = replace_line(
        text,
        r"^\s*set micro_nicons_val = .*$",
        f"  set micro_nicons_val = {row['micro_nicons_val']} # cons_droplet value for ice",
    )
    for param in PARAMS:
        text = replace_line(
            text,
            rf"^(\s*){re.escape(param)}\s*=.*$",
            rf"\g<1>{param} = {row[param]}",
        )
    return replace_build_with_reuse(text)


def main():
    if not TEMPLATE_EXE.exists():
        raise FileNotFoundError(f"template executable not found: {TEMPLATE_EXE}")

    OUT_DESIGN_DIR.mkdir(exist_ok=True)
    OUT_SCRIPT_DIR.mkdir(exist_ok=True)

    baseline = pd.read_csv(BASELINE).iloc[0]
    selected = pd.read_csv(SELECTED)["parameter"].tolist()
    if len(selected) != 8:
        raise RuntimeError(f"expected 8 selected parameters, got {len(selected)}")

    rows = []
    ranges = []
    case_index = 0
    for param_rank, param in enumerate(selected, start=1):
        base_numeric = float(baseline[f"{param}_numeric"])
        baseline_text = str(baseline[param])
        values = []
        for level_index, perturbation in enumerate(PERTURBATIONS, start=1):
            row = baseline.copy()
            case = f"{CASE_PREFIX}_{case_index:03d}_{param}"
            value = base_numeric * (1.0 + perturbation)
            row["case"] = case
            row[param] = format_fortran(value, baseline_text)
            row[f"{param}_numeric"] = value
            row["varied_parameter"] = param
            row["selected_parameter_rank"] = param_rank
            row["level_index"] = level_index
            row["relative_perturbation"] = perturbation
            row["relative_perturbation_percent"] = perturbation * 100.0
            row["baseline_numeric"] = base_numeric
            row["varied_value_numeric"] = value
            row["varied_value_fortran"] = row[param]
            rows.append(row)
            values.append(value)
            case_index += 1

        ranges.append(
            {
                "parameter": param,
                "baseline_numeric": base_numeric,
                "min_value_numeric": min(values),
                "max_value_numeric": max(values),
                "baseline_fortran": baseline_text,
                "min_value_fortran": format_fortran(min(values), baseline_text),
                "max_value_fortran": format_fortran(max(values), baseline_text),
                "n_levels": len(PERTURBATIONS),
                "relative_perturbations": ";".join(str(x) for x in PERTURBATIONS),
                "design": "one-at-a-time; +/-100%; baseline excluded",
            }
        )

    design = pd.DataFrame(rows)
    design_path = OUT_DESIGN_DIR / "oat8_sensitive_64_design.csv"
    ranges_path = OUT_DESIGN_DIR / "oat8_sensitive_parameter_ranges.csv"
    design.to_csv(design_path, index=False)
    pd.DataFrame(ranges).to_csv(ranges_path, index=False)

    template = TEMPLATE.read_text()
    manifest_rows = []
    for _, row in design.iterrows():
        script_text = render_script(template, row)
        script_path = OUT_SCRIPT_DIR / f"{row['case']}.csh"
        script_path.write_text(script_text)
        script_path.chmod(0o755)
        manifest_rows.append(
            {
                "case": row["case"],
                "script": str(script_path),
                "varied_parameter": row["varied_parameter"],
                "relative_perturbation": row["relative_perturbation"],
                "relative_perturbation_percent": row[
                    "relative_perturbation_percent"
                ],
                "varied_value_numeric": row["varied_value_numeric"],
                "varied_value_fortran": row["varied_value_fortran"],
                "template_exe": str(TEMPLATE_EXE),
                "reuse_build": True,
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = OUT_SCRIPT_DIR / "oat8_sensitive_reuse_build_script_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    print(f"design rows: {len(design)}")
    print(design_path)
    print(ranges_path)
    print(f"scripts: {len(manifest)}")
    print(OUT_SCRIPT_DIR)


if __name__ == "__main__":
    main()
