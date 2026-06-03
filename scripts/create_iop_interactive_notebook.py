#!/usr/bin/env python3
"""Create an interactive notebook for ARM97 IOP forcing/observation variables."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/IOP_observation_interactive_plots.ipynb"


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
        # ARM97 IOP interactive plots

        This notebook reads the ARM97 SCM IOP file used by the current E3SM SCM cases and
        provides interactive plots for surface/column variables and vertical profile variables.

        It intentionally uses the command-line `ncdump` reader so it can run even when
        `xarray`/`netCDF4` are not installed in the active Python kernel.
        """
    ),
    code(
        r"""
        from pathlib import Path
        import os
        import re
        import subprocess

        ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
        os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".local_cache/cache"))
        os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local_cache/matplotlib-cache"))
        Path(os.environ["XDG_CACHE_HOME"]).mkdir(exist_ok=True)
        Path(os.environ["MPLCONFIGDIR"]).mkdir(exist_ok=True)

        from datetime import datetime
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        try:
            from IPython.display import display
        except Exception:
            display = print

        IOP_FILE = Path(os.environ.get("ARM97_IOP_FILE", "/path/to/ARM97_iopfile_4scam.nc"))
        assert IOP_FILE.exists(), IOP_FILE

        PROFILE_VARS = [
            "T", "q", "u", "v", "omega", "WD",
            "divT", "vertdivTx", "divq", "vertdivq",
            "s", "divs", "vertdivT", "ds_dt", "dT_dt", "dq_dt",
            "Q1", "Q2", "ARSCL_cld", "rh",
        ]

        SURFACE_VARS = [
            "Ptend", "Prec", "lhflx", "shflx", "Ps", "CF_Ps", "Tsair", "Tg",
            "RHsair", "windsrf", "usrf", "vsrf", "NDRsrf", "TOA_LWup",
            "TOA_SWdn", "TOA_ins", "lowcld", "midcld", "hghcld", "totcld",
            "cldthk", "cldht", "cldliq", "dcolH2Odt", "colH2OAdv", "evapsrf",
            "dcolDSEdt", "colDSEAdv", "colRH", "colLH", "omegas", "qs", "ss",
            "prew", "srflwup", "srflwdn", "srfswup", "srfswdn", "alb",
        ]

        UNITS = {
            "T": "K", "q": "kg/kg", "u": "m/s", "v": "m/s", "omega": "Pa/s",
            "WD": "1/s", "divT": "K/s", "vertdivTx": "K/s", "divq": "kg/kg/s",
            "vertdivq": "kg/kg/s", "s": "K", "divs": "K/s", "vertdivT": "K/s",
            "ds_dt": "K/s", "dT_dt": "K/s", "dq_dt": "kg/kg/s", "Q1": "K/s",
            "Q2": "K/s", "ARSCL_cld": "%", "rh": "%",
            "Ptend": "Pa/s", "Prec": "mm/s", "lhflx": "W/m2", "shflx": "W/m2",
            "Ps": "Pa", "CF_Ps": "Pa", "Tsair": "K", "Tg": "K", "RHsair": "%",
            "windsrf": "m/s", "usrf": "m/s", "vsrf": "m/s", "NDRsrf": "W/m2",
            "TOA_LWup": "W/m2", "TOA_SWdn": "W/m2", "TOA_ins": "W/m2",
            "lowcld": "%", "midcld": "%", "hghcld": "%", "totcld": "%",
            "cldthk": "m", "cldht": "m", "cldliq": "m", "dcolH2Odt": "mm/s",
            "colH2OAdv": "mm/s", "evapsrf": "mm/s", "dcolDSEdt": "K",
            "colDSEAdv": "W/m2", "colRH": "W/m2", "colLH": "W/m2",
            "omegas": "mb/hr", "qs": "kg/kg", "ss": "K", "prew": "cm",
            "srflwup": "W/m2", "srflwdn": "W/m2", "srfswup": "W/m2",
            "srfswdn": "W/m2", "alb": "fraction",
        }

        DIMS = {"time": 2089, "lev": 35, "lat": 1, "lon": 1}

        print(IOP_FILE)
        print(DIMS)
        print(f"{len(PROFILE_VARS)} profile variables, {len(SURFACE_VARS)} surface/column variables")
        """
    ),
    md(
        """
        ## Data reader

        The first access to a variable may take a few seconds because `ncdump` prints the
        selected variable and Python parses the numeric values. Results are cached in memory.
        """
    ),
    code(
        r"""
        _CACHE = {}

        def _run_ncdump(varname):
            cmd = ["ncdump", "-v", varname, str(IOP_FILE)]
            return subprocess.check_output(cmd, text=True)

        def _parse_values(text, varname):
            marker = "\ndata:"
            if marker not in text:
                raise ValueError(f"Could not find data section for {varname}")
            data_text = text.split(marker, 1)[1]
            match = re.search(rf"\b{re.escape(varname)}\s*=\s*(.*?);", data_text, flags=re.S)
            if not match:
                raise ValueError(f"Could not find assignment for {varname}")
            payload = match.group(1).replace("\n", " ")
            payload = re.sub(r"//.*?(?=,|$)", " ", payload)
            values = np.fromstring(payload.replace(",", " "), sep=" ")
            return values

        def read_var(varname):
            if varname in _CACHE:
                return _CACHE[varname]
            values = _parse_values(_run_ncdump(varname), varname)
            if varname in PROFILE_VARS:
                arr = values.reshape(DIMS["time"], DIMS["lev"], DIMS["lat"], DIMS["lon"])[:, :, 0, 0]
            elif varname in SURFACE_VARS:
                arr = values.reshape(DIMS["time"], DIMS["lat"], DIMS["lon"])[:, 0, 0]
            elif varname == "lev":
                arr = values
            elif varname in {"time", "tsec", "year", "month", "day", "hour", "minute"}:
                arr = values
            else:
                arr = values
            _CACHE[varname] = arr
            return arr

        lev_pa = read_var("lev")
        tsec = read_var("tsec")
        time_days = (tsec - tsec[0]) / 86400.0

        years = read_var("year").astype(int)
        months = read_var("month").astype(int)
        days = read_var("day").astype(int)
        hours = read_var("hour").astype(int)
        minutes = read_var("minute").astype(int)
        datetimes = np.array([
            datetime(y, m, d, h, minute)
            for y, m, d, h, minute in zip(years, months, days, hours, minutes)
        ])

        def label(varname):
            unit = UNITS.get(varname, "")
            return f"{varname} ({unit})" if unit else varname

        print("Loaded lev and tsec")
        """
    ),
    md(
        """
        ## Plot functions

        Use these directly if widgets are unavailable in your Jupyter kernel.

        Examples:

        ```python
        plot_profile("T", time_index=0)
        plot_profile("T", time_index=400)
        plot_time_height("divT")
        plot_surface("Prec")
        ```
        """
    ),
    code(
        r"""
        def plot_profile(varname="T", time_index=0):
            if varname not in PROFILE_VARS:
                raise ValueError(f"{varname} is not a profile variable")
            arr = read_var(varname)
            time_index = int(np.clip(time_index, 0, arr.shape[0] - 1))
            fig, ax = plt.subplots(figsize=(6.5, 7))
            ax.plot(arr[time_index, :], lev_pa / 100.0, marker="o", ms=3, lw=1.5)
            ax.invert_yaxis()
            ax.grid(True, alpha=0.3)
            ax.set_xlabel(label(varname))
            ax.set_ylabel("IOP pressure level (hPa)")
            ax.set_title(f"{varname} profile at time_index={time_index}, day={time_days[time_index]:.2f}")
            plt.show()

        def plot_time_height(varname="T", stride=1, style="raw"):
            if varname not in PROFILE_VARS:
                raise ValueError(f"{varname} is not a profile variable")
            arr = read_var(varname)
            stride = max(1, int(stride))
            z = arr[::stride, :].T

            if style == "anomaly":
                x = datetimes[::stride]
                z = z - np.nanmean(arr)
                lim = float(np.nanmax(np.abs(z)))
                fig, ax = plt.subplots(figsize=(12, 5.4))
                mesh = ax.pcolormesh(
                    x, lev_pa / 100.0, z,
                    shading="auto", cmap="RdBu_r", vmin=-lim, vmax=lim,
                )
                ax.grid(True, alpha=0.22, color="0.65")
                ax.set_xlabel("Time")
                ax.set_ylabel("Level")
                ax.set_title(f"{varname}: {UNITS.get(varname, '')} anomaly from overall mean", fontweight="bold")
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
                fig.autofmt_xdate(rotation=32, ha="right")
            else:
                x = time_days[::stride]
                cmap = "RdBu_r"
                fig, ax = plt.subplots(figsize=(10, 6))
                mesh = ax.pcolormesh(x, lev_pa / 100.0, z, shading="auto", cmap="viridis")
                ax.set_xlabel("Days since first IOP time")
                ax.set_ylabel("IOP pressure level (hPa)")
                ax.set_title(f"{varname} time-height section")

            ax.invert_yaxis()
            cb = fig.colorbar(mesh, ax=ax)
            cb.set_label(label(varname) if style == "raw" else UNITS.get(varname, ""))
            plt.show()

        def plot_surface(varname="Ps"):
            if varname not in SURFACE_VARS:
                raise ValueError(f"{varname} is not a surface/column variable")
            arr = read_var(varname)
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(time_days, arr, lw=1.2)
            ax.grid(True, alpha=0.3)
            ax.set_xlabel("Days since first IOP time")
            ax.set_ylabel(label(varname))
            ax.set_title(f"{varname} time series")
            plt.show()

        def plot_profile_level_time_series(varname="T", level_index=0):
            if varname not in PROFILE_VARS:
                raise ValueError(f"{varname} is not a profile variable")
            arr = read_var(varname)
            level_index = int(np.clip(level_index, 0, arr.shape[1] - 1))
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(time_days, arr[:, level_index], lw=1.2)
            ax.grid(True, alpha=0.3)
            ax.set_xlabel("Days since first IOP time")
            ax.set_ylabel(label(varname))
            ax.set_title(
                f"{varname} at IOP level_index={level_index}, "
                f"pressure={lev_pa[level_index] / 100.0:.1f} hPa"
            )
            plt.show()

        plot_profile("T", 0)
        """
    ),
    md(
        """
        ## Interactive controls
        """
    ),
    code(
        r"""
        try:
            import ipywidgets as widgets
            from IPython.display import clear_output

            profile_var = widgets.Dropdown(options=PROFILE_VARS, value="T", description="profile")
            surface_var = widgets.Dropdown(options=SURFACE_VARS, value="Ps", description="surface")
            time_index = widgets.IntSlider(value=0, min=0, max=DIMS["time"] - 1, step=1, description="time")
            level_index = widgets.IntSlider(value=0, min=0, max=DIMS["lev"] - 1, step=1, description="level")
            time_stride = widgets.IntSlider(value=4, min=1, max=48, step=1, description="time stride")
            heatmap_style = widgets.ToggleButtons(
                options=[("raw", "raw"), ("anomaly", "anomaly")],
                value="raw",
                description="heatmap",
            )
            mode = widgets.ToggleButtons(
                options=["profile", "time-height", "level time series", "surface time series"],
                value="profile",
                description="plot",
            )
            out = widgets.Output()

            def redraw(*_):
                with out:
                    clear_output(wait=True)
                    if mode.value == "profile":
                        plot_profile(profile_var.value, time_index.value)
                    elif mode.value == "time-height":
                        plot_time_height(profile_var.value, time_stride.value, heatmap_style.value)
                    elif mode.value == "level time series":
                        plot_profile_level_time_series(profile_var.value, level_index.value)
                    else:
                        plot_surface(surface_var.value)

            for w in [profile_var, surface_var, time_index, level_index, time_stride, heatmap_style, mode]:
                w.observe(redraw, names="value")

            controls = widgets.VBox([
                mode,
                widgets.HBox([profile_var, surface_var]),
                widgets.HBox([time_index, level_index, time_stride]),
                heatmap_style,
            ])
            display(controls, out)
            redraw()
        except Exception as exc:
            print("ipywidgets is not available in this kernel. Use plot_profile, plot_time_height, or plot_surface directly.")
            print(repr(exc))
        """
    ),
    md(
        """
        ## Quick variable browser
        """
    ),
    code(
        r"""
        print("Profile variables:")
        for name in PROFILE_VARS:
            print(f"  {name:12s} {UNITS.get(name, '')}")

        print("\nSurface/column variables:")
        for name in SURFACE_VARS:
            print(f"  {name:12s} {UNITS.get(name, '')}")
        """
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
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
