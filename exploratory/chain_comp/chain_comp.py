"""EXPLORATORY, POST HOC (instruction 12 §5(h); verdicts Shannon06 I5, Shannon07 J2): composition of hops 2-5 of the
custody chains by track state, recall per state and method, and the arithmetic share of the four-hop custody
difference on common chains that the per-hop recall differences account for. Counts and arithmetic only.

    python exploratory/chain_comp/chain_comp.py

Chains exactly as posthoc_custody_decomp_confirm2.py (= evaluate.custody_table): chain = (trip_id, chain), only chains
whose first evaluated hop is hop 0, rows sorted by hop, position j = 1..5. Confirmation 2, target 0.95, primary predictor,
evaluation seeds 0-4 (per seed, then the mean), blocks 1 and 2 and both pooled (combined). Read only:
results/porto_cctv_confirm2/runs/*/t0950/s*/hits.parquet and results/porto_cctv_confirm2_posthoc/custody/decomp_*.csv.
Track state = hopkind (0 later, 1 initiated, 2 re-acquired = post-gap).
Outputs (exploratory/chain_comp/):
  composition.csv      start (all, reacquired) x scope x j = 2..5: hops and hops per state (per seed equal; asserted)
  recall_state.csv     start x scope x j x state x method: recall of the j-th hops (unconditional) and conditional on
                       hops 1..j-1 hit; plus start = 'every hop' (all evaluation hops of the state, any position)
  common_check.csv     common chains (both methods of a pair hit hop 1): cond_j and survival_5 recomputed (point, seed
                       mean) against decomp_common_chains.csv
  arithmetic.csv       per pair: D4 = survival_5(group) - survival_5(marginal); S = sum over j = 2..5 of the conditional
                       recall differences; S / D4; L4 = 4 x (later-hop recall difference over every later hop);
                       L4 / D4; Lp = r_G^4 - r_M^4 with the same later-hop recalls; Lp / D4
  manifest.csv
"""
import hashlib
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "results/porto_cctv_confirm2/runs"
CU = ROOT / "results/porto_cctv_confirm2_posthoc/custody"
OUT = ROOT / "exploratory/chain_comp"
A = yaml.safe_load(open(ROOT / "configs/confirm2_analysis.yaml"))
PRED = A["predictor"]
T = 0.95
HMAX = 5
METHODS = ["static", "aci_g0005", "mvp_log", "qr_groups_refit"]     # ACI for the common-chain pairs of the paper sentence
PAIRS = [(m, g) for m in ["static", "aci_g0005"] for g in ["qr_groups_refit", "mvp_log"]]   # as the decomposition script
HEADER = "# Post hoc analysis (run after the confirm2 results were seen; exploratory, aggregation and arithmetic only)"


def load(blk, s):
    d = RUNS / blk / f"t{int(round(T * 1000)):04d}" / f"s{s}"
    cols = ["trip_id", "chain", "hop", "hopkind"] + [f"hit|{PRED}|{m}" for m in METHODS]
    H = pd.read_parquet(d / "hits.parquet", columns=cols)
    every = H[["hopkind"] + [f"hit|{PRED}|{m}" for m in METHODS]].copy()
    H["key"] = H.trip_id.astype(np.int64) * 1000 + H.chain.astype(np.int64)
    H = H.sort_values(["key", "hop"], kind="stable")
    H = H[H.groupby("key").hop.transform("min") == 0]
    H["j"] = H.groupby("key").cumcount() + 1
    H = H[H.j <= HMAX].copy()
    H["start"] = H.key.map(H[H.j == 1].set_index("key").hopkind)
    return H, every


