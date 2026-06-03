from pathlib import Path
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
OUT = Path("analysis_outputs")
DESIGN_CSV = Path("stage1_design/e3sm_scm_stage1_experiment_design.csv")


def open_case(case):
    path = ROOT / case / "run" / "case_scripts.eam.h0.1997-06-19-84585.nc"
    return xr.open_dataset(path)


def get_1d(ds, name):
    return ds[name].squeeze(drop=True)


def time_weights_days(ds):
    if "time_bnds" in ds:
        bnds = ds["time_bnds"].values
        dt = bnds[:, 1] - bnds[:, 0]
        if np.issubdtype(dt.dtype, np.timedelta64):
            return dt / np.timedelta64(1, "D")
        return dt
    t = ds["time"].values
    if np.issubdtype(t.dtype, np.datetime64):
        diff_days = np.diff(t) / np.timedelta64(1, "D")
    else:
        diff_days = np.diff(t)
    dt = np.empty(t.shape, dtype=float)
    dt[1:] = diff_days
    dt[0] = 0.0
    return dt


def weighted_mean(da, w):
    arr = np.asarray(da.values, dtype=float)
    if arr.ndim == 1:
        return float(np.nansum(arr * w) / np.nansum(w))
    raise ValueError(f"expected 1-D array, got shape {arr.shape}")


def summarize_case(case):
    with open_case(case) as ds:
        w_days = time_weights_days(ds)
        seconds = w_days * 86400.0

        precc = get_1d(ds, "PRECC")
        precl = get_1d(ds, "PRECL")
        prect = precc + precl

        summary = {
            "case": case,
            "n_time": int(ds.sizes["time"]),
            "sim_days": float(np.nansum(w_days)),
            "prect_mean_mm_day": weighted_mean(prect * 86400.0 * 1000.0, w_days),
            "precc_mean_mm_day": weighted_mean(precc * 86400.0 * 1000.0, w_days),
            "precl_mean_mm_day": weighted_mean(precl * 86400.0 * 1000.0, w_days),
            "prect_accum_mm": float(np.nansum(prect.values * seconds * 1000.0)),
            "prect_max_mm_day": float(np.nanmax(prect.values * 86400.0 * 1000.0)),
            "cldtot_mean": weighted_mean(get_1d(ds, "CLDTOT"), w_days),
            "tgcldlwp_mean": weighted_mean(get_1d(ds, "TGCLDLWP"), w_days),
            "tgcldiwp_mean": weighted_mean(get_1d(ds, "TGCLDIWP"), w_days),
            "tgcldcwp_mean": weighted_mean(get_1d(ds, "TGCLDCWP"), w_days),
            "fsnt_mean_wm2": weighted_mean(get_1d(ds, "FSNT"), w_days),
            "flnt_mean_wm2": weighted_mean(get_1d(ds, "FLNT"), w_days),
            "toa_net_mean_wm2": weighted_mean(get_1d(ds, "FSNT") - get_1d(ds, "FLNT"), w_days),
            "lhflx_mean_wm2": weighted_mean(get_1d(ds, "LHFLX"), w_days),
            "shflx_mean_wm2": weighted_mean(get_1d(ds, "SHFLX"), w_days),
            "tmq_mean_kg_m2": weighted_mean(get_1d(ds, "TMQ"), w_days),
        }
        return summary


def make_timeseries_plot(design):
    variables = [
        ("PRECT", "Total precipitation", "mm/day", lambda ds: (get_1d(ds, "PRECC") + get_1d(ds, "PRECL")) * 86400.0 * 1000.0),
        ("CLDTOT", "Total cloud fraction", "1", lambda ds: get_1d(ds, "CLDTOT")),
        ("TGCLDLWP", "Liquid water path", "kg/m2", lambda ds: get_1d(ds, "TGCLDLWP")),
        ("TGCLDIWP", "Ice water path", "kg/m2", lambda ds: get_1d(ds, "TGCLDIWP")),
        ("TOA_NET", "TOA net radiation", "W/m2", lambda ds: get_1d(ds, "FSNT") - get_1d(ds, "FLNT")),
    ]

    case_order = design["case"].tolist()
    baseline = "scm_ARM97_baseline"

    for varname, title, units, getter in variables:
        fig, ax = plt.subplots(figsize=(11, 5))
        for case in case_order:
            with open_case(case) as ds:
                days = get_1d(ds, "time").values
                y = getter(ds).values
                if case == baseline:
                    ax.plot(days, y, color="black", linewidth=2.2, label=case)
                else:
                    ax.plot(days, y, linewidth=1.0, alpha=0.75, label=case)
        ax.set_title(title)
        ax.set_xlabel("Days since 1997-06-19 23:29:45")
        ax.set_ylabel(units)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(OUT / f"stage1_timeseries_{varname}.png", dpi=160)
        plt.close(fig)


def make_delta_bar_plot(summary):
    baseline = summary.loc[summary["case"] == "scm_ARM97_baseline"].iloc[0]
    metrics = [
        "prect_accum_mm",
        "prect_mean_mm_day",
        "cldtot_mean",
        "tgcldlwp_mean",
        "tgcldiwp_mean",
        "toa_net_mean_wm2",
    ]
    delta = summary.copy()
    for metric in metrics:
        delta[f"{metric}_delta_vs_baseline"] = delta[metric] - baseline[metric]
    delta.to_csv(OUT / "stage1_summary_with_deltas.csv", index=False)

    for metric in metrics:
        dcol = f"{metric}_delta_vs_baseline"
        plot_df = delta[delta["case"] != "scm_ARM97_baseline"].copy()
        fig, ax = plt.subplots(figsize=(10, 4.8))
        ax.barh(plot_df["case"], plot_df[dcol])
        ax.axvline(0, color="black", linewidth=1)
        ax.set_title(f"{metric}: difference from baseline")
        ax.set_xlabel(dcol)
        fig.tight_layout()
        fig.savefig(OUT / f"stage1_delta_{metric}.png", dpi=160)
        plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    design = pd.read_csv(DESIGN_CSV)
    summary = pd.DataFrame([summarize_case(case) for case in design["case"]])
    summary = design.merge(summary, on="case", how="left")
    summary.to_csv(OUT / "stage1_summary.csv", index=False)
    make_timeseries_plot(design)
    make_delta_bar_plot(summary)
    print(summary[[
        "case",
        "prect_accum_mm",
        "prect_mean_mm_day",
        "cldtot_mean",
        "tgcldlwp_mean",
        "tgcldiwp_mean",
        "toa_net_mean_wm2",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
