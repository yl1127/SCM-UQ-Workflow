from pathlib import Path
import os
import re

import pandas as pd


TEMPLATE = Path("e3sm_scm_stage1_run_scripts/scm_ARM97_baseline.csh")
DESIGN = Path("qmc_design/e3sm_scm_qmc_64_design.csv")
BASELINE = Path("qmc_design/e3sm_scm_qmc_baseline.csv")
OUT_DIR = Path("e3sm_scm_qmc_run_scripts")


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


def render_script(template, row):
    text = template
    case = row["case"]
    text = replace_line(
        text,
        r"^\s*setenv casename .*$",
        f"  setenv casename {case}",
    )
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
    return text


def main():
    OUT_DIR.mkdir(exist_ok=True)
    template = TEMPLATE.read_text()
    design = pd.concat(
        [pd.read_csv(BASELINE), pd.read_csv(DESIGN)],
        ignore_index=True,
        sort=False,
    )

    manifest_rows = []
    for _, row in design.iterrows():
        script_text = render_script(template, row)
        script_path = OUT_DIR / f"{row['case']}.csh"
        script_path.write_text(script_text)
        script_path.chmod(0o755)
        manifest_rows.append(
            {
                "case": row["case"],
                "script": str(script_path),
                "source": "baseline" if row["case"] == "qmc_ARM97_baseline" else "qmc_64",
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(OUT_DIR / "qmc_run_script_manifest.csv", index=False)
    print(f"generated scripts: {len(manifest)}")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
