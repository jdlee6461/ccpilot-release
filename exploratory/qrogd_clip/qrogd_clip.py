"""EXPLORATORY, POST HOC (instruction 12 §5(c)(d); verdict Shannon04 G8-3, G8-4): how often the qr_ogd group offsets
theta_G reach the clip bound in the confirmation-2 runs, and the per-group feedback counts T_G with 3 / (gamma T_G).

    python exploratory/qrogd_clip/qrogd_clip.py --run BLOCK T SEED     # one stored run (primary predictor)
    python exploratory/qrogd_clip/qrogd_clip.py --summary              # collect the 50 runs

Path of P0 (posthoc_review_p0.py check_qrogd, instruction 01 v02 §5): stored run configuration, P0 calibration cache
(work/review_cache/BLOCK/cal.parquet), base thresholds qr_group_taus (seed = evaluation seed), online correction with the
stored feedback mask and resolution times. Read only: ccpilot/ and the run outputs in results/porto_cctv_confirm2/runs/
are imported or read, not changed. Steps per run:
  1. tau = ccpilot.multigroup.qr_ogd_taus(...) as in P0; hits (s_test >= tau) must equal the stored hit column bit for bit
  2. the same loop, copied below (replay), also records theta_G; its thresholds must equal step 1 bit for bit
  3. only then the per-group counts are written
Per run and group (25 groups: 'all' + the levels of eval.multigroup.dims, names of ccpilot.multigroup.group_matrix):
  n_hops           evaluation hops in the group
  n_feedback       hops in the group with the feedback flag
  T_G              feedback outcomes applied to theta_G (resolved before the last query of the segment)
  bound_3_gT       clip / (gamma T_G)  (eq. qrogd-bound; clip = 3)
  n_upd_clipped    applied updates whose unclipped value lay outside [-clip, clip] (the clip acted)
  n_upd_at_bound   applied updates after which |theta_G| = clip
  n_query_at_bound evaluation hops of the group queried while |theta_G| = clip
  first_bound_t    t_exit of the first such query (empty if none); theta_final, theta_min, theta_max
Outputs: runs/clip_BLOCK_tTTTT_sS.csv and check_BLOCK_tTTTT_sS.json; summary: qrogd_clip.csv, checks.csv,
tg_bound.csv (25 groups x block1, block2, both: T_G seed mean at each target), manifest.csv.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import argparse  # noqa: E402
import hashlib  # noqa: E402
import heapq  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import posthoc_review_common as C  # noqa: E402

C.threads(1)                                   # as P0 (bitwise reproduction there was with one thread)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ccpilot.multigroup import group_matrix, qr_group_taus, qr_ogd_taus  # noqa: E402

OUT = Path("exploratory/qrogd_clip")
P = C.PRIMARY


def replay(base_tau, scores, t_exit, t_res_hit, t_res_miss, G_test, alpha, feedback_mask, gamma, clip):
    """copy of ccpilot.multigroup.qr_ogd_taus (same operations in the same order) that also records theta_G"""
    logb = np.log(np.maximum(base_tau, 1e-300))
    K = G_test.shape[1]
    theta = np.zeros(K)
    n = len(scores)
    taus = np.empty(n)
    heap = []
    T = np.zeros(K, int); n_clip = np.zeros(K, int); n_at = np.zeros(K, int); n_q = np.zeros(K, int)
    first = np.full(K, np.nan); tmin = np.zeros(K); tmax = np.zeros(K)
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            err = 1.0 if scores[j] < taus[j] else 0.0
            gi = np.flatnonzero(G_test[j])           # same elements, same order as theta[G_test[j]] in the library
            raw = theta[gi] - gamma * (err - alpha)
            theta[gi] = np.clip(raw, -clip, clip)
            T[gi] += 1
            n_clip[gi] += np.abs(raw) > clip
            n_at[gi] += np.abs(theta[gi]) == clip
            tmin[gi] = np.minimum(tmin[gi], theta[gi]); tmax[gi] = np.maximum(tmax[gi], theta[gi])
        taus[i] = np.exp(logb[i] + theta[G_test[i]].sum())
        gi = np.flatnonzero(G_test[i])
        hit_b = gi[np.abs(theta[gi]) == clip]
        n_q[hit_b] += 1
        first[hit_b] = np.where(np.isnan(first[hit_b]), t, first[hit_b])
        if feedback_mask[i]:
            heapq.heappush(heap, (t_res_hit[i] if scores[i] >= taus[i] else t_res_miss[i], i))
    return taus, dict(T_G=T, n_upd_clipped=n_clip, n_upd_at_bound=n_at, n_query_at_bound=n_q, first_bound_t=first,
                      theta_final=theta.copy(), theta_min=tmin, theta_max=tmax)


def tag(block, t, s):
    return f"{block}_t{int(round(t * 1000)):04d}_s{s}"


def run(block, t, s):
    t0 = time.time()
    cfg = C.run_cfg(block, t, s)
    ex = cfg["eval"]; mg = ex["multigroup"]; o = mg["qr_ogd"]; alpha = C.alpha_of(cfg)
    gamma, clip = o.get("gamma", 0.005), o.get("clip", 3.0)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    cal = C.load_cal(block)
    cols = ["t_exit", "feedback", "t_res_hit", "t_res_miss"] + C.DIMS
    H = C.load_hits(block, t, s)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    (_, G_test), names = group_matrix([cal, H[cols]], mg["dims"])
    s_cal = cal[f"score|{P}"].to_numpy(); s_test = H[f"score|{P}"].to_numpy()
    base, _ = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))
    tau = qr_ogd_taus(base, s_test, t_exit, th, tm, G_test, alpha, fb, gamma, clip)
    h = (s_test >= tau).astype(np.int8); st = H[f"hit|{P}|qr_ogd"].to_numpy().astype(np.int8)
    tau2, R = replay(base, s_test, t_exit, th, tm, G_test, alpha, fb, gamma, clip)
    chk = {"block": block, "target": t, "seed": s, "predictor": P, "gamma": gamma, "clip": clip, "n_hops": len(h),
           "hits_bitwise_stored": bool(np.array_equal(h, st)), "n_diff_stored": int((h != st).sum()),
           "replay_tau_bitwise": bool(np.array_equal(tau2, tau)),
           "sha256_hits_recomputed": hashlib.sha256(h.tobytes()).hexdigest(),
           "sha256_hits_stored": hashlib.sha256(st.tobytes()).hexdigest()}
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    if chk["hits_bitwise_stored"] and chk["replay_tau_bitwise"]:
        D = pd.DataFrame({"block": block, "target": t, "seed": s, "group": names,
                          "n_hops": G_test.sum(0), "n_feedback": G_test[fb].sum(0), **R})
        D["bound_3_gT"] = clip / (gamma * D.T_G)
        D.to_csv(OUT / "runs" / f"clip_{tag(block, t, s)}.csv", index=False)
    chk["seconds"] = round(time.time() - t0, 1)
    json.dump(chk, open(OUT / "runs" / f"check_{tag(block, t, s)}.json", "w"), indent=1)
    print(chk, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def summary():
    K = pd.DataFrame([json.load(open(f)) for f in sorted((OUT / "runs").glob("check_*.json"))])
    K.to_csv(OUT / "checks.csv", index=False)
    assert len(K) == 50 and K.hits_bitwise_stored.all() and K.replay_tau_bitwise.all(), K
    D = pd.concat([pd.read_csv(f) for f in sorted((OUT / "runs").glob("clip_*.csv"))], ignore_index=True)
    D.to_csv(OUT / "qrogd_clip.csv", index=False)
    gamma, clip = K["gamma"].iloc[0], K["clip"].iloc[0]
    m = D.groupby(["group", "target", "block"]).T_G.mean().unstack("block")
    m["both"] = m.block1 + m.block2
    B = m.reset_index().melt(id_vars=["group", "target"], var_name="scope", value_name="T_G_seed_mean")
    B["bound_3_gT"] = clip / (gamma * B.T_G_seed_mean)
    B.to_csv(OUT / "tg_bound.csv", index=False)
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "exploratory/qrogd_clip/qrogd_clip.py"],
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
    files = ["checks.csv", "qrogd_clip.csv", "tg_bound.csv"] + [f"runs/{f.name}" for f in sorted((OUT / "runs").iterdir())]
    pd.DataFrame({"file": [str(OUT / f) for f in files], "sha256": [sha(OUT / f) for f in files],
                  "script_commit": commit}).to_csv(OUT / "manifest.csv", index=False)
    print(K.groupby("block").agg(runs=("seed", "size"), seconds=("seconds", "max")).to_string())
    print(D.groupby("group")[["n_upd_clipped", "n_query_at_bound"]].sum().to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs=3)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if a.run:
        run(a.run[0], float(a.run[1]), int(a.run[2]))
    if a.summary:
        summary()


if __name__ == "__main__":
    main()
