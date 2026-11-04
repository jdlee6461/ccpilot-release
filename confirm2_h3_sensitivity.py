"""confirm2 H3 sensitivity (plan §6.3): cost ratio to H3 with H3 refitted in every bootstrap replicate.

    python confirm2_h3_sensitivity.py --block expl1 work/trial_expl1/t0950_s0 work/trial_expl1/t0950_s1 \
        --taxi-map expl1 work/porto_cctv/taxi_map.parquet --out results/.../h3_sensitivity --workers 6

Settings from configs/confirm2_analysis.yaml `h3_sensitivity` (target 0.95, blocks combined, taxi clusters, B = 100).
One or more blocks (each: name + the runs of that block at the target, all seeds); taxi clusters are resampled jointly
over the blocks (the same TAXI_ID in both blocks is one cluster). In every replicate H3 is refitted per block on the
resampled hops: the qr_group_taus design and LP (level 1 - t, highs-ipm) with each hop weighted by its cluster's
multiplicity (= duplicating the hops; hops with weight 0 are dropped). Ratio = (seed mean of the method's mean cost over
both blocks) / (mean H3 cost over both blocks), both weighted by the replicate. The interval with H3 fixed at the
full-sample fit, computed on the same replicates, is reported beside it. Percentile 95% interval.
Output: h3_sensitivity.csv, h3_sensitivity_replicates.csv, h3_sensitivity_log.json
"""
import argparse
import json
import os
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "8"          # plan §11.1-6 (rev 72): thread-count limit
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from scipy.optimize import linprog

from confirm2_analysis import ANALYSIS, ATTRS, load_block
from ccpilot.multigroup import _design
from ccpilot.predictors import TAU_MIN

_B = {}


def wqr_tau(X, y, w, alpha):
    keep = w > 0
    Xk, yk, wk = X[keep], y[keep], w[keep]
    n, p = Xk.shape
    c = np.r_[np.zeros(p), alpha * wk, (1 - alpha) * wk]
    A = sparse.hstack([sparse.csr_matrix(Xk), sparse.identity(n, format="csr"), -sparse.identity(n, format="csr")], format="csr")
    res = linprog(c, A_eq=A, b_eq=yk, bounds=[(None, None)] * p + [(0, None)] * (2 * n), method="highs-ipm")
    if not res.success:
        raise RuntimeError(res.message)
    return np.maximum(np.exp(X @ res.x[:p]), TAU_MIN)


def _init(blocks, alpha):
    _B["blocks"] = blocks; _B["alpha"] = alpha


def replicate(wtaxi):
    num = den = 0.0
    out = []
    for b in _B["blocks"]:
        w = wtaxi[b["code"]]
        tau = wqr_tau(b["X"], b["y"], w, _B["alpha"])
        out.append((float(w @ b["lk"].cost_per_hop(tau)), float(w.sum())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", nargs="+", action="append", required=True, help="name run_dir [run_dir ...]")
    ap.add_argument("--taxi-map", nargs=2, action="append", required=True, help="name taxi_map.parquet")
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--B", type=int)
    a = ap.parse_args()
    A = yaml.safe_load(open(ANALYSIS)); S = A["h3_sensitivity"]
    t = float(S["target"]); B = a.B or int(S["B"]); alpha = 1 - t
    pred = A["predictor"]; methods = A["proposed"] + A["comparators_main"]
    tmaps = dict(a.taxi_map)
    blocks, taxis = [], []
    for spec in a.block:
        name, dirs = spec[0], spec[1:]
        b = load_block(name, dirs, tmaps[name], None, pred, methods)
        assert all(abs(t_ - t) < 1e-9 for t_, _ in b["runs"]), "runs must be at the sensitivity target"
        H0 = b["H0"]
        X = _design([H0[ATTRS]], ATTRS)[0]
        y = np.log(np.maximum(b["score"], 1e-8))
        mcost = {m: np.mean([r["cost"][m] for r in b["runs"].values()], axis=0) for m in methods}     # seed mean per hop
        blocks.append({"name": name, "X": X, "y": y, "lk": b["lk"], "taxi": b["taxi"], "mcost": mcost})
        taxis.append(b["taxi"])
    ut = pd.Index(np.unique(np.concatenate(taxis)))
    for b in blocks:
        b["code"] = ut.get_indexer(b["taxi"])
    C = len(ut)
    rng = np.random.default_rng(A["seeds"]["bootstrap"] + 3)
    W = rng.multinomial(C, np.full(C, 1.0 / C), size=B).astype(float)
    t0 = time.time()
    tau_full = [wqr_tau(b["X"], b["y"], np.ones(len(b["y"])), alpha) for b in blocks]
    t_full = time.time() - t0
    h3_fixed_cost = [b["lk"].cost_per_hop(tf) for b, tf in zip(blocks, tau_full)]
    lite = [{"X": b["X"], "y": b["y"], "lk": b["lk"], "code": b["code"]} for b in blocks]
    t1 = time.time()
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(lite, alpha)) as ex:
        reps = list(ex.map(replicate, list(W)))
    t_boot = time.time() - t1
    rows, rep_rows = [], []
    h3_refit = np.array([sum(c for c, _ in r) / sum(n for _, n in r) for r in reps])
    for bi in range(B):
        rep_rows.append({"replicate": bi, "h3_cost_refit": h3_refit[bi]})
    for m in methods:
        pt_num = sum(b["mcost"][m].sum() for b in blocks); pt_n = sum(len(b["y"]) for b in blocks)
        pt_fixed = (pt_num / pt_n) / (sum(c.sum() for c in h3_fixed_cost) / pt_n)
        rr, rf = [], []
        for bi in range(B):
            wsum = sum(W[bi][b["code"]].sum() for b in blocks)
            mc = sum(W[bi][b["code"]] @ b["mcost"][m] for b in blocks) / wsum
            fixed = sum(W[bi][b["code"]] @ c for b, c in zip(blocks, h3_fixed_cost)) / wsum
            rr.append(mc / h3_refit[bi]); rf.append(mc / fixed)
        lo_r, hi_r = np.percentile(rr, [2.5, 97.5]); lo_f, hi_f = np.percentile(rf, [2.5, 97.5])
        rows.append({"target": t, "method": m, "blocks": "+".join(b["name"] for b in blocks), "cluster": "taxi", "B": B,
                     "point_fixed_fit": pt_fixed, "lo_refit": lo_r, "hi_refit": hi_r, "lo_fixed": lo_f, "hi_fixed": hi_f,
                     "note": "ratio = seed-mean method cost / H3 cost; refit = H3 refitted per replicate; fixed = full-sample H3"})
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "h3_sensitivity.csv", index=False)
    pd.DataFrame(rep_rows).to_csv(out / "h3_sensitivity_replicates.csv", index=False)
    log = {"target": t, "B": B, "taxi_clusters": C, "workers": a.workers, "hops": int(sum(len(b["y"]) for b in blocks)),
           "full_fit_seconds": t_full, "bootstrap_seconds": t_boot, "seconds_per_replicate_per_worker": t_boot * a.workers / B}
    json.dump(log, open(out / "h3_sensitivity_log.json", "w"), indent=1)
    print(json.dumps(log, indent=1)); print(pd.DataFrame(rows).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
