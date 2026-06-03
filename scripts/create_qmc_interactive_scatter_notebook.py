from pathlib import Path
import os

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/QMC_interactive_scatter_expanded_variables.ipynb"


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "pygments_lexer": "ipython3"},
}

nb["cells"] = [
    nbf.v4.new_markdown_cell(
        """# Interactive QMC scatter analysis

This notebook expands the SCM response variables and builds an interactive Plotly scatter plot.

- x-axis: one normalized QMC design parameter
- y-axis: one SCM response metric
- color: optional case attribute, response metric, or parameter

The normalized parameter value is `(sample - baseline) / (0.2 * abs(baseline))`, so `-1` and `+1` correspond to the -20% and +20% QMC design bounds."""
    ),
    nbf.v4.new_code_cell(
        """from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import xarray as xr
from IPython.display import display
from ipywidgets import Dropdown, Checkbox, interact

ROOT = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()
RUN_ROOT = Path(os.environ.get("SCM_RUNS", "/path/to/SCM_runs"))
DESIGN = ROOT / 'qmc_design' / 'e3sm_scm_qmc_64_design.csv'
BASELINE = ROOT / 'qmc_design' / 'e3sm_scm_qmc_baseline.csv'
STATUS = ROOT / 'qmc_design' / 'e3sm_scm_qmc_run_status.csv'
OUT = ROOT / 'qmc_analysis'
OUT.mkdir(exist_ok=True)

px.defaults.template = 'plotly_white'"""
    ),
    nbf.v4.new_markdown_cell("## Load QMC design and define continuous parameters"),
    nbf.v4.new_code_cell(
        """design = pd.read_csv(DESIGN)
baseline = pd.read_csv(BASELINE).iloc[0]
status = pd.read_csv(STATUS)

success_cases = status.loc[status['status'].eq('success'), 'case'].tolist()
design = design[design['case'].isin(success_cases)].copy()

fixed_cols = {'case', 'qmc_index', 'qmc_sampler', 'qmc_seed', 'do_tms', 'zmconv_cape_cin', 'zmconv_mx_bot_lyr_adj', 'se_ftype'}
param_numeric_cols = [
    c for c in design.columns
    if c.endswith('_numeric') and c.replace('_numeric', '') not in fixed_cols
]
parameters = [c.replace('_numeric', '') for c in param_numeric_cols]

for p in parameters:
    base = float(baseline[f'{p}_numeric'])
    denom = 0.2 * abs(base)
    design[f'{p}_norm'] = (design[f'{p}_numeric'] - base) / denom if denom else np.nan

parameter_norm_cols = [f'{p}_norm' for p in parameters]
print(f'Successful QMC cases: {len(design)}')
print(f'Continuous QMC parameters: {len(parameters)}')"""
    ),
    nbf.v4.new_markdown_cell("## Extract expanded SCM response metrics"),
    nbf.v4.new_code_cell(
        """def history_file(case):
    files = sorted((RUN_ROOT / case / 'run').glob('*.eam.h0.*.nc'))
    if not files:
        raise FileNotFoundError(f'No history file found for {case}')
    return files[0]


def scalar_time_series(ds, name):
    if name not in ds:
        return None
    da = ds[name]
    if 'ncol' in da.dims:
        da = da.isel(ncol=0)
    return da


def finite_float(value):
    value = float(value)
    return value if np.isfinite(value) else np.nan


def case_metrics(case):
    with xr.open_dataset(history_file(case)) as ds:
        out = {'case': case, 'final_time': str(ds['time'].isel(time=-1).values)}

        for name in ['TREFHT', 'TS', 'CLDTOT', 'TGCLDLWP', 'TGCLDIWP', 'LHFLX', 'SHFLX', 'FSNT', 'FLNT']:
            da = scalar_time_series(ds, name)
            if da is None:
                continue
            units = da.attrs.get('units', '')
            suffix = {'K': '_K', 'W/m2': '_Wm2', 'kg/m2': '_kgm2', '1': ''}.get(units, '')
            out[f'{name}_final{suffix}'] = finite_float(da.isel(time=-1).values)
            out[f'{name}_mean{suffix}'] = finite_float(da.mean('time').values)
            out[f'{name}_min{suffix}'] = finite_float(da.min('time').values)
            out[f'{name}_max{suffix}'] = finite_float(da.max('time').values)

        precc = scalar_time_series(ds, 'PRECC')
        precl = scalar_time_series(ds, 'PRECL')
        if precc is not None and precl is not None:
            prect = precc + precl
            # EAM PRECC/PRECL are m/s liquid water equivalent. Convert rates to mm/day,
            # and integrate over the output timestep to get accumulated mm.
            prect_mm_day = prect * 1000.0 * 86400.0
            seconds = ds['time'].diff('time') / np.timedelta64(1, 's')
            if seconds.size:
                dt = float(seconds.median().values)
            else:
                dt = np.nan
            out['PRECT_mean_mm_day'] = finite_float(prect_mm_day.mean('time').values)
            out['PRECT_max_mm_day'] = finite_float(prect_mm_day.max('time').values)
            out['PRECT_accum_mm'] = finite_float((prect * 1000.0 * dt).sum('time').values)

        if 'FSNT' in ds and 'FLNT' in ds:
            fsnt = scalar_time_series(ds, 'FSNT')
            flnt = scalar_time_series(ds, 'FLNT')
            toa_net = fsnt - flnt
            out['TOA_net_final_Wm2'] = finite_float(toa_net.isel(time=-1).values)
            out['TOA_net_mean_Wm2'] = finite_float(toa_net.mean('time').values)
            out['TOA_net_min_Wm2'] = finite_float(toa_net.min('time').values)
            out['TOA_net_max_Wm2'] = finite_float(toa_net.max('time').values)

        if 'T' in ds:
            t = ds['T']
            if 'ncol' in t.dims:
                t = t.isel(ncol=0)
            lowest = t.isel(lev=-1)
            out['T_lowest_lev_final_K'] = finite_float(lowest.isel(time=-1).values)
            out['T_lowest_lev_mean_K'] = finite_float(lowest.mean('time').values)

        if 'Q' in ds:
            q = ds['Q']
            if 'ncol' in q.dims:
                q = q.isel(ncol=0)
            lowest = q.isel(lev=-1)
            out['Q_lowest_lev_final_kgkg'] = finite_float(lowest.isel(time=-1).values)
            out['Q_lowest_lev_mean_kgkg'] = finite_float(lowest.mean('time').values)

        return out


rows = [case_metrics(case) for case in design['case']]
responses = pd.DataFrame(rows)
responses_csv = OUT / 'qmc_expanded_responses_by_case.csv'
responses.to_csv(responses_csv, index=False)
print(f'Saved {responses_csv}')
responses.head()"""
    ),
    nbf.v4.new_markdown_cell("## Merge design parameters and response metrics"),
    nbf.v4.new_code_cell(
        """df = design.merge(responses, on='case', how='inner')

response_cols = [
    c for c in responses.columns
    if c not in {'case', 'final_time'} and pd.api.types.is_numeric_dtype(responses[c])
]

merged_csv = OUT / 'qmc_design_with_expanded_responses.csv'
df.to_csv(merged_csv, index=False)
print(f'Saved {merged_csv}')
print(f'Response metrics: {len(response_cols)}')
display(df[['case'] + response_cols[:8]].head())"""
    ),
    nbf.v4.new_markdown_cell("## Interactive scatter plot"),
    nbf.v4.new_code_cell(
        """x_options = {p: f'{p}_norm' for p in parameters}
y_options = {c: c for c in response_cols}
color_options = {'qmc_index': 'qmc_index', 'none': None}
color_options.update({c: c for c in response_cols})
color_options.update({p: f'{p}_norm' for p in parameters})


def draw_scatter(x_parameter='clubb_C8', y_response='TREFHT_final_K', color_by='qmc_index', show_trend=True):
    x_col = x_options[x_parameter]
    y_col = y_options[y_response]
    color_col = color_options[color_by]
    trendline = 'ols' if show_trend else None

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        color=color_col,
        hover_name='case',
        hover_data=['qmc_index', 'final_time'],
        trendline=trendline,
        labels={
            x_col: f'{x_parameter} normalized perturbation',
            y_col: y_response,
        },
        title=f'{y_response} vs {x_parameter}',
        width=950,
        height=620,
    )
    fig.add_vline(x=0, line_dash='dash', line_color='gray', opacity=0.6)
    fig.update_traces(marker={'size': 9, 'opacity': 0.85})
    fig.update_layout(legend_title_text=color_by)
    fig.show()


interact(
    draw_scatter,
    x_parameter=Dropdown(options=parameters, value='clubb_C8', description='x param'),
    y_response=Dropdown(options=response_cols, value='TREFHT_final_K', description='y response'),
    color_by=Dropdown(options=list(color_options), value='qmc_index', description='color'),
    show_trend=Checkbox(value=True, description='OLS trend'),
);"""
    ),
    nbf.v4.new_markdown_cell("## Parameter-response Spearman correlation heatmap"),
    nbf.v4.new_code_cell(
        """corr_rows = []
for p in parameters:
    x = df[f'{p}_norm']
    for y in response_cols:
        corr_rows.append({
            'parameter': p,
            'response': y,
            'spearman': x.corr(df[y], method='spearman'),
            'pearson': x.corr(df[y], method='pearson'),
        })

corr = pd.DataFrame(corr_rows)
corr_csv = OUT / 'qmc_expanded_parameter_response_correlations.csv'
corr.to_csv(corr_csv, index=False)

heat = corr.pivot(index='parameter', columns='response', values='spearman')
fig = px.imshow(
    heat,
    color_continuous_scale='RdBu_r',
    zmin=-1,
    zmax=1,
    aspect='auto',
    title='Spearman correlation: normalized QMC parameters vs expanded SCM responses',
    labels={'x': 'response metric', 'y': 'QMC parameter', 'color': 'Spearman'},
    width=1200,
    height=850,
)
fig.update_xaxes(tickangle=45)
fig.show()
print(f'Saved {corr_csv}')"""
    ),
    nbf.v4.new_markdown_cell("## Strongest absolute Spearman relationships"),
    nbf.v4.new_code_cell(
        """top = corr.assign(abs_spearman=corr['spearman'].abs()).sort_values('abs_spearman', ascending=False)
top_csv = OUT / 'qmc_expanded_top_spearman_relationships.csv'
top.to_csv(top_csv, index=False)
display(top.head(25))
print(f'Saved {top_csv}')"""
    ),
]

nbf.write(nb, NOTEBOOK)
print(NOTEBOOK)
