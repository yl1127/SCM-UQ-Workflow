#!/bin/csh

#######################################################################
#######################################################################
#######  Script to run E3SM in SCM for
#######  ARM97
#######  Deep convection over ARM SGP site
#######
#######  Script Author: P. Bogenschutz (bogenschutz1@llnl.gov)

#######################################################
#######  BEGIN USER DEFINED SETTINGS

  # Set the name of your case here
  setenv casename run_e3sm_scm_ARM97_qmc64_0706_057

  # Set the case directory here
  if (! $?SCM_RUNS) setenv SCM_RUNS /path/to/SCM_runs
  setenv casedirectory $SCM_RUNS
  # Directory where code lives
  # setenv code_dir $HOME/pe3sm/codes/E3SM_codes/E3SM.maint-2.1
  if (! $?E3SM_CODE_DIR) setenv E3SM_CODE_DIR /path/to/E3SM
  setenv code_dir $E3SM_CODE_DIR
  # Code tag name. Not used
  setenv code_tag E3SM_codetag

  # Name of machine you are running on (i.e. edison, anvil, etc)
  setenv machine Mac

  # Want to submit run to the queue?
  #   Setting to false will submit run directly
  #   onto the login nodes rather than using
  #   the batch queue
  setenv submit_to_queue false

  # Name of project to run on, if submitting to queue
  setenv projectname e3sm

  # Following option affect CAM_CONFIG_OPTIONS, Extra attention needed

  # Aerosol specification
  # Options include:
  #  1) cons_droplet (sets cloud liquid and ice concentration
  #                   to a constant)
  #  2) prescribed (uses climatologically prescribed aerosol
  #                 concentration)
  setenv init_aero_type prescribed
  # setenv init_aero_type cons_droplet

# User enter any needed modules to load or use below
#  EXAMPLE:
  # module load python # disabled on local Mac; use system python via PATH

  if ($?SCM_UQ_EXTRA_PATH) then
    setenv PATH ${SCM_UQ_EXTRA_PATH}:$PATH
  endif
  # The reused qmc_ARM97_baseline executable was built in a "nothreads"
  # configuration, so keep OpenMP at 1 thread and avoid oversubscription.
  setenv OMP_NUM_THREADS 1
  setenv OMP_PROC_BIND false
  setenv VECLIB_MAXIMUM_THREADS 1
  setenv OPENBLAS_NUM_THREADS 1

####### END USER DEFINED SETTINGS
####### Likely POSSIBLE EXCEPTION (not limited to):
#######  - If the user wants to add addition output, for example, the CAM
#######	   namelist (user_nl_eam) should be modified below to accomodate for this
###########################################################################
###########################################################################
###########################################################################

  # Set the dynamical core
  #  Note that currently the default dynamical core for the SCM is
  #  the Eulerian core.  Soon, this will change.  Currently running
  #  with the SE dynamical core is unsupported.
  #setenv dycore Eulerian
  setenv dycore SE    # Only SE supported in maint-2.1

# Case specific information kept here
  set lat = 36.6 # latitude
  set lon = 262.5 # longitude
  set do_iop_srf_prop = .true. # Use surface fluxes in IOP file?
  set do_scm_relaxation = .false. # Relax case to observations?
  set do_turnoff_swrad = .false. # Turn off SW calculation
  set do_turnoff_lwrad = .false. # Turn off LW calculation
  set do_turnoff_precip = .false. # Turn off precipitation
  set micro_nccons_val = 100D6 # cons_droplet value for liquid
  set micro_nicons_val = 0.0001D6 # cons_droplet value for ice
  set startdate = 1997-06-19 # Experiment start date
  set start_in_sec = 84585 # Experiment start time in seconds
  set stop_option = ndays
  set stop_n = 26
  set iop_file = ARM97_iopfile_4scam.nc #IOP file name
# End Case specific stuff here

  # Location of IOP file
  set iop_path = atm/cam/scam/iop

  # Prescribed aerosol file path and name
  set presc_aero_path = atm/cam/chem/trop_mam/aero
  set presc_aero_file = mam5_0.9x1.2_L80_F2010_c013024.nc

  set PROJECT=$projectname
