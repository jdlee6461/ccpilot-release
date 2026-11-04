"""POST-HOC realised values of the qr_ogd inequality (paper eq. qrogd-bound) on the held-out period. Not pre-registered.

    python posthoc_qrogd_bound.py          # stored hop-level results only; no model is run

qr_ogd (ccpilot.multigroup.qr_ogd_taus) updates theta_G <- clip(theta_G - gamma (err_j - alpha), -c, c) for every group
G of a resolved feedback hop j. The update uses only err_j = 1 - hit_j, the feedback mask and the resolution time, so the
offsets are replayed exactly from the stored per-hop hits:
  - hops in the order of evaluate.run's tr_test (= order of hits.parquet), sorted by t_exit
  - feedback mask = np.random.default_rng(seed).random(n) < feedback_fraction (first draw of evaluate.run's rng)
  - resolution time: t_arrive if hit else t_exit + t_max (t_arrive joined from work/porto_cctv_confirm/transitions)
  - a feedback outcome is applied when the first later query arrives with t_exit >= resolution time (same heap loop)
Groups: 'all' + one per level of eval.multigroup.dims (25), as ccpilot.multigroup.group_matrix.
Reported per seed and group: T_G (applied updates), final theta_G, |theta_G|/(gamma T_G), bound c/(gamma T_G), realised
miss rate on the T_G feedback hops minus alpha, number of updates at which the clip bound, and the group recall.
Inputs: results/porto_cctv_confirm_posthoc/seeds_prereg25/seed_{0..4}/hits.parquet (evaluation seeds 0-4).
Output: results/porto_cctv_confirm_posthoc/qr_ogd_bound/qr_ogd_bound.csv
"""
import heapq
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.posthoc import load_config

ROOT = Path(__file__).resolve().parent
CFG = "configs/porto_cctv_confirm.yaml"            # read only
SEEDS = ROOT / "results/porto_cctv_confirm_posthoc/seeds_prereg25"
OUT = ROOT / "results/porto_cctv_confirm_posthoc/qr_ogd_bound"
COL = "hit|src_zone_hour_speed|qr_ogd"
SEGS = ["test_jun_a", "test_jun_b"]


def replay(err, t_exit, t_res, fb, G, alpha, gamma, clip):
    theta = np.zeros(G.shape[1]); T = np.zeros(G.shape[1], int); S = np.zeros(G.shape[1])
    n_clip = np.zeros(G.shape[1], int)
    heap = []
    for i in np.argsort(t_exit, kind="stable"):
        while heap and heap[0][0] <= t_exit[i]:
            _, j = heapq.heappop(heap)
            g = G[j]
            raw = theta[g] - gamma * (err[j] - alpha)
            n_clip[g] += (np.abs(raw) > clip)
            theta[g] = np.clip(raw, -clip, clip)
            T[g] += 1; S[g] += err[j] - alpha
        if fb[i]:
            heapq.heappush(heap, (t_res[i], i))
    return theta, T, S, n_clip


def main():
    cfg = load_config(CFG); ex = cfg["eval"]
    alpha = 1 - ex["target_recall"]; t_max = cfg["events"]["t_max_s"]
    o = ex["multigroup"]["qr_ogd"]; gamma, clip = o.get("gamma", 0.005), o.get("clip", 3.0)
    dims = ex["multigroup"]["dims"]; frac = ex["aci"]["feedback_fraction"]
    assert ex["aci"].get("feedback_delay", "realistic") != "none"
    arr = pd.read_parquet(Path(cfg["work_dir"]) / "transitions.parquet", columns=["tr_id", "t_arrive"]).set_index("tr_id").t_arrive
    rows = []
    for seed in range(5):
        H = pd.read_parquet(SEEDS / f"seed_{seed}/hits.parquet")
        t_exit = H.t_exit.to_numpy()
        assert np.all(np.diff(t_exit) >= 0)                       # tr_test order (sorted by t_exit)
        hit = H[COL].to_numpy().astype(float); err = 1 - hit
        t_res = np.where(hit == 1, arr.reindex(H.tr_id).to_numpy(), t_exit + t_max)
        assert not np.isnan(t_res).any()
        fb = np.random.default_rng(seed).random(len(H)) < frac
        names = ["all"]; cols = [np.ones(len(H), bool)]
        for d in dims:
            for v in sorted(H[d].unique()):
                names.append(f"{d}={v}"); cols.append(H[d].to_numpy() == v)
        G = np.column_stack(cols)
        assert G.shape[1] == 25
        theta, T, S, n_clip = replay(err, t_exit, t_res, fb, G, alpha, gamma, clip)
        for gi, g in enumerate(names):
            unclipped = n_clip[gi] == 0
            if unclipped:
                assert abs(S[gi] + theta[gi] / gamma) < 1e-6 * max(1, T[gi])     # telescoping identity
            rows.append({"seed": seed, "group": g, "n_eval": int(G[:, gi].sum()), "recall": hit[G[:, gi]].mean(),
                         "T_G": int(T[gi]), "theta": theta[gi], "abs_theta_over_gammaT": abs(theta[gi]) / (gamma * T[gi]),
                         "bound_c_over_gammaT": clip / (gamma * T[gi]), "miss_minus_alpha_fb": S[gi] / T[gi],
                         "theta_over_clip": abs(theta[gi]) / clip, "n_clip_events": int(n_clip[gi])})
    R = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "qr_ogd_bound.csv", index=False)
    R["kind"] = np.where(R.group == "hopkind=2", "re-acquired",
                         np.where(R.group.str.match(r"(speed_bin|entropy_bin|nn_bin)="), "quartile", "other"))
    pd.set_option("display.width", 250)
    print(R[R.group == "hopkind=2"].round(5).to_string(index=False))
    print(R.groupby(["kind"]).agg(T_min=("T_G", "min"), T_max=("T_G", "max"),
                                  ratio_max=("abs_theta_over_gammaT", "max"), bound_max=("bound_c_over_gammaT", "max"),
                                  theta_over_clip_max=("theta_over_clip", "max"), clip_events=("n_clip_events", "sum"),
                                  mma_min=("miss_minus_alpha_fb", "min"), mma_max=("miss_minus_alpha_fb", "max")).round(5).to_string())
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
