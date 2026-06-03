from pathlib import Path
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


ROOT = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
OUT = Path("qmc_analysis")
DESIGN = Path("qmc_design/e3sm_scm_qmc_64_design.csv")
BASELINE = Path("qmc_design/e3sm_scm_qmc_baseline.csv")
STATUS = Path("qmc_design/e3sm_scm_qmc_run_status.csv")

RESPONSES = [
    "prect_accum_mm",
    "prect_mean_mm_day",
    "precc_mean_mm_day",
    "precl_mean_mm_day",
    "prect_max_mm_day",
    "cldtot_mean",
    "tgcldlwp_mean",
    "tgcldiwp_mean",
    "tgcldcwp_mean",
    "toa_net_mean_wm2",
    "fsnt_mean_wm2",
    "flnt_mean_wm2",
    "lhflx_mean_wm2",
    "shflx_mean_wm2",
    "tmq_mean_kg_m2",
]


def open_case(case):
    path = ROOT / case / "run" / "case_scripts.eam.h0.1997-06-19-84585.nc"
    return xr.open_dataset(path)


def get_1d(ds, name):
    return ds[name].squeeze(drop=True)


def time_weights_days(ds):
    bnds = ds["time_bnds"].values
    dt = bnds[:, 1] - bnds[:, 0]
    if np.issubdtype(dt.dtype, np.timedelta64):
        return dt / np.timedelta64(1, "D")
    return dt.astype(float)


def weighted_mean(da, weights_days):
    arr = np.asarray(da.values, dtype=float)
    return float(np.nansum(arr * weights_days) / np.nansum(weights_days))


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
            "prect_accum_mm": float(np.nansum(prect.values * seconds * 1000.0)),
            "prect_mean_mm_day": weighted_mean(prect * 86400.0 * 1000.0, w_days),
            "precc_mean_mm_day": weighted_mean(precc * 86400.0 * 1000.0, w_days),
            "precl_mean_mm_day": weighted_mean(precl * 86400.0 * 1000.0, w_days),
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


def parameter_columns(df):
    return [
        c[:-8]
        for c in df.columns
        if c.endswith("_numeric") and c[:-8] in df.columns
    ]


def add_normalized_parameters(df, baseline, params):
    out = df.copy()
    for p in params:
        b = float(baseline[f"{p}_numeric"])
        denom = 0.2 * abs(b)
        out[f"{p}_norm"] = (out[f"{p}_numeric"] - b) / denom
    return out


def correlations(df, params, responses):
    rows = []
    for response in responses:
        for p in params:
            x = df[f"{p}_norm"]
            y = df[f"delta_{response}"]
            rows.append(
                {
                    "response": response,
                    "parameter": p,
                    "pearson": x.corr(y, method="pearson"),
                    "spearman": x.corr(y, method="spearman"),
                }
            )
    corr = pd.DataFrame(rows)
    corr["abs_pearson"] = corr["pearson"].abs()
    corr["abs_spearman"] = corr["spearman"].abs()
    return corr.sort_values(["response", "abs_spearman"], ascending=[True, False])