# set E3SMROOT=${code_dir}/${code_tag}
  set E3SMROOT=${code_dir}

  cd $E3SMROOT/cime/scripts
  set compset=FSCM-ARM97

  if ($dycore == Eulerian) then
    set grid=T42_T42
  endif

  if ($dycore == SE) then
    set grid=ne4_ne4
  endif

  set CASEID=$casename

  set CASEDIR=${casedirectory}/$CASEID

  set run_root_dir = $CASEDIR
  set temp_case_scripts_dir = $run_root_dir/case_scripts

  set case_scripts_dir = $run_root_dir/case_scripts
  set case_build_dir   = $run_root_dir/build
  set case_run_dir     = $run_root_dir/run

  set walltime = '00:20:00'

# COSP satellite simulator output
  setenv do_cosp  true

# Create new case
  ./create_newcase -case $temp_case_scripts_dir -mach $machine -project $PROJECT -compset $compset -res $grid --walltime $walltime
  cd $temp_case_scripts_dir

# SCM must run in serial mode
  if ($dycore == Eulerian) then
    ./xmlchange --id MPILIB --val mpi-serial
  endif

# Define executable and run directories
  ./xmlchange --id EXEROOT --val "${case_build_dir}"
  ./xmlchange --id RUNDIR --val "${case_run_dir}"

# Use implicit surface stress coupling as the baseline for PPE/QMC experiments.
  ./xmlchange ATM_FLUX_INTEGRATION_METHOD="implicit_stress"

# Set to debug, only on certain machines
  if ($machine == edison) then
    ./xmlchange --id JOB_QUEUE --val 'debug'
  endif

  if ($submit_to_queue == false) then
   #./xmlchange --id RUN_WITH_SUBMIT --val 'TRUE'
    ./xmlchange --id SAVE_TIMING --val 'FALSE'
  endif

# Minimize profiling overhead for fast local runs.  This does not affect
# model physics or history output.
  ./xmlchange --id TIMER_DETAIL --val 0
  ./xmlchange --id TIMER_LEVEL --val 0
  ./xmlchange --id TPROF_TOTAL --val 0

# Get local input data directory path
  set input_data_dir = `./xmlquery DIN_LOC_ROOT -value`

# SCM is run as one MPI task.  The reused executable is not OpenMP-threaded.
  set npes = 1
  foreach component ( ATM LND ICE OCN CPL GLC ROF WAV )
    ./xmlchange  NTASKS_$component=$npes,NTHRDS_$component=1
  end

# CAM configure options.  By default set up with settings the same as E3SMv1
# set CAM_CONFIG_OPTS="-phys cam5 -scam -nlev 72 -clubb_sgs"
# EAMv2 config options for SCM

  #set CAM_CONFIG_OPTS="-phys default -scam -nlev 72 -clubb_sgs"
  # Match the reusable Mac executable configured by the baseline PRECT/COSP run.
  set CAM_CONFIG_OPTS="-phys default -scam -nlev 80 -clubb_sgs -microphys p3"
  if ($dycore == Eulerian) then
    set CAM_CONFIG_OPTS="$CAM_CONFIG_OPTS -nospmd -nosmp"
  endif

  if ( $do_cosp == true ) then
    set  CAM_CONFIG_OPTS="$CAM_CONFIG_OPTS -cosp -verbose"
  endif

# CAM configure options dependant on what aerosol specification is used
  if ($init_aero_type == cons_droplet) then
    set CAM_CONFIG_OPTS="$CAM_CONFIG_OPTS -chem none"
  endif

  if ($init_aero_type == prescribed || $init_aero_type == observed) then
    set CAM_CONFIG_OPTS="$CAM_CONFIG_OPTS -chem none"
  endif

  ./xmlchange CAM_CONFIG_OPTS="$CAM_CONFIG_OPTS"
  set clubb_micro_steps = 8
# If SE dycore is used then we need to change the timestep
# to be consistent with ne30 timestep.  Also change the
# cld_macmic_num_steps to be consistent
  if ($dycore == SE) then
    ./xmlchange ATM_NCPL='48'
    ./xmlchange CAM_TARGET='theta-l'
    set clubb_micro_steps = 6
  endif

# User enter CAM namelist options
#  Add additional output here for example
cat <<EOF >> user_nl_eam
 cld_macmic_num_steps = $clubb_micro_steps
 cosp_lite = .true.
 use_gw_front = .false.
 iopfile = '$input_data_dir/$iop_path/$iop_file'
 mfilt = 10000
 nhtfrq = 1
 fincl1 = 'PRECT'
 scm_iop_srf_prop = $do_iop_srf_prop
 iop_nudge_tq = $do_scm_relaxation
 iradlw = 1
 iradsw = 1
 precip_off = $do_turnoff_precip
 scmlat = $lat
 scmlon = $lon
