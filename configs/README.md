# ARM97 Parameter Configs

This folder contains YAML parameter sets used by the ARM97 SCM PPE/QMC workflow.

## E3SMv3 Merged PPE Parameters

Source file: `params_arm97_e3smv3_qmc_ppe.yaml`

Length parameters from the professor-provided E3SMv3 table are stored in E3SM namelist SI units, i.e. meters.

| # | Parameter | Short name | ARM97 | atm_in_full | Baseline | Lower | Upper | Format | Source | Note |
|---:|---|---|---|---|---:|---:|---:|---|---|---|
| 1 | `zmconv_c0_lnd` | `c0_lnd` | `0.0020` | `0.0020D0` | 0.002 | 0.001 | 0.006 | `float` | `tuning-parameters-from-PPE-paper.docx` | Deep convection precipitation efficiency over land; zm_conv; Qian15/Ma. |
| 2 | `zmconv_c0_ocn` | `c0_ocn` | `0.0020` | `0.0020D0` | 0.002 | 0.001 | 0.006 | `float` | `tuning-parameters-from-PPE-paper.docx` | Deep convection precipitation efficiency over ocean; zm_conv; Qian15/Ma. |
| 3 | `cldfrc_dp1` | `dp1` | `0.018D0` | `0.018D0` | 0.1 | 0.02 | 0.1 | `D0` | `tuning-parameters-from-PPE-paper.docx` | Deep convection cloud fraction parameter; clubb_intr; Ma. |
| 4 | `zmconv_dmpdz` | `dmpdz` | `-0.7e-3` | `-0.7e-3` | -0.0005 | -0.002 | -0.0001 | `e` | `tuning-parameters-from-PPE-paper.docx` | Parcel fractional mass entrainment rate; zm_conv; Qian15/Neale. |
| 5 | `zmconv_ke` | `ke` | `2.5E-6` | `2.5E-6` | 0.000001 | 0.0000005 | 0.00001 | `E` | `tuning-parameters-from-PPE-paper.docx` | Evaporation efficiency of precipitation; zm_conv; Qian15. |
| 6 | `zmconv_alfa` | `alfa` | `0.14D0` | `0.14D0` | 0.10 | 0.05 | 0.60 | `D0` | `tuning-parameters-from-PPE-paper.docx` | Maximum cloud downdraft mass flux fraction; zm_conv; Qian15. |
| 7 | `zmconv_tau` | `tau` | `not set` | `3600` | 3600.0 | 1800.0 | 14400.0 | `float` | `tuning-parameters-from-PPE-paper.docx` | Time scale for consumption rate deep CAPE; zm_conv; Qian15/Neale. |
| 8 | `ice_sed_ai` | `ai` | `500.0` | `not set` | 700.0 | 350.0 | 1400.0 | `float` | `tuning-parameters-from-PPE-paper.docx` | Fall speed parameter for cloud ice; micro_mg_utils; Ma/Zhang. |
| 9 | `cldfrc2m_rhmaxi` | `rhmaxi` | `1.05D0` | `1.05D0` | 1.0 | 1.0 | 1.1 | `D0` | `tuning-parameters-from-PPE-paper.docx` | Max relative humidity threshold for ice cloud; cldfrc2m; Ma/Zhang. |
| 10 | `clubb_gamma_coef` | `gamma_coef` | `0.12D0` | `0.12D0` | 0.32 | 0.1 | 0.5 | `float` | `tuning-parameters-from-PPE-paper.docx` | Constant of the width of PDF in w coordinate; parameters_tunable; Guo15/Ma. |
| 11 | `clubb_C8` | `c8` | `5.2` | `5.2` | 4.2 | 2.0 | 8.0 | `float` | `tuning-parameters-from-PPE-paper.docx` | Constant associated with Newtonian damping; parameters_tunable; Guo15/Ma. |
| 12 | `clubb_beta` | `beta` | `not set` | `not set` | 2.4 | 1.0 | 3.0 | `float` | `tuning-parameters-from-PPE-paper.docx` | Constant related to skewness of theta_l and qt; parameters_tunable; Ma. |
| 13 | `clubb_C2rt` | `c2rt` | `1.75D0` | `1.75D0` | 1.0 | 0.5 | 2.0 | `D0` | `tuning-parameters-from-PPE-paper.docx` | Constant with dissipation of variance of total water; parameters_tunable; Guo15/Ma. |
| 14 | `clubb_c_K10` | `c_k10` | `0.35` | `0.35` | 0.6 | 0.3 | 1.2 | `float` | `tuning-parameters-from-PPE-paper.docx` | Momentum diffusion factor; parameters_tunable; Ma. |
| 15 | `clubb_C1` | `c1` | `2.4` | `2.4` | 1.0 | 1.0 | 5.0 | `float` | `tuning-parameters-from-PPE-paper.docx` | Constant associated with dissipation of variance; parameters_tunable; Ma. |
| 16 | `clubb_C6rt` | `c6rt` | `not set` | `not set` | 4.0 | 3.0 | 8.0 | `float` | `tuning-parameters-from-PPE-paper.docx` | Low skewness of Newtonian damping of water flux; parameters_tunable; Qian. |
| 17 | `effgw_oro` | `effgw_oro` | `0.375` | `0.375` | 0.3 | 0.1 | 0.4 | `float` | `tuning-parameters-from-PPE-paper.docx` | Gravity wave drag intensity; gw_drag; Ma. |
| 18 | `nucleate_ice_subgrid` | `ice_subgrid` | `not set` | `1.35D0` | 1.35 | 1.0 | 1.3 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Subgrid RH factor for ice nucleation; v3 default from atm_in_full, perturbation range from professor table. |
| 19 | `so4_sz_thresh_icenuc` | `so4_ice` | `0.080e-6` | `0.080e-6` | 0.00000008 | 0.00000005 | 0.0000001 | `e` | `Tuning+parameters+in+ZM+and+P3.doc` | Sulfate aerosol size threshold for ice nucleation; 50-100 nm range converted to meters, baseline 80 nm. |
| 20 | `p3_wbf_coeff` | `wbf` | `not set` | `1.0` | 1.0 | 0.1 | 1.0 | `float` | `Tuning+parameters+in+ZM+and+P3.doc` | WBF coefficient; v3-only P3 microphysics parameter. |
| 21 | `p3_max_mean_rain_size` | `max_rain_size` | `not set` | `0.005D0` | 0.005 | 0.0002 | 0.005 | `D` | `Tuning+parameters+in+ZM+and+P3.doc` | Maximal mean raindrop size; 0.2-5 mm range converted to meters. |
| 22 | `p3_embryonic_rain_size` | `embryonic_rain_size` | `not set` | `0.000025D0` | 0.000025 | 0.000015 | 0.00005 | `D` | `Tuning+parameters+in+ZM+and+P3.doc` | Embryonic raindrop size for autoconversion; 15-50 um range converted to meters. |
| 23 | `p3_autocon_coeff` | `autocon_coeff` | `not set` | `30500.0D0` | 30500.0 | 1350.0 | 30500.0 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Autoconversion coefficient; two professor-table values treated as a continuous min/max range. |
| 24 | `p3_qc_autocon_expon` | `qc_autocon_expon` | `not set` | `3.19D0` | 3.19 | 2.47 | 3.2 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Autoconversion qc exponent; v3 default from atm_in_full. |
| 25 | `p3_nc_autocon_expon` | `nc_autocon_expon` | `not set` | `-1.10D0` | -1.10 | -1.79 | -1.4 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Autoconversion nc exponent; two professor-table values treated as a continuous min/max range. |
| 26 | `p3_accret_coeff` | `accret_coeff` | `not set` | `117.25D0` | 117.25 | 67.0 | 117.25 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Accretion coefficient; two professor-table values treated as a continuous min/max range. |
| 27 | `p3_qc_accret_expon` | `qc_accret_expon` | `not set` | `1.15D0` | 1.15 | 1.0 | 2.0 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Accretion qc/qr exponent; v3 default from atm_in_full. |
| 28 | `zmconv_auto_fac` | `zm_auto_fac` | `not set` | `7.0D0` | 7.0 | 3.0 | 7.5 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Autoconversion enhancement factor in ZM microphysics; v3-only professor table parameter. |
| 29 | `zmconv_accr_fac` | `zm_accr_fac` | `not set` | `1.5D0` | 1.5 | 1.5 | 2.0 | `D0` | `Tuning+parameters+in+ZM+and+P3.doc` | Accretion enhancement factor in ZM microphysics; v3-only professor table parameter. |
| 30 | `zmconv_micro_dcs` | `zm_micro_dcs` | `not set` | `150.E-6` | 0.00015 | 0.0001 | 0.0004 | `e` | `Tuning+parameters+in+ZM+and+P3.doc` | Autoconversion size threshold for cloud ice; 100-400 um range converted to meters. |

Note: `mi0` and `re_ice` appear in the professor-provided parameter documents, but they are excluded from the runnable PPE YAML for now. This local E3SM checkout does not define `mi0` in `components/eam/bld/namelist_files/namelist_definition.xml`; adding it to `user_nl_eam` fails namelist validation. `re_ice` was also not added because the matching E3SM namelist variable is not confirmed in the active ARM97 templates or `atm_in_full`. Add either parameter only after the exact supported E3SM namelist name is confirmed.
