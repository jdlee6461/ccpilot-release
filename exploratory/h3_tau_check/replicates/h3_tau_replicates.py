"""EXPLORATORY (instruction 06 §1): thresholds of the 100 bootstrap replicates of the frozen H3 sensitivity analysis.

    python exploratory/h3_tau_check/replicates/h3_tau_replicates.py run --start 0 --end 20     # replicates [start, end)
    python exploratory/h3_tau_check/replicates/h3_tau_replicates.py summary

Read only: confirm2_h3_sensitivity.py and ccpilot/ are imported unchanged (as at 6758bce). The blocks, the taxi-cluster
codes and the replicate weights are built exactly as in confirm2_h3_sensitivity.main (runs at the sensitivity target,
taxi map work/porto_cctv_confirm2/taxi_map.parquet, default_rng(bootstrap seed + 3).multinomial over the taxi
clusters, B from configs/confirm2_analysis.yaml); replicate b refits H3 per block with wqr_tau as replicate() does.
  run      per replicate: work/h3_tau_check/replicates/rep_<b>.npz (tau of each block, the replicate's h3_cost_refit
           computed as in confirm2_h3_sensitivity.py:101)
  summary  replicates_tau.csv: per replicate, frozen and reproduced h3_cost_refit (h3_sensitivity_replicates.csv),
           bitwise equality, and per block hops with weight > 0, tau min / max, hops with tau > 1.5 and tau > 2, hops
           with negative lookup cost (all hops of the block, as the cost w @ cost_per_hop(tau) uses them);
           manifest.csv: cached files, sha256, commit
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "8"          # as in the frozen script (plan §11.1-6), set before numpy is imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

import argparse  # noqa: E402
import hashlib  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from confirm2_analysis import ANALYSIS, ATTRS, load_block  # noqa: E402
from confirm2_h3_sensitivity import wqr_tau  # noqa: E402
from ccpilot.multigroup import _design  # noqa: E402

RUNS = Path(ROOT) / "results/porto_cctv_confirm2/runs"
FROZEN = Path(ROOT) / "results/porto_cctv_confirm2/h3_sensitivity/h3_sensitivity_replicates.csv"
TAXI = Path(ROOT) / "work/porto_cctv_confirm2/taxi_map.parquet"
CACHE = Path(ROOT) / "work/h3_tau_check/replicates"
OUT = Path(ROOT) / "exploratory/h3_tau_check/replicates"
BLOCKS = ["block1", "block2"]


def setup():
    """blocks, cluster codes and replicate weights as in confirm2_h3_sensitivity.main (lines 70-87)."""
    A = yaml.safe_load(open(Path(ROOT) / ANALYSIS)); S = A["h3_sensitivity"]
    t = float(S["target"]); B = int(S["B"]); alpha = 1 - t
    pred = A["predictor"]; methods = A["proposed"] + A["comparators_main"]
    blocks, taxis = [], []
    for name in BLOCKS:
        dirs = sorted(str(d) for d in (RUNS / name).glob(f"t{int(round(t * 1000)):04d}/s*") if d.is_dir())
        b = load_block(name, dirs, TAXI, None, pred, methods)
        H0 = b["H0"]
        X = _design([H0[ATTRS]], ATTRS)[0]
        y = np.log(np.maximum(b["score"], 1e-8))
        blocks.append({"name": name, "X": X, "y": y, "lk": b["lk"], "taxi": b["taxi"]})
        taxis.append(b["taxi"])
    ut = pd.Index(np.unique(np.concatenate(taxis)))
    for b in blocks:
        b["code"] = ut.get_indexer(b["taxi"])
    C = len(ut)
    rng = np.random.default_rng(A["seeds"]["bootstrap"] + 3)
    W = rng.multinomial(C, np.full(C, 1.0 / C), size=B).astype(float)
    return blocks, W, alpha


def run(a):
    blocks, W, alpha = setup()
    CACHE.mkdir(parents=True, exist_ok=True)
    for bi in range(a.start, min(a.end, len(W))):
        t0 = time.time()
        out, taus = [], {}
        for b in blocks:                                        # replicate() of confirm2_h3_sensitivity.py:57-64
            w = W[bi][b["code"]]
            tau = wqr_tau(b["X"], b["y"], w, alpha)
            out.append((float(w @ b["lk"].cost_per_hop(tau)), float(w.sum())))
            taus[b["name"]] = tau
        refit = sum(c for c, _ in out) / sum(n for _, n in out)  # confirm2_h3_sensitivity.py:101
        np.savez(CACHE / f"rep_{bi:03d}.npz", h3_cost_refit=refit, seconds=time.time() - t0,
                 **{f"tau_{k}": v for k, v in taus.items()})
        print(bi, refit, {k: float(v.max()) for k, v in taus.items()}, round(time.time() - t0), flush=True)


def summary(a):
    blocks, W, _ = setup()
    F = pd.read_csv(FROZEN, float_precision="round_trip").set_index("replicate").h3_cost_refit
    rows = []
    for bi in range(len(W)):
        z = np.load(CACHE / f"rep_{bi:03d}.npz")
        v = float(z["h3_cost_refit"])
        r = {"replicate": bi, "h3_cost_refit_frozen": float(F.loc[bi]), "h3_cost_refit_reproduced": v,
             "bitwise_equal": bool(F.loc[bi] == v)}
        for b in blocks:
            tau = z[f"tau_{b['name']}"]; w = W[bi][b["code"]]; n = b["name"]
            r.update({f"{n}_hops": len(tau), f"{n}_hops_weight_gt0": int((w > 0).sum()), f"{n}_tau_min": float(tau.min()),
                      f"{n}_tau_max": float(tau.max()), f"{n}_n_tau_gt_1p5": int((tau > 1.5).sum()),
                      f"{n}_n_tau_gt_2": int((tau > 2).sum()), f"{n}_n_cost_neg": int((b["lk"].cost_per_hop(tau) < 0).sum())})
        rows.append(r)
    R = pd.DataFrame(rows); R.to_csv(OUT / "replicates_tau.csv", index=False)
    print("replicates", len(R), "bitwise equal", int(R.bitwise_equal.sum()))
    for n in BLOCKS:
        print(n, "tau max", R[f"{n}_tau_max"].max(), "tau min", R[f"{n}_tau_min"].min(), ">1.5", R[f"{n}_n_tau_gt_1p5"].sum(),
              ">2", R[f"{n}_n_tau_gt_2"].sum(), "neg", R[f"{n}_n_cost_neg"].sum())
    commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    pd.DataFrame([{"file": str(f.relative_to(ROOT)), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "commit": commit}
                  for f in sorted(CACHE.glob("rep_*.npz"))]).to_csv(OUT / "manifest.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["run", "summary"])
    ap.add_argument("--start", type=int, default=0); ap.add_argument("--end", type=int, default=100)
    a = ap.parse_args()
    {"run": run, "summary": summary}[a.step](a)


if __name__ == "__main__":
    main()