EOF

# CAM namelist options to match E3SMv1 settings
#  Future implementations this block will not be needed
#  Match settings in compset 2000_cam5_av1c-04p2
cat <<EOF >> user_nl_eam
! parameters need to be reset for v3
 use_hetfrz_classnuc = .true.
 microp_aero_wsub_scheme = 1
 convproc_do_aer = .true.
 demott_ice_nuc = .true.
 liqcf_fix = .true.
 regen_fix = .true.
 resus_fix = .true.
 mam_amicphys_optaa = 1
 fix_g1_err_ndrop = .true.
 ssalt_tuning = .true.
 use_rad_dt_cosz = .true.
 ice_sed_ai = 982.1686
 cldfrc_dp1 = 0.096881876D0
 clubb_ice_deep = 14.e-6
 clubb_ice_sh = 5e-05
 clubb_liq_deep = 8e-06
 clubb_liq_sh = 1e-05
 clubb_C2rt = 1.3158405D0
 zmconv_c0_lnd = 0.0036946894
 zmconv_c0_ocn = 0.0043882879
 zmconv_dmpdz = -1.11258719e-03
 zmconv_ke = 6.49508207E-06
 zmconv_alfa = 0.38593638D0
 zmconv_tau = 3917.1541
 effgw_oro = 0.18356791
 linoz_psc_T = 197.5
 seasalt_emis_scale = 0.55D0
 dust_emis_fact = 13.8D0
 clubb_gamma_coef = 0.12091461
 clubb_gamma_coefb = 0.28D0
 clubb_gamma_coefc = 1.2
 clubb_mu = 0.0005
 clubb_C8 = 4.1747675
 clubb_beta = 1.8715802
 clubb_C11 = 0.70
 clubb_C11b = 0.20
 clubb_C11c = 0.85
 clubb_C1b = 2.8
 clubb_C1c = 0.75
 clubb_C6rtb = 7.50
 clubb_C6rtc = 0.50
 clubb_C6thlb = 7.50
 clubb_C6thlc = 0.50
 clubb_c_K10h = 0.35
 clubb_tk1 = 268.15D0
 clubb_wpxp_L_thresh = 100.0D0
 clubb_use_sgv = .true.
 cldfrc2m_rhmaxi = 1.0991683D0
 clubb_c_K10 = 1.040858
 effgw_beres = 0.35
 do_tms = .false.
 so4_sz_thresh_icenuc = 0.080e-6
 microp_aero_wsubmin = 0.001D0
 n_so4_monolayers_pcage = 8.0D0

 zmconv_tiedke_add = 0.8D0
 zmconv_tp_fac = 2.0D0
 zmconv_trigdcape_ull = .true.
 zmconv_cape_cin = 1
 zmconv_mx_bot_lyr_adj = 1

 taubgnd = 2.50000000D-03
 clubb_C1 = 4.3882235
 clubb_C6rt = 5.4617236
 raytau0 = 5D0
 se_ftype = 2
 clubb_C14 = 1.3D0
 gw_convect_hcf = 10.0
 sscav_tuning = .false.
 relvar_fix = .true.
 sol_factb_interstitial = 0.1D0
 sol_facti_cloud_borne = 1.0D0
 sol_factic_interstitial = 0.4D0
 rad_climate = 'A:Q:H2O', 'N:O2:O2', 'N:CO2:CO2',
        'N:ozone:O3', 'N:N2O:N2O', 'N:CH4:CH4',
        'N:CFC11:CFC11', 'N:CFC12:CFC12',
        'M:mam3_mode1:/Users/yunlong/projects/e3sm/inputdata/atm/cam/physprops/mam3_mode1_rrtmg_c110318.nc',
        'M:mam3_mode2:/Users/yunlong/projects/e3sm/inputdata/atm/cam/physprops/mam3_mode2_rrtmg_c110318.nc',
        'M:mam3_mode3:/Users/yunlong/projects/e3sm/inputdata/atm/cam/physprops/mam3_mode3_rrtmg_c110318.nc'
EOF

