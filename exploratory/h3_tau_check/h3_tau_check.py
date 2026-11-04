"""EXPLORATORY (instruction 05 §1): deterministic reproduction of the H3 thresholds of the frozen confirmation-2 analysis.

    python exploratory/h3_tau_check/h3_tau_check.py fit --block block1 --target 0.95    # one H3 fit (confirm2_analysis.py)
    python exploratory/h3_tau_check/h3_tau_check.py sens --block block1                # full-sample wqr_tau (h3_sensitivity)
    python exploratory/h3_tau_check/h3_tau_check.py summary

Read only: the frozen code is imported, not changed (confirm2_analysis.py, confirm2_h3_sensitivity.py and ccpilot/ as at
6758bce), the run outputs are read from results/porto_cctv_confirm2/runs/ with the frozen analysis command line (block
dirs, taxi map and attributes as in DEVIATIONS.md D5). Per-hop thresholds are cached in work/h3_tau_check/ (git-ignored).
  fit      tau3 = qr_group_taus(...)[0] with the arguments of confirm2_analysis.py:465 (level 1 - t, all hops of the
           block, highs-ipm, seed 0); the fit takes the block's hops and stored scores only, not the method runs
  sens     tau = wqr_tau(X, y, 1, 1 - t) of confirm2_h3_sensitivity.py:89 (t = h3_sensitivity target)
  summary  reproduce_hindsight.csv  H3 cost_mean and recall_all (hindsight.csv) and the H3 ratios (cost_ratios.csv),
                                    frozen value, reproduced value, bitwise equality
           reproduce_sensitivity.csv  point_fixed_fit (h3_sensitivity.csv), frozen, reproduced, bitwise equality
           tau_table.csv            per source, block and target: hops, tau max, hops with tau > 1.5 and tau > 2,
                                    hops with negative lookup cost; read only when the reproduction is bitwise equal
           h3_capped.csv            only when a hop has tau > 2: H3 cost and ratios with min(tau, 1.5)
           manifest.csv             cached files, sha256, commit
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "8"          # as in the frozen scripts (plan §11.1-6), set before numpy is imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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
from ccpilot.multigroup import _design, qr_group_taus  # noqa: E402

RUNS = Path(ROOT) / "results/porto_cctv_confirm2/runs"
FROZEN = Path(ROOT) / "results/porto_cctv_confirm2"
WORK = Path(ROOT) / "work/porto_cctv_confirm2"
CACHE = Path(ROOT) / "work/h3_tau_check"
OUT = Path(ROOT) / "exploratory/h3_tau_check"
BLOCKS = ["block1", "block2"]
CAP = 1.5


def cfg():
    A = yaml.safe_load(open(Path(ROOT) / ANALYSIS))
    return A, A["predictor"], A["proposed"] + A["comparators_main"] + A.get("comparators_other", [])


def block(name, target=None):
    """load_block as the frozen command line calls it: all runs of the block (or the runs at one target)."""
    A, pred, methods = cfg()
    pat = f"t{int(round(target * 1000)):04d}/s*" if target is not None else "t*/s*"
    dirs = sorted(str(d) for d in (RUNS / name).glob(pat) if d.is_dir())
    attr = WORK / f"attr_{name}.parquet" if target is None else None
    if target is not None:
        methods = A["proposed"] + A["comparators_main"]          # confirm2_h3_sensitivity.py:72
    return load_block(name, dirs, WORK / "taxi_map.parquet", attr, pred, methods), methods


def fit(a):
    b, _ = block(a.block)
    targets = sorted({t for t, _ in b["runs"]})
    t = [x for x in targets if abs(x - a.target) < 1e-9][0]
    nbk = len(b["H0"])
    t0 = time.time()
    tau3, beta = qr_group_taus(b["H0"][ATTRS], b["score"], b["H0"][ATTRS], ATTRS, 1 - t, max_n=nbk + 1, seed=0,
                               lp_method="highs-ipm")
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE / f"tau3_{a.block}_t{int(round(t * 1000)):04d}.npz", tau=tau3, beta=beta, target=t,
             seconds=time.time() - t0)
    print(a.block, t, nbk, float(tau3.max()), time.time() - t0)


def sens(a):
    A, _, _ = cfg()
    t = float(A["h3_sensitivity"]["target"])
    b, _ = block(a.block, t)
    X = _design([b["H0"][ATTRS]], ATTRS)[0]
    y = np.log(np.maximum(b["score"], 1e-8))
    t0 = time.time()
    tau = wqr_tau(X, y, np.ones(len(y)), 1 - t)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE / f"wqr_{a.block}_t{int(round(t * 1000)):04d}.npz", tau=tau, target=t, seconds=time.time() - t0)
    print(a.block, t, len(y), float(tau.max()), time.time() - t0)


def rt(path):
    return pd.read_csv(path, float_precision="round_trip")


def tau_row(src, name, t, tau, lk):
    c = lk.cost_per_hop(tau)
    return {"source": src, "block": name, "target": t, "seeds": "all (the fit does not read the method runs)",
            "hops": len(tau), "tau_min": float(tau.min()), "tau_max": float(tau.max()),
            "n_tau_gt_1p5": int((tau > 1.5).sum()), "n_tau_gt_2": int((tau > 2).sum()), "n_cost_neg": int((c < 0).sum()),
            "lookup_p_max": float(max(lk.glob[lk.start[i]:lk.end[i]].max() - 2.0 * i for i in range(len(lk.start))))}


def summary(a):
    A, pred, methods = cfg()
    B = {n: block(n)[0] for n in BLOCKS}
    targets = sorted({t for t, _ in B["block1"]["runs"]}); seeds = sorted({s for _, s in B["block1"]["runs"]})
    tau = {(n, t): np.load(CACHE / f"tau3_{n}_t{int(round(t * 1000)):04d}.npz")["tau"] for n in BLOCKS for t in targets}
    HS = rt(FROZEN / "analysis/hindsight.csv"); RA = rt(FROZEN / "analysis/cost_ratios.csv")
    scopes = {"combined": BLOCKS, **{n: [n] for n in BLOCKS}}
    rows = []

    def h3(sc, t, cap):
        tb = {n: np.minimum(tau[(n, t)], CAP) if cap else tau[(n, t)] for n in scopes[sc]}
        hits = np.concatenate([B[n]["score"] >= tb[n] for n in scopes[sc]]).astype(float)
        cost = np.concatenate([B[n]["lk"].cost_per_hop(tb[n]) for n in scopes[sc]])
        return hits.mean(), cost.mean()

    def ratios(sc, t, hp):
        out = {}
        for m in methods:
            mpt = [np.concatenate([B[n]["runs"][(t, s)]["cost"][m] for n in scopes[sc]]).mean() for s in seeds]
            out[m] = np.mean([x / hp for x in mpt])
        return out
    for sc in scopes:
        for t in targets:
            r_, c_ = h3(sc, t, False)
            f = HS[(HS.scope == sc) & (HS.target == t) & (HS.reference == "H3")].iloc[0]
            rows += [{"file": "hindsight.csv", "scope": sc, "target": t, "quantity": q, "method": "", "frozen": fv,
                      "reproduced": v, "bitwise_equal": bool(fv == v)}
                     for q, fv, v in (("cost_mean", f.cost_mean, c_), ("recall_all", f.recall_all, r_))]
            for m, v in ratios(sc, t, c_).items():
                fv = RA[(RA.scope == sc) & (RA.target == t) & (RA.reference == "H3") & (RA.method == m)].ratio.iloc[0]
                rows.append({"file": "cost_ratios.csv", "scope": sc, "target": t, "quantity": "ratio_H3", "method": m,
                             "frozen": fv, "reproduced": v, "bitwise_equal": bool(fv == v)})
    R = pd.DataFrame(rows); R.to_csv(OUT / "reproduce_hindsight.csv", index=False)
    print("hindsight/cost_ratios rows", len(R), "bitwise equal", int(R.bitwise_equal.sum()))

    # h3_sensitivity point_fixed_fit (confirm2_h3_sensitivity.py:104-106)
    ts = float(A["h3_sensitivity"]["target"])
    S = {n: block(n, ts) for n in BLOCKS}
    wq = {n: np.load(CACHE / f"wqr_{n}_t{int(round(ts * 1000)):04d}.npz")["tau"] for n in BLOCKS}
    HSN = rt(FROZEN / "h3_sensitivity/h3_sensitivity.csv")
    srows = []
    fixed = [S[n][0]["lk"].cost_per_hop(wq[n]) for n in BLOCKS]
    pt_n = sum(len(S[n][0]["score"]) for n in BLOCKS)
    for m in S["block1"][1]:
        mc = {n: np.mean([r["cost"][m] for r in S[n][0]["runs"].values()], axis=0) for n in BLOCKS}
        v = (sum(mc[n].sum() for n in BLOCKS) / pt_n) / (sum(c.sum() for c in fixed) / pt_n)
        fv = HSN[HSN.method == m].point_fixed_fit.iloc[0]
        srows.append({"file": "h3_sensitivity.csv", "target": ts, "quantity": "point_fixed_fit", "method": m, "frozen": fv,
                      "reproduced": v, "bitwise_equal": bool(fv == v)})
    SR = pd.DataFrame(srows); SR.to_csv(OUT / "reproduce_sensitivity.csv", index=False)
    print("h3_sensitivity rows", len(SR), "bitwise equal", int(SR.bitwise_equal.sum()))

    if not (R.bitwise_equal.all() and SR.bitwise_equal.all()):
        print("reproduction not bitwise equal: thresholds not read"); return
    T = [tau_row("confirm2_analysis H3 tau3", n, t, tau[(n, t)], B[n]["lk"]) for n in BLOCKS for t in targets]
    T += [tau_row("h3_sensitivity wqr_tau (full sample)", n, ts, wq[n], S[n][0]["lk"]) for n in BLOCKS]
    T = pd.DataFrame(T); T.to_csv(OUT / "tau_table.csv", index=False)
    print(T.drop(columns="seeds").to_string(index=False))
    if T.n_tau_gt_2.sum() > 0:
        cr = []
        for sc in scopes:
            for t in targets:
                r0, c0 = h3(sc, t, False); r1, c1 = h3(sc, t, True)
                q0, q1 = ratios(sc, t, c0), ratios(sc, t, c1)
                cr += [{"scope": sc, "target": t, "method": m, "h3_cost_mean_frozen_lookup": c0, "h3_cost_mean_capped": c1,
                        "ratio_frozen_lookup": q0[m], "ratio_capped": q1[m]} for m in methods]
        pd.DataFrame(cr).to_csv(OUT / "h3_capped.csv", index=False)
    commit = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    pd.DataFrame([{"file": str(f.relative_to(ROOT)), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "commit": commit}
                  for f in sorted(CACHE.glob("*.npz"))]).to_csv(OUT / "manifest.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["fit", "sens", "summary"])
    ap.add_argument("--block", choices=BLOCKS); ap.add_argument("--target", type=float)
    a = ap.parse_args()
    {"fit": fit, "sens": sens, "summary": summary}[a.step](a)


if __name__ == "__main__":
    main()