def standardized_regression(df, params, responses):
    rows = []
    x = df[[f"{p}_norm" for p in params]].to_numpy()
    x = StandardScaler().fit_transform(x)
    for response in responses:
        y = df[f"delta_{response}"].to_numpy()
        y_std = StandardScaler().fit_transform(y.reshape(-1, 1)).ravel()
        model = LinearRegression().fit(x, y_std)
        pred = model.predict(x)
        ss_res = float(np.sum((y_std - pred) ** 2))
        ss_tot = float(np.sum((y_std - y_std.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot else np.nan
        for p, coef in zip(params, model.coef_):
            rows.append(
                {
                    "response": response,
                    "parameter": p,
                    "std_coef": coef,
                    "abs_std_coef": abs(coef),
                    "model_r2": r2,
                }
            )
    return pd.DataFrame(rows).sort_values(["response", "abs_std_coef"], ascending=[True, False])


def plot_response_ranking(df, response):
    plot_df = df.sort_values(f"delta_{response}")
    fig, ax = plt.subplots(figsize=(9, 10))
    ax.barh(plot_df["case"], plot_df[f"delta_{response}"])
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"Delta {response} vs QMC baseline")
    ax.set_xlabel(f"delta_{response}")
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    fig.savefig(OUT / f"rank_delta_{response}.png", dpi=160)
    plt.close(fig)


def plot_correlation_heatmap(corr, responses):
    top = corr[corr["response"].isin(responses)]
    pivot = top.pivot(index="parameter", columns="response", values="spearman").fillna(0.0)
    order = pivot.abs().max(axis=1).sort_values(ascending=False).index[:20]
    pivot = pivot.loc[order]
    fig, ax = plt.subplots(figsize=(9, 9))
    im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    fig.colorbar(im, ax=ax, label="Spearman correlation")
    ax.set_title("Top parameter-response correlations")
    fig.tight_layout()
    fig.savefig(OUT / "top20_spearman_correlation_heatmap.png", dpi=160)
    plt.close(fig)


def plot_top_scatter(df, corr, response, n=6):
    top_params = corr[corr["response"].eq(response)].head(n)["parameter"].tolist()
    for p in top_params:
        fig, ax = plt.subplots(figsize=(5.5, 4.2))
        ax.scatter(df[f"{p}_norm"], df[f"delta_{response}"], s=32)
        ax.axhline(0, color="black", linewidth=1, alpha=0.5)
        ax.axvline(0, color="black", linewidth=1, alpha=0.5)
        ax.set_xlabel(f"{p} normalized perturbation")
        ax.set_ylabel(f"delta_{response}")
        ax.set_title(f"{p} vs delta {response}")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / f"scatter_{response}_{p}.png", dpi=160)
        plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    design = pd.read_csv(DESIGN)
    baseline_design = pd.read_csv(BASELINE)
    all_design = pd.concat([baseline_design, design], ignore_index=True, sort=False)
    status = pd.read_csv(STATUS)
    successful = status[status["status"].eq("success")]["case"].tolist()
    all_design = all_design[all_design["case"].isin(successful)].copy()

    summaries = pd.DataFrame([summarize_case(case) for case in all_design["case"]])
    full = all_design.merge(summaries, on="case", how="inner")
    full.to_csv(OUT / "qmc_summary.csv", index=False)

    baseline = full[full["case"].eq("qmc_ARM97_baseline")].iloc[0]
    for r in RESPONSES:
        full[f"delta_{r}"] = full[r] - baseline[r]

    params = parameter_columns(full)
    qmc_only = full[~full["case"].eq("qmc_ARM97_baseline")].copy()
    qmc_only = add_normalized_parameters(qmc_only, baseline, params)
    qmc_only.to_csv(OUT / "qmc_delta_vs_baseline.csv", index=False)

    corr = correlations(qmc_only, params, RESPONSES)
    corr.to_csv(OUT / "qmc_parameter_correlations.csv", index=False)

    reg = standardized_regression(qmc_only, params, RESPONSES)
    reg.to_csv(OUT / "qmc_standardized_regression.csv", index=False)

    key_responses = [
        "prect_accum_mm",
        "cldtot_mean",
        "tgcldlwp_mean",
        "tgcldiwp_mean",
        "toa_net_mean_wm2",
    ]
    for r in key_responses:
        plot_response_ranking(qmc_only, r)
        plot_top_scatter(qmc_only, corr, r, n=6)
    plot_correlation_heatmap(corr, key_responses)

    top = corr[corr["response"].isin(key_responses)].groupby("response").head(8)
    top.to_csv(OUT / "qmc_top_correlations_key_responses.csv", index=False)

    print("cases analyzed:", len(qmc_only), "+ baseline")
    print("parameters:", len(params))
    print(top[["response", "parameter", "spearman", "pearson"]].to_string(index=False))


if __name__ == "__main__":
    main()