# if constant droplet was selected then modify name list to reflect this
if ($init_aero_type == cons_droplet) then

cat <<EOF >> user_nl_eam
  micro_do_nccons = .true.
  micro_do_nicons = .true.
  micro_nccons = $micro_nccons_val
  micro_nicons = $micro_nicons_val
EOF

endif

# if prescribed or observed aerosols set then need to put in settings for prescribed aerosol model
if ($init_aero_type == prescribed ||$init_aero_type == observed) then

cat <<EOF >> user_nl_eam
  use_hetfrz_classnuc = .false.
  aerodep_flx_type = 'CYCLICAL'
  aerodep_flx_datapath = '$input_data_dir/$presc_aero_path'
  aerodep_flx_file = '$presc_aero_file'
  aerodep_flx_cycle_yr = 01
  prescribed_aero_type = 'CYCLICAL'
  prescribed_aero_datapath='$input_data_dir/$presc_aero_path'
  prescribed_aero_file='$presc_aero_file'
  prescribed_aero_cycle_yr = 01
EOF

endif

# if observed aerosols then set flag
if ($init_aero_type == observed) then

cat <<EOF >> user_nl_eam
  scm_observed_aero = .true.
EOF

endif

# avoid the monthly cice file from writing as this
#   appears to be currently broken for SCM
cat <<EOF >> user_nl_cice
  histfreq='y','x','x','x','x'
EOF

# Use CLM4.5.  Currently need to point to the correct file for Eulerian
#  dy-core (this will be fixed in upcoming PR)
set ELM_CONFIG_OPTS="-phys elm"
./xmlchange ELM_CONFIG_OPTS="$ELM_CONFIG_OPTS"

# Modify the run start and duration parameters for the desired case
  ./xmlchange RUN_STARTDATE="$startdate",START_TOD="$start_in_sec",STOP_OPTION="$stop_option",STOP_N="$stop_n"
  ./xmlchange CALENDAR="GREGORIAN"

# Modify the latitude and longitude for the particular case
  ./xmlchange PTS_MODE="TRUE",PTS_LAT="$lat",PTS_LON="$lon"
  ./xmlchange MASK_GRID="USGS"

  ./case.setup

# Don't want to write restarts as this appears to be broken for
#  CICE model in SCM.  For now set this to a high value to avoid
  ./xmlchange PIO_TYPENAME="netcdf"
  ./xmlchange REST_N=30000

# Modify some parameters for CICE to make it SCM compatible
  ./xmlchange CICE_AUTO_DECOMP="FALSE"
  ./xmlchange CICE_DECOMPTYPE="blkrobin"
  ./xmlchange --id CICE_BLCKX --val 1
  ./xmlchange --id CICE_BLCKY --val 1
  ./xmlchange --id CICE_MXBLCKS --val 1
  ./xmlchange CICE_CONFIG_OPTS="-nodecomp -maxblocks 1 -nx 1 -ny 1"

# Reuse a pre-built executable from the baseline case; skip rebuilding the model.
  set template_exe = ""
  if ($?TEMPLATE_EXE_MAC) then
    if ("$TEMPLATE_EXE_MAC" != "") set template_exe = "$TEMPLATE_EXE_MAC"
  endif
  if ("$template_exe" == "") then
    if ($?TEMPLATE_EXE) then
      if ("$TEMPLATE_EXE" != "") set template_exe = "$TEMPLATE_EXE"
    endif
  endif
  if ("$template_exe" == "") then
    echo "ERROR: set TEMPLATE_EXE_MAC or TEMPLATE_EXE to a compatible pre-built e3sm.exe"
    exit 1
  endif
  if (! -e "$template_exe") then
    echo "ERROR: template executable not found: $template_exe"
    exit 1
  endif
  mkdir -p $case_build_dir
  cp "$template_exe" $case_build_dir/e3sm.exe
  if (-e /opt/homebrew/opt/openblas/lib/libopenblas.0.dylib) then
    install_name_tool -change @rpath/libopenblas.0.dylib /opt/homebrew/opt/openblas/lib/libopenblas.0.dylib $case_build_dir/e3sm.exe
  endif
  ./xmlchange BUILD_COMPLETE=TRUE

# Submit case to queue if set, else submit
#   via the case.run script
  if ($submit_to_queue == true) then
    ./case.submit
  else
    ./case.submit --no-batch
  endif

  exit
