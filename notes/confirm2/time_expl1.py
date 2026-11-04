"""confirm2 precheck item 7: wall time of one full evaluation on EXPLORATORY period 1 (configs/porto_cctv.yaml).

    python notes/confirm2/time_expl1.py

One evaluation seed (0), one target (0.95), all methods and predictors of the configuration, as run_pilot.py --stage eval.
The configuration is copied in memory; output goes to work/precheck_confirm2_timing/ (git-ignored) so that the committed
exploratory results are not overwritten. Nothing is run on the confirm2 candidate period.
Writes results/precheck_confirm2/timing_expl1.csv.
"""
import copy
import json
import platform
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ccpilot import evaluate  # noqa: E402
from ccpilot.posthoc import load_config  # noqa: E402


def main():
    cfg = copy.deepcopy(load_config("configs/porto_cctv.yaml"))
    cfg["out_dir"] = "work/precheck_confirm2_timing"
    cfg["eval"]["seed"] = 0
    cfg["eval"]["target_recall"] = 0.95
    w = Path(cfg["work_dir"])
    t0 = time.time()
    trans = pd.read_parquet(w / "transitions.parquet"); truth = pd.read_parquet(w / "truth.parquet")
    cams = pd.read_csv(w / "cameras.csv"); n_bins = json.load(open(w / "meta.json"))["n_bins"]
    t1 = time.time()
    res, _, _ = evaluate.run(cfg, trans, truth, cams, n_bins, cfg["out_dir"])
    t2 = time.time()
    n_test = int(res.groupby("segment").n.first().sum())
    methods = sorted(set(res.method))
    out = pd.DataFrame([{"period": "exploratory 1 (porto_cctv.yaml)", "seed": 0, "target": 0.95,
                         "load_s": t1 - t0, "eval_s": t2 - t1, "test_hops": n_test,
                         "n_predictors": res.predictor.nunique(), "n_method_rows": len(methods),
                         "methods": ";".join(methods), "host": platform.node(), "python": platform.python_version()}])
    Path("results/precheck_confirm2").mkdir(parents=True, exist_ok=True)
    out.to_csv("results/precheck_confirm2/timing_expl1.csv", index=False)
    print(out.T.to_string())


if __name__ == "__main__":
    main()
