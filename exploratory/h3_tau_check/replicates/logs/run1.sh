#!/bin/bash
cd /home/user/ccpilot
source ~/miniconda3/etc/profile.d/conda.sh && conda activate ccpilot
/usr/bin/time -v python exploratory/h3_tau_check/replicates/h3_tau_replicates.py run --start $1 --end $2 > work/h3_tau_check/replicates/logs/rep_$1_$2.log 2>&1
