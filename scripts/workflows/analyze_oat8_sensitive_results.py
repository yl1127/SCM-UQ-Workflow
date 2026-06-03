from pathlib import Path
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
OUT = Path("oat8_analysis")
STATUS = Path("oat8_sensitive_design/oat8_sensitive_reuse_build_run_status_checked.csv")
BASELINE_CASE = "qmc_ARM97_baseline"

KEY_RESPONSES = [
    "TREFHT_final_K",
    "TREFHT_mean_K",
    "T_lowest_lev_mean_K",
    "CLDTOT_mean",
    "TGCLDLWP_mean_kgm2",
    "TGCLDIWP_mean_kgm2",
    "PRECT_accum_mm",
    "PRECT_mean_mm_day",
    "TOA_net_mean_Wm2",
]


def history_file(case):
    files = sorted((ROOT / case / "run").glob("*.eam.h0.*.nc"))
    if not files:
        raise FileNotFoundError(f"No EAM history file found for {case}")
    return files[0]


def scalar_time_series(ds, name):
    if name not in ds:
        return None
    da = ds[name]
    if "ncol" in da.dims:
        da = da.isel(ncol=0)
    return da.squeeze(drop=True)


def finite_float(value):
    value = float(value)
    return value if np.isfinite(value) else np.nan


def time_weights_days(ds):
    if "time_bnds" in ds:
        bnds = ds["time_bnds"].values
        dt = bnds[:, 1] - bnds[:, 0]
        if np.issubdtype(dt.dtype, np.timedelta64):
            return dt / np.timedelta64(1, "D")
        return dt.astype(float)
    if ds.sizes.get("time", 0) > 1:
        dt = ds["time"].diff("time") / np.timedelta64(1, "D")
        median = float(dt.median().values)
    else:
        median = 1.0
    return np.full(ds.sizes["time"], median)


def weighted_mean(da, weights_days):
    arr = np.asarray(da.values, dtype=float)
    return float(np.nansum(arr * weights_days) / np.nansum(weights_days))


def add_basic_stats(out, ds, name):
    da = scalar_time_series(ds, name)
    if da is None:
        return
    units = da.attrs.get("units", "")
    suffix = {"K": "_K", "W/m2": "_Wm2", "kg/m2": "_kgm2", "1": ""}.get(units, "")
    weights = time_weights_days(ds)
    out[f"{name}_final{suffix}"] = finite_float(da.isel(time=-1).values)
    out[f"{name}_mean{suffix}"] = weighted_mean(da, weights)
    out[f"{name}_min{suffix}"] = finite_float(da.min("time").values)
    out[f"{name}_max{suffix}"] = finite_float(da.max("time").values)


def case_metrics(case):
    with xr.open_dataset(history_file(case)) as ds:
        out = {"case": case, "final_time": str(ds["time"].isel(time=-1).values)}
        for name in [
            "TREFHT",
            "TS",
            "CLDTOT",
            "TGCLDLWP",
            "TGCLDIWP",
            "TGCLDCWP",
            "LHFLX",
            "SHFLX",
            "FSNT",
            "FLNT",
            "TMQ",
        ]:
            add_basic_stats(out, ds, name)

        weights = time_weights_days(ds)
        seconds = weights * 86400.0
        precc = scalar_time_series(ds, "PRECC")
        precl = scalar_time_series(ds, "PRECL")
        if precc is not None and precl is not None:
            prect = precc + precl
            prect_mm_day = prect * 1000.0 * 86400.0
            out["PRECT_accum_mm"] = finite_float(np.nansum(prect.values * seconds * 1000.0))
            out["PRECT_mean_mm_day"] = weighted_mean(prect_mm_day, weights)
            out["PRECT_max_mm_day"] = finite_float(prect_mm_day.max("time").values)
            out["PRECC_mean_mm_day"] = weighted_mean(precc * 1000.0 * 86400.0, weights)
            out["PRECL_mean_mm_day"] = weighted_mean(precl * 1000.0 * 86400.0, weights)

        fsnt = scalar_time_series(ds, "FSNT")
        flnt = scalar_time_series(ds, "FLNT")
        if fsnt is not None and flnt is not None:
            toa = fsnt - flnt
            out["TOA_net_final_Wm2"] = finite_float(toa.isel(time=-1).values)
            out["TOA_net_mean_Wm2"] = weighted_mean(toa, weights)
            out["TOA_net_min_Wm2"] = finite_float(toa.min("time").values)
            out["TOA_net_max_Wm2"] = finite_float(toa.max("time").values)

        if "T" in ds:
            t = ds["T"]
            if "ncol" in t.dims:
                t = t.isel(ncol=0)
            lowest = t.isel(lev=-1).squeeze(drop=True)
            out["T_lowest_lev_final_K"] = finite_float(lowest.isel(time=-1).values)
            out["T_lowest_lev_mean_K"] = weighted_mean(lowest, weights)
            out["T_column_mean_K"] = finite_float(t.mean().values)

        if "Q" in ds:
            q = ds["Q"]
            if "ncol" in q.dims:
                q = q.isel(ncol=0)
            lowest = q.isel(lev=-1).squeeze(drop=True)
            out["Q_lowest_lev_final_kgkg"] = finite_float(lowest.isel(time=-1).values)
            out["Q_lowest_lev_mean_kgkg"] = weighted_mean(lowest, weights)

        return out


