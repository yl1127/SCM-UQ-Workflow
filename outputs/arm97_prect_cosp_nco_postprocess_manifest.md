# ARM97 PRECT/COSP NCO Post-Processing

Generated ready-to-visualize NetCDF files:

- `outputs/arm97_prect_cosp_model_ready.nc`
- `outputs/arm97_iop_observation_model_window_nco.nc`

NCO tools:

```sh
/private/tmp/scm-uq-nco/bin/ncks --version
# ncks version 5.3.9
```

Commands used:

```sh
MODEL=/Users/yunlong/projects/e3sm/SCM_runs/e3sm_scm_ARM97_prect_cosp/run/e3sm_scm_ARM97_prect_cosp.eam.h0.1997-06-19-84585.nc
OBS=/Users/yunlong/Workshop/SCM-UQ-Workflow/scripts_baseline/ARM97_iopfile_4scam.nc

/private/tmp/scm-uq-nco/bin/ncks -O "$MODEL" outputs/arm97_prect_cosp_model_ready.nc
/private/tmp/scm-uq-nco/bin/ncks -O -d time,72,1944 "$OBS" outputs/arm97_iop_observation_model_window_nco.nc
```

The observation slice uses the absolute-time overlap with the model run:

- model: `1997-06-19 23:29:45` to `1997-07-15 23:29:45`
- observation slice: indices `72..1944`, interpreted as `bdate + tsec`
- observation slice start/end: `1997-06-19 23:29:45.937500` to `1997-07-15 23:29:46`

This preserves the original NetCDF time variables and avoids Python-side time rewriting or concatenation.
