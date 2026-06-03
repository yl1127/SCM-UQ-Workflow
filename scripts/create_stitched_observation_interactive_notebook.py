#!/usr/bin/env python3
"""Create an interactive notebook for ARM97 stitched-vs-observation diagnostics."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/ARM97_stitched_vs_observation_interactive.ipynb"


def md(source: str) -> dict:
    source = textwrap.dedent(source).strip()
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def code(source: str) -> dict:
    source = textwrap.dedent(source).strip()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


cells = [
    md(
        """
        # ARM97 stitched run vs observation

        Interactive demo notebook for comparing the stitched 26-day ARM97 SCM output with the ARM97 IOP observation file.

        The main figure uses a built-in Plotly variable selector. The observation series is interpolated onto the stitched model time axis before calculating `stitched - observation`, while the top panel also shows the native-resolution observation line for context.
        """
    ),
    code(
        r"""
        from __future__ import annotations

        from dataclasses import dataclass
        from datetime import timedelta
        import os
        from pathlib import Path

        ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
        os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local_cache/matplotlib-cache"))

        import numpy as np
        import pandas as pd
        from netCDF4 import Dataset, num2date
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        STITCHED = ROOT / "mac_arm97_segment_design/mac_ARM97_26day_stitched_from_segments.nc"
        OBSERVATION = Path(os.environ.get("ARM97_IOP_FILE", "/path/to/ARM97_iopfile_4scam.nc"))

        assert STITCHED.exists(), STITCHED
        assert OBSERVATION.exists(), OBSERVATION

        print("stitched:", STITCHED)
        print("observation:", OBSERVATION)
        """
    ),
    md(
        """
        ## Variable mapping

        These are the model-to-observation pairs used in the demo. Unit conversions are applied where needed, for example `prew` from cm to kg/m2 and `totcld` from percent to fraction.
        """
    ),
    code(
        r"""
        @dataclass(frozen=True)
        class VarSpec:
            model: str
            obs: str
            units: str
            scale_obs: float = 1.0
            obs_offset: float = 0.0
            description: str = ""

        VARS = [
            VarSpec("TREFHT", "Tsair", "K", description="2 m air temperature"),
            VarSpec("TS", "Tg", "K", description="surface/ground temperature"),
            VarSpec("TMQ", "prew", "kg/m2", scale_obs=10.0, description="precipitable water"),
            VarSpec("CLDTOT", "totcld", "1", scale_obs=0.01, description="total cloud fraction"),
            VarSpec("PS", "Ps", "Pa", description="surface pressure"),
            VarSpec("LHFLX", "lhflx", "W/m2", description="latent heat flux"),
            VarSpec("SHFLX", "shflx", "W/m2", description="sensible heat flux"),
            VarSpec("FSNS", "srfswdn-srfswup", "W/m2", description="surface net shortwave flux"),
            VarSpec("FLNS", "srflwup-srflwdn", "W/m2", description="surface net longwave flux"),
            VarSpec("FSDS", "srfswdn", "W/m2", description="surface downwelling shortwave flux"),
            VarSpec("FLDS", "srflwdn", "W/m2", description="surface downwelling longwave flux"),
        ]

        pd.DataFrame([vars(v) for v in VARS])
        """
    ),
    md(
        """
        ## Load and align data
        """
    ),
    code(
        r"""
        def as_series(var):
            data = np.ma.asarray(var[:], dtype=np.float64)
            if data.ndim == 1:
                return data
            axes = tuple(range(1, data.ndim))
            return np.ma.mean(data, axis=axes)

        def obs_series(ds, expression):
            if "-" in expression:
                left, right = expression.split("-", 1)
                return as_series(ds.variables[left]) - as_series(ds.variables[right])
            return as_series(ds.variables[expression])

        def filled(arr):
            return np.asarray(np.ma.asarray(arr, dtype=np.float64).filled(np.nan), dtype=np.float64)

        def interpolate_obs(obs_days, obs_values, target_days):
            finite = np.isfinite(obs_values)
            if finite.sum() < 2:
                return np.full_like(target_days, np.nan, dtype=np.float64)
            return np.interp(target_days, obs_days[finite], obs_values[finite], left=np.nan, right=np.nan)

        def stats(model_values, obs_values):
            finite = np.isfinite(model_values) & np.isfinite(obs_values)
            diff = model_values[finite] - obs_values[finite]
            if diff.size == 0:
                return dict(n=0, mean_obs=np.nan, mean_stitched=np.nan, bias=np.nan, mae=np.nan, rmse=np.nan, max_abs=np.nan)
            return dict(
                n=int(diff.size),
                mean_obs=float(np.mean(obs_values[finite])),
                mean_stitched=float(np.mean(model_values[finite])),
                bias=float(np.mean(diff)),
                mae=float(np.mean(np.abs(diff))),
                rmse=float(np.sqrt(np.mean(diff * diff))),
                max_abs=float(np.max(np.abs(diff))),
            )

        DATA = {}
        with Dataset(STITCHED) as stitched, Dataset(OBSERVATION) as obs:
            st = stitched.variables["time"]
            model_days = np.asarray(st[:], dtype=np.float64)
            model_dates = np.array(
                num2date(model_days, st.units, getattr(st, "calendar", "standard"), only_use_cftime_datetimes=False)
            )
            obs_days = (np.asarray(obs.variables["tsec"][:], dtype=np.float64) - float(obs.variables["tsec"][0])) / 86400.0
            origin = model_dates[0] - timedelta(days=float(model_days[0]))
            obs_dates = np.array([origin + timedelta(days=float(x)) for x in obs_days])

            for spec in VARS:
                if spec.model not in stitched.variables:
                    continue
                obs_names = spec.obs.split("-")
                if any(name not in obs.variables for name in obs_names):
                    continue

                model_values = filled(as_series(stitched.variables[spec.model]))
                obs_native = filled(obs_series(obs, spec.obs)) * spec.scale_obs + spec.obs_offset
                obs_at_model = interpolate_obs(obs_days, obs_native, model_days)
                diff = model_values - obs_at_model
                DATA[spec.model] = dict(
                    spec=spec,
                    model_dates=model_dates,
                    obs_dates=obs_dates,
                    model_values=model_values,
                    obs_native=obs_native,
                    obs_at_model=obs_at_model,
                    diff=diff,
                    stats=stats(model_values, obs_at_model),
                )

        summary = pd.DataFrame([
            {
                "variable": name,
                "observation": d["spec"].obs,
                "description": d["spec"].description,
                "units": d["spec"].units,
                **d["stats"],
            }
            for name, d in DATA.items()
        ]).sort_values("rmse", ascending=False)

        print(f"Loaded {len(DATA)} variables.")
        summary
        """
    ),
    md(
        """
        ## Interactive stitched-vs-observation figure

        Use the dropdown at the top-right of the figure to switch variables. Use Plotly's toolbar zoom/pan tools to focus on individual events during a live demo.
        """
    ),
    code(
        r"""
        def title_for(name, d):
            s = d["stats"]
            return (
                f"{name}: stitched vs observation"
                f"<br><sup>{d['spec'].description} | obs={d['spec'].obs} | "
                f"bias={s['bias']:.3g} {d['spec'].units}, "
                f"RMSE={s['rmse']:.3g}, MAE={s['mae']:.3g}, n={s['n']}</sup>"
            )

        names = list(DATA)
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.10,
            row_heights=[0.68, 0.32],
        )

        buttons = []
        for i, name in enumerate(names):
            d = DATA[name]
            visible = i == 0
            fig.add_trace(
                go.Scatter(
                    x=d["obs_dates"],
                    y=d["obs_native"],
                    mode="lines",
                    name="observation",
                    line=dict(color="rgba(80,80,80,0.75)", width=1.2),
                    visible=visible,
                    hovertemplate="%{x}<br>obs=%{y:.4g}<extra></extra>",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=d["model_dates"],
                    y=d["model_values"],
                    mode="lines",
                    name="stitched",
                    line=dict(color="#1261A6", width=2.4),
                    visible=visible,
                    hovertemplate="%{x}<br>stitched=%{y:.4g}<extra></extra>",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=d["model_dates"],
                    y=d["diff"],
                    mode="lines",
                    name="stitched - observation",
                    line=dict(color="#C2410C", width=1.7),
                    visible=visible,
                    hovertemplate="%{x}<br>diff=%{y:.4g}<extra></extra>",
                ),
                row=2,
                col=1,
            )

            mask = [False] * (len(names) * 3)
            mask[i * 3 : i * 3 + 3] = [True, True, True]
            buttons.append(
                dict(
                    label=f"{name}: {d['spec'].description}",
                    method="update",
                    args=[
                        {"visible": mask},
                        {
                            "title.text": title_for(name, d),
                            "yaxis.title.text": f"{name} ({d['spec'].units})",
                            "yaxis2.title.text": f"stitched - observation ({d['spec'].units})",
                        },
                    ],
                )
            )

        first = DATA[names[0]]
        fig.update_layout(
            title=dict(text=title_for(names[0], first), x=0.01, xanchor="left"),
            template="plotly_white",
            height=760,
            width=1120,
            hovermode="x unified",
            margin=dict(l=80, r=40, t=120, b=70),
            legend=dict(orientation="h", yanchor="bottom", y=1.005, xanchor="left", x=0),
            updatemenus=[
                dict(
                    type="dropdown",
                    x=1.0,
                    y=1.13,
                    xanchor="right",
                    yanchor="top",
                    buttons=buttons,
                    showactive=True,
                )
            ],
        )
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_xaxes(title="Time", row=2, col=1)
        fig.update_yaxes(title=f"{names[0]} ({first['spec'].units})", row=1, col=1)
        fig.update_yaxes(title=f"stitched - observation ({first['spec'].units})", zeroline=True, zerolinewidth=1, zerolinecolor="black", row=2, col=1)
        fig.show()
        """
    ),
    md(
        """
        ## Pressure-level profile comparison

        This second interactive plot compares profile variables at a selected observation pressure level. The stitched model profile is first converted from hybrid coordinates to pressure using `hyam * P0 + hybm * PS(time)`, then vertically interpolated to the selected pressure level.
        """
    ),
    code(
        r"""
        @dataclass(frozen=True)
        class ProfileSpec:
            model: str
            obs: str
            units: str
            description: str = ""

        PROFILE_VARS = [
            ProfileSpec("T", "T", "K", "temperature"),
            ProfileSpec("Q", "q", "kg/kg", "specific humidity"),
            ProfileSpec("U", "u", "m/s", "zonal wind"),
            ProfileSpec("V", "v", "m/s", "meridional wind"),
            ProfileSpec("OMEGA", "omega", "Pa/s", "pressure vertical velocity"),
            ProfileSpec("RELHUM", "rh", "%", "relative humidity"),
        ]

        def interp_model_matrix_to_pressure(values, pressure, target_pressure):
            values = np.asarray(values, dtype=np.float64)
            pressure = np.asarray(pressure, dtype=np.float64)
            idx = np.sum(pressure < target_pressure, axis=1)
            valid = (idx > 0) & (idx < pressure.shape[1])
            out = np.full(values.shape[0], np.nan, dtype=np.float64)
            if not valid.any():
                return out

            rows = np.arange(values.shape[0])[valid]
            upper = idx[valid]
            lower = upper - 1
            p0 = pressure[rows, lower]
            p1 = pressure[rows, upper]
            v0 = values[rows, lower]
            v1 = values[rows, upper]
            ok = np.isfinite(p0) & np.isfinite(p1) & np.isfinite(v0) & np.isfinite(v1) & (p1 != p0)
            interp = np.full(rows.shape[0], np.nan, dtype=np.float64)
            interp[ok] = v0[ok] + (target_pressure - p0[ok]) * (v1[ok] - v0[ok]) / (p1[ok] - p0[ok])
            out[rows] = interp
            return out

        def load_profile_data():
            profile = {}
            with Dataset(STITCHED) as stitched, Dataset(OBSERVATION) as obs:
                st = stitched.variables["time"]
                model_days = np.asarray(st[:], dtype=np.float64)
                model_dates = np.array(
                    num2date(model_days, st.units, getattr(st, "calendar", "standard"), only_use_cftime_datetimes=False)
                )
                obs_days = (np.asarray(obs.variables["tsec"][:], dtype=np.float64) - float(obs.variables["tsec"][0])) / 86400.0
                origin = model_dates[0] - timedelta(days=float(model_days[0]))
                obs_dates = np.array([origin + timedelta(days=float(x)) for x in obs_days])

                obs_levels_pa = np.asarray(obs.variables["lev"][:], dtype=np.float64)
                p0 = float(np.asarray(stitched.variables["P0"][...]))
                hyam = np.asarray(stitched.variables["hyam"][:], dtype=np.float64)
                hybm = np.asarray(stitched.variables["hybm"][:], dtype=np.float64)
                ps = np.asarray(stitched.variables["PS"][:], dtype=np.float64).squeeze()
                model_pressure = hyam[None, :] * p0 + hybm[None, :] * ps[:, None]

                for spec in PROFILE_VARS:
                    if spec.model not in stitched.variables or spec.obs not in obs.variables:
                        continue
                    model_values = np.asarray(stitched.variables[spec.model][:], dtype=np.float64).squeeze()
                    obs_values = np.asarray(obs.variables[spec.obs][:], dtype=np.float64).squeeze()

                    level_data = {}
                    for level_index, target_pressure in enumerate(obs_levels_pa):
                        model_at_level = interp_model_matrix_to_pressure(model_values, model_pressure, target_pressure)
                        obs_native = obs_values[:, level_index]
                        obs_at_model = interpolate_obs(obs_days, obs_native, model_days)
                        level_data[float(target_pressure)] = dict(
                            model_at_level=model_at_level,
                            obs_native=obs_native,
                            obs_at_model=obs_at_model,
                            diff=model_at_level - obs_at_model,
                            stats=stats(model_at_level, obs_at_model),
                        )

                    profile[spec.model] = dict(
                        spec=spec,
                        model_dates=model_dates,
                        obs_dates=obs_dates,
                        obs_levels_pa=obs_levels_pa,
                        level_data=level_data,
                    )
            return profile

        PROFILE_DATA = load_profile_data()
        print(f"Loaded {len(PROFILE_DATA)} profile variables and {len(next(iter(PROFILE_DATA.values()))['obs_levels_pa'])} pressure levels.")
        """
    ),
    code(
        r"""
        try:
            import ipywidgets as widgets
            import matplotlib.dates as mdates
            import matplotlib.pyplot as plt
            from IPython.display import display

            profile_names = list(PROFILE_DATA)
            pressure_options = [
                (f"{p / 100:.0f} hPa", float(p))
                for p in next(iter(PROFILE_DATA.values()))["obs_levels_pa"]
                if float(p) < 96500.0
            ]
            pressure_values = [value for _, value in pressure_options]
            default_pressure = min(pressure_values, key=lambda p: abs(p - 50000.0))

            profile_var = widgets.Dropdown(
                options=[(f"{name}: {PROFILE_DATA[name]['spec'].description}", name) for name in profile_names],
                value="T" if "T" in profile_names else profile_names[0],
                description="variable",
                layout=widgets.Layout(width="430px"),
            )
            pressure_level = widgets.SelectionSlider(
                options=pressure_options,
                value=default_pressure,
                description="level",
                continuous_update=False,
                readout=True,
                layout=widgets.Layout(width="620px"),
                style={"description_width": "50px"},
            )

            def profile_title(name, level_pa, d):
                spec = PROFILE_DATA[name]["spec"]
                s = d["stats"]
                return (
                    f"{name} at {level_pa / 100:.0f} hPa: stitched vs observation"
                    f"<br><sup>{spec.description} | obs={spec.obs} | "
                    f"bias={s['bias']:.3g} {spec.units}, RMSE={s['rmse']:.3g}, "
                    f"MAE={s['mae']:.3g}, n={s['n']}</sup>"
                )

            def draw_profile(name, level_pa):
                level_pa = float(level_pa)
                item = PROFILE_DATA[name]
                spec = item["spec"]
                d = item["level_data"][level_pa]

                s = d["stats"]
                title = (
                    f"{name} at {level_pa / 100:.0f} hPa: stitched vs observation\n"
                    f"{spec.description} | obs={spec.obs} | "
                    f"bias={s['bias']:.3g} {spec.units}, RMSE={s['rmse']:.3g}, "
                    f"MAE={s['mae']:.3g}, n={s['n']}"
                )

                fig, axes = plt.subplots(
                    2,
                    1,
                    figsize=(12, 7),
                    sharex=True,
                    gridspec_kw={"height_ratios": [2.1, 1.0], "hspace": 0.08},
                )
                axes[0].plot(item["obs_dates"], d["obs_native"], color="0.25", lw=1.1, alpha=0.75, label="observation")
                axes[0].plot(item["model_dates"], d["model_at_level"], color="#1261A6", lw=2.0, label="stitched")
                axes[0].set_ylabel(f"{name} ({spec.units})")
                axes[0].legend(loc="best", frameon=False)
                axes[0].grid(True, alpha=0.25)

                axes[1].plot(item["model_dates"], d["diff"], color="#C2410C", lw=1.4, label="stitched - observation")
                axes[1].axhline(0, color="black", lw=0.8)
                axes[1].set_ylabel(f"diff ({spec.units})")
                axes[1].set_xlabel("Time")
                axes[1].grid(True, alpha=0.25)

                axes[1].xaxis.set_major_locator(mdates.DayLocator(interval=4))
                axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
                fig.suptitle(title, x=0.02, ha="left", y=0.98)
                fig.autofmt_xdate(rotation=0)
                fig.subplots_adjust(top=0.86, left=0.08, right=0.98, bottom=0.10)
                display(fig)
                plt.close(fig)

            out = widgets.interactive_output(
                draw_profile,
                {"name": profile_var, "level_pa": pressure_level},
            )
            display(widgets.VBox([profile_var, pressure_level]), out)
        except Exception as exc:
            print("ipywidgets profile controls are unavailable in this kernel.")
            print(repr(exc))
        """
    ),
    md(
        """
        ## Optional static export

        Run this cell if you want a CSV copy of the summary table from the notebook session.
        """
    ),
    code(
        r"""
        out = ROOT / "mac_arm97_segment_design/comparison/stitched_vs_observation_interactive_summary.csv"
        summary.to_csv(out, index=False)
        out
        """
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "pygments_lexer": "ipython3",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK.write_text(json.dumps(notebook, indent=2) + "\n")
print(NOTEBOOK)
