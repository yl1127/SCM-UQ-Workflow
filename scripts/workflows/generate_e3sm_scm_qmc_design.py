from pathlib import Path
import os

import pandas as pd
import qmcpy as qp


OUT_DIR = Path("qmc_design")
N_SAMPLES = 64
SEED = 20260428


CONTINUOUS_PARAMS = [
    ("micro_nccons_val", 100.0e6, "D6"),
    ("micro_nicons_val", 0.0001e6, "D6"),
    ("ice_sed_ai", 500.0, "float"),
    ("cldfrc_dp1", 0.045, "D0"),
    ("clubb_ice_deep", 16.0e-6, "e"),
    ("clubb_ice_sh", 50.0e-6, "e"),
    ("clubb_liq_deep", 8.0e-6, "e"),
    ("clubb_liq_sh", 10.0e-6, "e"),
    ("clubb_C2rt", 1.75, "D0"),
    ("zmconv_c0_lnd", 0.007, "float"),
    ("zmconv_c0_ocn", 0.007, "float"),
    ("zmconv_dmpdz", -0.7e-3, "e"),
    ("zmconv_ke", 1.5e-6, "E"),
    ("effgw_oro", 0.25, "float"),
    ("seasalt_emis_scale", 0.85, "float"),
    ("dust_emis_fact", 2.05, "D0"),
    ("clubb_gamma_coef", 0.32, "float"),
    ("clubb_C8", 4.3, "float"),
    ("cldfrc2m_rhmaxi", 1.05, "D0"),
    ("clubb_c_K10", 0.3, "float"),
    ("effgw_beres", 0.4, "float"),
    ("so4_sz_thresh_icenuc", 0.075e-6, "e"),
    ("n_so4_monolayers_pcage", 8.0, "D0"),
    ("micro_mg_accre_enhan_fac", 1.5, "D0"),
    ("zmconv_tiedke_add", 0.8, "D0"),
    ("taubgnd", 2.5e-3, "D"),
    ("clubb_C1", 1.335, "float"),
    ("raytau0", 5.0, "D0"),
    ("prc_coef1", 30500.0, "D0"),
    ("prc_exp", 3.19, "D0"),
    ("prc_exp1", -1.2, "D0"),
    ("clubb_C14", 1.3, "D0"),
]


FIXED_PARAMS = [
    ("do_tms", ".false.", "logical option; held fixed"),
    ("zmconv_cape_cin", "1", "integer/scheme option; held fixed"),
    ("zmconv_mx_bot_lyr_adj", "2", "integer/scheme option; held fixed"),
    ("se_ftype", "2", "integer/scheme option; held fixed"),
]


def bounds_around_baseline(value, pct=0.20):
    a = value * (1.0 - pct)
    b = value * (1.0 + pct)
    return min(a, b), max(a, b)


def format_value(value, style):
    if style == "D6":
        mantissa = f"{value / 1.0e6:.12f}".rstrip("0").rstrip(".")
        return f"{mantissa}D6"
    if style == "D0":
        return f"{value:.8g}D0"
    if style == "D":
        return f"{value:.8e}".replace("e", "D")
    if style == "E":
        return f"{value:.8E}"
    if style == "e":
        return f"{value:.8e}"
    return f"{value:.8g}"


def main():
    OUT_DIR.mkdir(exist_ok=True)

    ranges = []
    for name, baseline, style in CONTINUOUS_PARAMS:
        low, high = bounds_around_baseline(baseline)
        ranges.append(
            {
                "parameter": name,
                "baseline_numeric": baseline,
                "lower_numeric": low,
                "upper_numeric": high,
                "baseline_fortran": format_value(baseline, style),
                "lower_fortran": format_value(low, style),
                "upper_fortran": format_value(high, style),
                "qmc_sampled": True,
                "note": "continuous; +/-20%",
            }
        )
    for name, value, note in FIXED_PARAMS:
        ranges.append(
            {
                "parameter": name,
                "baseline_numeric": value,
                "lower_numeric": value,
                "upper_numeric": value,
                "baseline_fortran": value,
                "lower_fortran": value,
                "upper_fortran": value,
                "qmc_sampled": False,
                "note": note,
            }
        )

    ranges_df = pd.DataFrame(ranges)
    ranges_df.to_csv(OUT_DIR / "e3sm_scm_qmc_parameter_ranges.csv", index=False)

    sampler = qp.DigitalNetB2(dimension=len(CONTINUOUS_PARAMS), seed=SEED)
    u = sampler(N_SAMPLES)

    rows = []
    for i in range(N_SAMPLES):
        row = {
            "case": f"qmc_ARM97_{i:03d}",
            "qmc_index": i,
            "qmc_sampler": "QMCPy DigitalNetB2",
            "qmc_seed": SEED,
        }
        for j, (name, baseline, style) in enumerate(CONTINUOUS_PARAMS):
            low, high = bounds_around_baseline(baseline)
            value = low + u[i, j] * (high - low)
            row[name] = format_value(value, style)
            row[f"{name}_numeric"] = value
        for name, value, _note in FIXED_PARAMS:
            row[name] = value
        rows.append(row)

    design_df = pd.DataFrame(rows)
    design_df.to_csv(OUT_DIR / "e3sm_scm_qmc_64_design.csv", index=False)

    baseline = {"case": "qmc_ARM97_baseline"}
    for name, value, style in CONTINUOUS_PARAMS:
        baseline[name] = format_value(value, style)
        baseline[f"{name}_numeric"] = value
    for name, value, _note in FIXED_PARAMS:
        baseline[name] = value
    pd.DataFrame([baseline]).to_csv(OUT_DIR / "e3sm_scm_qmc_baseline.csv", index=False)

    print(f"sampled continuous dimensions: {len(CONTINUOUS_PARAMS)}")
    print(f"fixed option dimensions: {len(FIXED_PARAMS)}")
    print(f"samples: {N_SAMPLES}")
    print(OUT_DIR / "e3sm_scm_qmc_64_design.csv")


if __name__ == "__main__":
    main()