def response_columns(df):
    excluded = {
        "case",
        "script",
        "varied_parameter",
        "relative_perturbation_percent",
        "status",
        "start_epoch",
        "end_epoch",
        "wall_seconds",
        "level_index",
        "relative_perturbation",
        "baseline_numeric",
        "varied_value_numeric",
        "case_status_wall_seconds",
        "case_build_seconds",
        "case_run_seconds",
        "history_file_exists",
    }
    return [
        c
        for c in df.columns
        if c not in excluded
        and not c.startswith("delta_")
        and pd.api.types.is_numeric_dtype(df[c])
    ]


def fit_line(x, y):
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return np.nan, np.nan
    slope, intercept = np.polyfit(x[mask], y[mask], deg=1)
    pred = slope * x[mask] + intercept
    ss_res = np.sum((y[mask] - pred) ** 2)
    ss_tot = np.sum((y[mask] - np.mean(y[mask])) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot else np.nan
    return float(slope), float(r2)


def oat_sensitivity(df, responses):
    rows = []
    for param, group in df.groupby("varied_parameter"):
        for response in responses:
            delta_col = f"delta_{response}"
            if delta_col not in group:
                continue
            x = np.r_[0.0, group["relative_perturbation"].to_numpy(dtype=float)]
            y = np.r_[0.0, group[delta_col].to_numpy(dtype=float)]
            slope, r2 = fit_line(x, y)
            spearman = pd.Series(x).corr(pd.Series(y), method="spearman")
            max_idx = np.nanargmax(np.abs(y)) if np.isfinite(y).any() else 0
            rows.append(
                {
                    "parameter": param,
                    "response": response,
                    "n_cases": len(group),
                    "slope_delta_per_100pct": slope,
                    "linear_r2_with_baseline_anchor": r2,
                    "spearman_with_baseline_anchor": spearman,
                    "max_abs_delta": float(np.nanmax(np.abs(y))),
                    "delta_at_max_abs": float(y[max_idx]),
                    "relative_perturbation_at_max_abs": float(x[max_idx]),
                    "min_delta": float(np.nanmin(y)),
                    "max_delta": float(np.nanmax(y)),
                }
            )
    out = pd.DataFrame(rows)
    out["abs_slope_delta_per_100pct"] = out["slope_delta_per_100pct"].abs()
    out["abs_spearman"] = out["spearman_with_baseline_anchor"].abs()
    return out.sort_values(["response", "max_abs_delta"], ascending=[True, False])


def plot_heatmap(sens, responses, value_col, filename, title, cbar_label, symmetric=True):
    pivot = sens[sens["response"].isin(responses)].pivot(
        index="parameter", columns="response", values=value_col
    )
    order = pivot.abs().max(axis=1).sort_values(ascending=False).index
    pivot = pivot.loc[order, responses]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    values = pivot.to_numpy()
    if symmetric:
        vmax = np.nanmax(np.abs(values))
        vmin = -vmax
        cmap = "RdBu_r"
    else:
        vmin = 0.0
        vmax = np.nanmax(values)
        cmap = "viridis"
    im = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    fig.colorbar(im, ax=ax, label=cbar_label)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(OUT / filename, dpi=180)
    plt.close(fig)


def plot_response_curves(df, responses):
    for response in responses:
        delta_col = f"delta_{response}"
        if delta_col not in df:
            continue
        params = df["varied_parameter"].drop_duplicates().tolist()
        fig, axes = plt.subplots(2, 4, figsize=(14, 7), sharex=True)
        for ax, param in zip(axes.ravel(), params):
            g = df[df["varied_parameter"].eq(param)].sort_values("relative_perturbation")
            x = np.r_[0.0, g["relative_perturbation"].to_numpy(dtype=float)]
            y = np.r_[0.0, g[delta_col].to_numpy(dtype=float)]
            order = np.argsort(x)
            ax.plot(x[order] * 100.0, y[order], marker="o", linewidth=1.6)
            ax.axhline(0, color="black", linewidth=0.8, alpha=0.5)
            ax.axvline(0, color="black", linewidth=0.8, alpha=0.5)
            ax.set_title(param, fontsize=10)
            ax.grid(True, alpha=0.25)
        for ax in axes[-1, :]:
            ax.set_xlabel("Perturbation (%)")
        for ax in axes[:, 0]:
            ax.set_ylabel(f"delta {response}")
        fig.suptitle(f"OAT response curves: {response}", y=1.01)
        fig.tight_layout()
        fig.savefig(OUT / f"oat8_response_curves_{response}.png", dpi=180, bbox_inches="tight")
        plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    status = pd.read_csv(STATUS)
    success = status[status["checked_status"].eq("success")].copy()

    baseline = case_metrics(BASELINE_CASE)
    cases = success["case"].tolist()
    responses = pd.DataFrame([baseline] + [case_metrics(case) for case in cases])
    responses.to_csv(OUT / "oat8_expanded_responses_by_case.csv", index=False)

    merged = success.merge(responses, on="case", how="inner")
    merged.to_csv(OUT / "oat8_design_with_expanded_responses.csv", index=False)

    baseline_row = pd.Series(baseline)
    resp_cols = response_columns(responses)
    for response in resp_cols:
        if response in baseline_row and pd.api.types.is_number(baseline_row[response]):
            merged[f"delta_{response}"] = merged[response] - float(baseline_row[response])

    merged.to_csv(OUT / "oat8_delta_vs_baseline.csv", index=False)

    available_key = [r for r in KEY_RESPONSES if f"delta_{r}" in merged.columns]
    sens = oat_sensitivity(merged, available_key)
    sens["normalized_max_abs_delta_within_response"] = sens.groupby("response")[
        "max_abs_delta"
    ].transform(lambda s: s / s.max() if s.max() else 0.0)
    sens["normalized_abs_slope_within_response"] = sens.groupby("response")[
        "abs_slope_delta_per_100pct"
    ].transform(lambda s: s / s.max() if s.max() else 0.0)
    sens.to_csv(OUT / "oat8_oat_sensitivity_summary.csv", index=False)

    top = sens.sort_values("max_abs_delta", ascending=False).groupby("response").head(5)
    top.to_csv(OUT / "oat8_top5_sensitivities_by_response.csv", index=False)

    rank = (
        sens.groupby("parameter")
        .agg(
            mean_normalized_max_abs_delta=("normalized_max_abs_delta_within_response", "mean"),
            max_normalized_max_abs_delta=("normalized_max_abs_delta_within_response", "max"),
            mean_normalized_abs_slope=("normalized_abs_slope_within_response", "mean"),
            raw_mean_max_abs_delta=("max_abs_delta", "mean"),
            raw_max_abs_delta=("max_abs_delta", "max"),
            mean_abs_slope=("abs_slope_delta_per_100pct", "mean"),
            n_responses=("response", "count"),
        )
        .reset_index()
        .sort_values("mean_normalized_max_abs_delta", ascending=False)
    )
    rank.to_csv(OUT / "oat8_parameter_overall_ranking.csv", index=False)

    plot_heatmap(
        sens,
        available_key,
        "slope_delta_per_100pct",
        "oat8_slope_heatmap_key_responses.png",
        "OAT slope per +100% parameter perturbation",
        "delta response per +100%",
        symmetric=True,
    )
    plot_heatmap(
        sens,
        available_key,
        "max_abs_delta",
        "oat8_max_abs_delta_heatmap_key_responses.png",
        "Maximum absolute response change from baseline",
        "max |delta response|",
        symmetric=False,
    )
    plot_response_curves(merged, available_key)

    report_lines = [
        "# OAT8 Sensitive-Parameter Result Analysis",
        "",
        f"Successful cases analyzed: {len(success)} / {len(status)}.",
        f"Baseline case: `{BASELINE_CASE}`.",
        "",
        "## Overall Parameter Ranking",
        "",
        rank.to_markdown(index=False, floatfmt=".4g"),
        "",
        "## Top Sensitivities By Response",
        "",
        top[[
            "response",
            "parameter",
            "slope_delta_per_100pct",
            "max_abs_delta",
            "relative_perturbation_at_max_abs",
            "linear_r2_with_baseline_anchor",
            "spearman_with_baseline_anchor",
        ]].to_markdown(index=False, floatfmt=".4g"),
        "",
        "## Output Files",
        "",
        "- `oat8_analysis/oat8_delta_vs_baseline.csv`",
        "- `oat8_analysis/oat8_oat_sensitivity_summary.csv`",
        "- `oat8_analysis/oat8_parameter_overall_ranking.csv`",
        "- `oat8_analysis/oat8_slope_heatmap_key_responses.png`",
        "- `oat8_analysis/oat8_max_abs_delta_heatmap_key_responses.png`",
        "- `oat8_analysis/oat8_response_curves_<response>.png`",
    ]
    (OUT / "oat8_analysis_report.md").write_text("\n".join(report_lines) + "\n")

    print(f"successful cases analyzed: {len(success)} / {len(status)}")
    print(f"responses analyzed: {len(available_key)}")
    print()
    print(rank.to_string(index=False))
    print()
    print(top[["response", "parameter", "slope_delta_per_100pct", "max_abs_delta"]].to_string(index=False))


if __name__ == "__main__":
    main()
