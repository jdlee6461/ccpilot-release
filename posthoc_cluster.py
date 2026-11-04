"""POST-HOC cluster bootstrap of group recall on the held-out (confirmation) period. Not pre-registered.

    python posthoc_cluster.py            # reads stored hop-level results only; no model is run

Inputs (all existing):
  results/porto_cctv_confirm_posthoc/outage_suite/none_s7/hits.parquet   evaluation seed 0, every method + score
      (no-outage run; its hits equal the confirmation regrade hits, see paper/scripts/ch6lib.load_held)
  results/porto_cctv_confirm_posthoc/seeds_prereg25/seed_{0..4}/hits.parquet   evaluation seeds 0-4
  work/porto_cctv_confirm/taxi_map.parquet   trip_id -> TAXI_ID (notes/confirm2/taxi_map.py)

Per method, segment and group of the pre-registered 25-group definition:
  Wilson 95% interval (as in the C1 judgement), and percentile cluster-bootstrap intervals with clusters = taxi
  or = local calendar day of the exit (B resamples of clusters with replacement, within segment):
  two-sided 95% (2.5/97.5 %) and one-sided 95% lower bound (5 %). Design effect = bootstrap variance of the
  group recall / (p(1-p)/n).
Seed spread: standard deviation over evaluation seeds 0-4 of each group's recall (same hops, different feedback
sample and MVP randomisation).

Output: results/porto_cctv_confirm_posthoc/cluster_ci/{cluster_ci.csv, below_bar.csv, seed_sd.csv}
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "paper" / "scripts"))
import ch6lib as L  # noqa: E402

OUT = ROOT / "results/porto_cctv_confirm_posthoc/cluster_ci"
TAXI = ROOT / "work/porto_cctv_confirm/taxi_map.parquet"
SEEDS = ROOT / "results/porto_cctv_confirm_posthoc/seeds_prereg25"
TZ = "Europe/Lisbon"
B = 4000
BAR = 0.94


def groups(H):
    for d in L.DIMS25:
        for g in sorted(H[d].unique()):
            yield d, int(g)


def boot(cl, M, Y, rng):
    """cl: cluster code per hop (0..C-1); M: hop x group membership (bool); Y: hop x method hits.
    Returns bootstrap recall array (B, groups, methods)."""
    C = cl.max() + 1
    N = np.zeros((C, M.shape[1])); np.add.at(N, cl, M)
    K = np.zeros((C, M.shape[1], Y.shape[1]))
    for j in range(Y.shape[1]):
        np.add.at(K[:, :, j], cl, M * Y[:, [j]])
    W = rng.multinomial(C, np.full(C, 1.0 / C), size=B).astype(float)      # (B, C) cluster resample counts
    n_b = W @ N
    k_b = np.einsum("bc,cgm->bgm", W, K)
    return k_b / n_b[:, :, None]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    H = L.load_held()
    tm = pd.read_parquet(TAXI).set_index("trip_id")["taxi_id"]
    H["taxi"] = tm.reindex(H.trip_id).to_numpy()
    assert H["taxi"].notna().all()
    H["day"] = pd.to_datetime(H.t_exit, unit="s", utc=True).dt.tz_convert(TZ).dt.date
    keys = [k for k in L.MKEYS]
    Y_all = np.column_stack([H[L.hitcol(k)].to_numpy() for k in keys]).astype(float)
    G = list(groups(H))
    M_all = np.column_stack([(H[d].to_numpy() == g) for d, g in G])
    rng = np.random.default_rng(20261002)
    rows = []
    for seg, sl in L.SEGS:
        m = (H.seg == seg).to_numpy()
        M, Y = M_all[m], Y_all[m]
        n = M.sum(0); k = M.T.astype(float) @ Y                      # (groups, methods)
        p = k / n[:, None]
        wlo, wub = L.wilson(k, n[:, None])
        res = {}
        for cname in ("taxi", "day"):
            codes = pd.factorize(H.loc[m, cname])[0]
            R = boot(codes, M, Y, rng)
            res[cname] = (np.percentile(R, 2.5, axis=0), np.percentile(R, 97.5, axis=0), np.percentile(R, 5, axis=0),
                          R.var(axis=0, ddof=1), len(np.unique(codes)))
        for gi, (d, g) in enumerate(G):
            for mi, key in enumerate(keys):
                r = {"segment": seg, "seg": sl, "group": f"{d}={g}", "group_name": L.group_name(d, g),
                     "method": key, "n": int(n[gi]), "recall": p[gi, mi],
                     "wilson_lo": wlo[gi, mi], "wilson_ub": wub[gi, mi]}
                v_bin = p[gi, mi] * (1 - p[gi, mi]) / n[gi]
                for cname, (lo, ub, lb1, var, ncl) in res.items():
                    r.update({f"{cname}_lo": lo[gi, mi], f"{cname}_ub": ub[gi, mi], f"{cname}_lb1s": lb1[gi, mi],
                              f"{cname}_de": var[gi, mi] / v_bin if v_bin > 0 else np.nan, f"{cname}_clusters": ncl})
                rows.append(r)
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "cluster_ci.csv", index=False)

    # groups judged below the bar (upper end < 0.94) under each interval
    cnt = (R.assign(wilson=R.wilson_ub < BAR, taxi=R.taxi_ub < BAR, day=R.day_ub < BAR)
           .groupby(["method", "seg"])[["wilson", "taxi", "day"]].sum().astype(int).unstack("seg"))
    cnt.columns = [f"{a}_{b}" for a, b in cnt.columns]
    cnt = cnt.reindex(keys)
    cnt.to_csv(OUT / "below_bar.csv")

    # seed spread (evaluation seeds 0-4); hits files store the regrade method set
    S = []
    for s in range(5):
        Hs = pd.read_parquet(SEEDS / f"seed_{s}/hits.parquet")
        for seg, sl in L.SEGS:
            ms = (Hs.segment == seg).to_numpy()
            for key in keys:
                col = L.hitcol(key)
                if col not in Hs.columns:
                    continue
                y = Hs[col].to_numpy()
                for d, g in G:
                    mm = ms & (Hs[d].to_numpy() == g)
                    S.append({"seed": s, "seg": sl, "method": key, "group": f"{d}={g}", "n": int(mm.sum()),
                              "recall": y[mm].mean()})
    S = pd.DataFrame(S)
    SD = S.groupby(["method", "seg", "group"]).agg(n=("n", "first"), mean=("recall", "mean"), sd=("recall", "std"),
                                                   min=("recall", "min"), max=("recall", "max")).reset_index()
    SD.to_csv(OUT / "seed_sd.csv", index=False)

    pd.set_option("display.width", 250)
    print(cnt.to_string())
    ml = R[R.method == "mvp_log"]
    print(ml[["seg", "group", "n", "recall", "wilson_ub", "taxi_ub", "day_ub", "taxi_de", "day_de"]].round(4).to_string(index=False))
    print(SD[SD.method == "mvp_log"].round(4).to_string(index=False))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
