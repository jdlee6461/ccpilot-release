"""POST HOC (external review, plan results/porto_cctv_confirm2_posthoc/review/REVIEW_PLAN.md): shared helpers.

Reads the frozen confirm2 runs (results/porto_cctv_confirm2/runs/<block>/<tXXXX>/s<k>/, read only) and the confirm2 work
directory (work/porto_cctv_confirm2/, read only). Intermediate files go to work/review_cache/ (git-ignored); results to
results/porto_cctv_confirm2_posthoc/review/.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

RUNS = Path("results/porto_cctv_confirm2/runs")
OUT = Path("results/porto_cctv_confirm2_posthoc/review")
CACHE = Path("work/review_cache")
BLOCKS = ["block1", "block2"]
TARGETS = [0.90, 0.93, 0.95, 0.97, 0.98]
SEEDS = [0, 1, 2, 3, 4]
PRIMARY = "src_zone_hour_speed"
PREDICTORS = ["src", "src_zone", "src_zone_hour", "src_zone_speed", "src_zone_hour_speed"]
DIMS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]   # multigroup.dims (25 groups with 'all')
CAL_COLS = ["tr_id", "trip_id", "t_exit", "t_arrive", "hop", "chain"] + DIMS


def run_dir(block, t, s):
    return RUNS / block / f"t{int(round(t * 1000)):04d}" / f"s{s}"


def run_cfg(block, t=0.95, s=0):
    """effective configuration of a stored run (run_config.yaml written by the run)."""
    return yaml.safe_load(open(run_dir(block, t, s) / "run_config.yaml", encoding="utf-8"))


def alpha_of(cfg):
    return 1.0 - cfg["eval"]["target_recall"]          # same expression as ccpilot/evaluate.py


def load_cal(block):
    """calibration hops (time order as in evaluate.run) with group columns and s_cal of the 5 predictors (P0 output)."""
    return pd.read_parquet(CACHE / block / "cal.parquet")


def load_hits(block, t, s, columns=None):
    return pd.read_parquet(run_dir(block, t, s) / "hits.parquet", columns=columns)


def threads(n=1):
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(k, str(n))


def write_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, default=str)