def main():
    blocks, seeds = list(A["blocks"]), A["seeds"]["method"]
    data = {(b, s): load(b, s) for b in blocks for s in seeds}
    comp, rec, cc = [], [], []
    for scope in ["combined"] + blocks:
        bl = blocks if scope == "combined" else [scope]
        per_seed = {s: pd.concat([data[(b, s)][0] for b in bl]) for s in seeds}
        every = {s: pd.concat([data[(b, s)][1] for b in bl]) for s in seeds}
        for start, sel in (("all", None), ("reacquired", 2)):
            first = None
            for s in seeds:
                H = per_seed[s] if sel is None else per_seed[s][per_seed[s].start == sel]
                c = H[H.j >= 2].groupby(["j", "hopkind"]).size().unstack(fill_value=0)
                first = c if first is None else first
                assert c.equals(first), (scope, start, s)          # hops do not depend on the seed
            for j, r in first.iterrows():
                n = int(r.sum())
                comp.append({"start": start, "scope": scope, "j": j, "n_hops": n,
                             **{f"n_state{k}": int(r.get(k, 0)) for k in (0, 1, 2)},
                             **{f"share_state{k}": r.get(k, 0) / n for k in (0, 1, 2)}})
            for m in METHODS:
                acc = {}
                for s in seeds:
                    H = per_seed[s] if sel is None else per_seed[s][per_seed[s].start == sel]
                    P = H.pivot(index="key", columns="j", values=f"hit|{PRED}|{m}")
                    K = H.pivot(index="key", columns="j", values="hopkind")
                    hit = P.reindex(columns=range(1, HMAX + 1)).to_numpy()
                    hk = K.reindex(columns=range(1, HMAX + 1)).to_numpy()
                    ok = np.nancumprod(np.where(np.isnan(hit), 1, hit), axis=1) * ~np.isnan(hit)
                    for j in range(2, HMAX + 1):
                        for k in (0, 1, 2):
                            has = (hk[:, j - 1] == k)
                            if not has.any():
                                continue
                            prev = has & (ok[:, j - 2] == 1)
                            acc.setdefault((j, k), []).append((hit[has, j - 1].mean(), int(has.sum()),
                                                               hit[prev, j - 1].mean(), int(prev.sum())))
                for (j, k), v in acc.items():
                    v = np.array(v)
                    rec.append({"start": start, "scope": scope, "j": j, "state": k, "method": m,
                                "recall": v[:, 0].mean(), "n": v[:, 1].mean(), "cond_recall": v[:, 2].mean(),
                                "n_cond": v[:, 3].mean()})
        for m in METHODS:
            for k in (0, 1, 2):
                r = [every[s].loc[every[s].hopkind == k, f"hit|{PRED}|{m}"].mean() for s in seeds]
                n = int((every[seeds[0]].hopkind == k).sum())
                rec.append({"start": "every hop", "scope": scope, "j": "any", "state": k, "method": m,
                            "recall": float(np.mean(r)), "n": n, "cond_recall": np.nan, "n_cond": np.nan})
        # common chains, point estimates (seed mean), as posthoc_custody_decomp_confirm2.py
        for mm, gg in PAIRS:
            for who in (mm, gg):
                acc = {}
                for s in seeds:
                    H = per_seed[s][per_seed[s].start == 2]
                    P = {x: H.pivot(index="key", columns="j", values=f"hit|{PRED}|{x}").reindex(columns=range(1, HMAX + 1))
                         for x in (mm, gg, who)}
                    common = (P[mm][1].to_numpy() == 1) & (P[gg][1].to_numpy() == 1)
                    hit = P[who].to_numpy()[common]
                    ok = np.nancumprod(np.where(np.isnan(hit), 1, hit), axis=1) * ~np.isnan(hit)
                    for j in range(2, HMAX + 1):
                        has = ~np.isnan(hit[:, j - 1])
                        acc.setdefault(("cond", j), []).append((has & (ok[:, j - 1] == 1)).sum() / (has & (ok[:, j - 2] == 1)).sum())
                    has5 = ~np.isnan(hit[:, HMAX - 1])
                    acc.setdefault(("survival5", 5), []).append((has5 & (ok[:, HMAX - 1] == 1)).sum() / has5.sum())
                for (st, j), v in acc.items():
                    cc.append({"scope": scope, "pair": f"{mm} vs {gg}", "stat": st, "j": j, "method": who,
                               "value": float(np.mean(v))})
    OUT.mkdir(parents=True, exist_ok=True)
    C = pd.DataFrame(comp); R = pd.DataFrame(rec); CC = pd.DataFrame(cc)
    ref = pd.read_csv(CU / "decomp_common_chains.csv", comment="#")
    M = CC.merge(ref[["scope", "pair", "stat", "j", "method", "value"]], on=["scope", "pair", "stat", "j", "method"],
                 how="left", suffixes=("", "_decomp"))
    M["abs_diff"] = (M.value - M.value_decomp).abs()
    assert M.value_decomp.notna().all() and M.abs_diff.max() < 1e-12, M.sort_values("abs_diff").tail()
    rows = []
    for scope in ["combined"] + list(A["blocks"]):
        ev = R[(R.start == "every hop") & (R.scope == scope) & (R.state == 0)].set_index("method").recall
        for mm, gg in PAIRS:
            pr = M[(M.scope == scope) & (M.pair == f"{mm} vs {gg}")].set_index(["stat", "j", "method"]).value
            D4 = pr[("survival5", 5, gg)] - pr[("survival5", 5, mm)]
            S = sum(pr[("cond", j, gg)] - pr[("cond", j, mm)] for j in range(2, HMAX + 1))
            if mm in ev.index:
                L4 = 4 * (ev[gg] - ev[mm]); Lp = ev[gg] ** 4 - ev[mm] ** 4
            else:
                L4 = Lp = np.nan
            rows.append({"scope": scope, "group": gg, "marginal": mm, "D4": D4, "S_sum_cond_diff": S, "S_over_D4": S / D4,
                         "later_recall_group": ev.get(gg, np.nan), "later_recall_marginal": ev.get(mm, np.nan),
                         "L4_4x_later_diff": L4, "L4_over_D4": L4 / D4, "Lp_power4_diff": Lp, "Lp_over_D4": Lp / D4})
    AR = pd.DataFrame(rows)
    for name, df in (("composition", C), ("recall_state", R), ("common_check", M), ("arithmetic", AR)):
        with open(OUT / f"{name}.csv", "w") as f:
            f.write(HEADER + "\n"); df.to_csv(f, index=False)
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(Path(__file__).relative_to(ROOT))], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
    fs = ["composition.csv", "recall_state.csv", "common_check.csv", "arithmetic.csv"]
    pd.DataFrame({"file": [f"exploratory/chain_comp/{f}" for f in fs],
                  "sha256": [hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in fs],
                  "script_commit": commit}).to_csv(OUT / "manifest.csv", index=False)
    pd.set_option("display.width", 250)
    print(C[C.scope == "combined"].to_string(index=False))
    print(R[(R.scope == "combined")].to_string(index=False))
    print(AR.to_string(index=False))


if __name__ == "__main__":
    main()
