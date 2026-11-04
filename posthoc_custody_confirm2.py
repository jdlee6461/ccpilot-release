"""POST-HOC (after the confirm2 results were seen): track custody on the confirm2 runs.

    python posthoc_custody_confirm2.py

Metric: exactly ccpilot/evaluate.py custody_table (old manuscript Table 18): per chain key = (trip_id, chain), hops
sorted by hop; only chains whose first evaluated hop is hop 0; ok_so_far = cumulative minimum of the open-loop hit;
custody(h) = mean of ok_so_far over the chains' h-th row (h = 1..5). Reported for all chains and split by the
chain-start group (hopkind of the first hop: 1 initiated, 2 re-acquired), per block (segment of the first hop) and
pooled over both blocks. JD decision 2026-10-17: no new metric definitions.

Inputs (read only): results/porto_cctv_confirm2/runs/<block>/t<target>/s<seed>/hits.parquet (50 runs),
work/porto_cctv_confirm2/taxi_map.parquet (DEVIATIONS.md D5). Methods: the ten methods of the confirm2 analysis
(CityTrac-style rule at the run's nominal target). Seeds: custody per seed, then the mean over seeds 0-4 and the
seed range.
Intervals (the confirm2 'other' setting of confirm2_analysis.py): cluster bootstrap, 95% percentile, B = 2000, by taxi
(drawn jointly over the two blocks) and by day (local date of the chain's first exit, resampled within its block); the
reported interval takes at each end the more conservative of the two (lo = min, hi = max). The same weights are used
for every seed, method and statistic, so differences between methods are paired. rng seed = bootstrap seed of
configs/confirm2_analysis.yaml (taxi weights drawn first, then day weights).
Outputs: results/porto_cctv_confirm2_posthoc/custody/
  custody.csv        method x target x scope x start x h: custody (seed mean), seed range, intervals
  custody_seeds.csv  per seed
  custody_diffs.csv  every pair of methods: difference of custody (method_a - method_b), paired intervals
  custody_numbers.tex
"""
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "results/porto_cctv_confirm2/runs"
OUT = ROOT / "results/porto_cctv_confirm2_posthoc/custody"
A = yaml.safe_load(open(ROOT / "configs/confirm2_analysis.yaml"))
PRED = A["predictor"]
TZ = "Europe/Lisbon"
H = 5
B = int(A["bootstrap"]["other"]["B"])
LEVEL = float(A["bootstrap"]["other"]["level"])
METHODS = A["proposed"] + A["comparators_main"] + A["comparators_other"]
START = {0: "all", 1: "initiated", 2: "reacquired"}   # 0 = all chains (custody_table without the split)
HEADER = "Post hoc analysis (run after the confirm2 results were seen; metric definitions as in Table 18 of the earlier manuscript)"


def hitcol(m, t):
    if m == "spatula_rule|fixed":
        return "hit|spatula_rule|fixed"
    if m == "citytrac_nominal":
        return f"hit|citytrac_rule|target{int(round(t * 100)):03d}"
    return f"hit|{PRED}|{m}"


def chain_rows(H0, hit):
    """evaluate.custody_table steps; per row: h, ok_so_far, first segment, first hopkind, taxi and day of the chain."""
    df = pd.DataFrame({"key": H0["key"].to_numpy(), "hop": H0["hop"].to_numpy(), "hit": hit,
                       "seg": H0["segment"].to_numpy(), "hk": H0["hopkind"].to_numpy(),
                       "taxi": H0["taxi"].to_numpy(), "day": H0["day"].to_numpy()}).sort_values(["key", "hop"], kind="stable")
    df = df[df.groupby("key")["hop"].transform("min") == 0]
    df["ok_so_far"] = df.groupby("key")["hit"].cummin()
    df["h"] = df.groupby("key").cumcount() + 1
    for c, src in (("seg_first", "seg"), ("hk_first", "hk"), ("taxi_first", "taxi"), ("day_first", "day")):
        df[c] = df.groupby("key")[src].transform("first")
    return df[df["h"] <= H]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tm = pd.read_parquet(ROOT / "work/porto_cctv_confirm2/taxi_map.parquet").set_index("trip_id").taxi_id
    targets, seeds, blocks = A["targets"], A["seeds"]["method"], list(A["blocks"])
    raw = {}           # (m, t, s, blk) -> chain rows (h <= 5)
    for blk in blocks:
        for t in targets:
            for s in seeds:
                d = RUNS / blk / f"t{int(round(t * 1000)):04d}" / f"s{s}"
                cols = ["trip_id", "chain", "hop", "hopkind", "segment", "t_exit"] + [hitcol(m, t) for m in METHODS]
                H0 = pd.read_parquet(d / "hits.parquet", columns=cols)
                H0["key"] = H0["trip_id"].astype(np.int64) * 1000 + H0["chain"].astype(np.int64)
                H0["taxi"] = tm.reindex(H0["trip_id"]).to_numpy()
                assert not pd.isna(H0["taxi"]).any()
                H0["day"] = blk + ":" + pd.to_datetime(H0.t_exit, unit="s", utc=True).dt.tz_convert(TZ).dt.date.astype(str)
                for m in METHODS:
                    df = chain_rows(H0, H0[hitcol(m, t)].to_numpy().astype(np.int8))
                    assert set(df.seg_first.unique()) <= {f"{blk}_eval"} and set(df.hk_first.unique()) <= {1, 2}
                    raw[(m, t, s, blk)] = df[["h", "ok_so_far", "hk_first", "taxi_first", "day_first"]]
                print(f"[custody] {blk} t={t} s={s}", flush=True)
    # cluster codes (taxi joint over blocks, day within block) and weights, as confirm2_analysis.weights()
    allr = pd.concat(raw.values())
    taxis = pd.Index(np.sort(allr.taxi_first.unique())); days = pd.Index(np.sort(allr.day_first.unique()))
    day_block = np.array([blocks.index(d.split(":")[0]) for d in days])
    rng = np.random.default_rng(A["seeds"]["bootstrap"])
    W = {"taxi": rng.multinomial(len(taxis), np.full(len(taxis), 1 / len(taxis)), size=B).astype(float)}
    Wd = np.zeros((B, len(days)))
    for bi in range(len(blocks)):
        idx = np.flatnonzero(day_block == bi)
        Wd[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=B)
    W["day"] = Wd
    code = {"taxi": taxis, "day": days}
    S = {}             # (m, t, s, blk, k, h, cluster) -> (num, den) per cluster code
    for (m, t, s, blk), df in raw.items():
        ci = {c: code[c].get_indexer(df[f"{c}_first"]) for c in code}
        for k in START:
            for h in range(1, H + 1):
                mm = (((df.hk_first == k) | (k == 0)) & (df.h == h)).to_numpy()
                for c in code:
                    S[(m, t, s, blk, k, h, c)] = (
                        np.bincount(ci[c][mm], weights=df.ok_so_far.to_numpy()[mm], minlength=len(code[c])),
                        np.bincount(ci[c][mm], minlength=len(code[c])).astype(float))
    a = (1 - LEVEL) / 2
    est, boots, rows, srows = {}, {}, [], []
    for m in METHODS:
        for t in targets:
            for scope in ["combined"] + blocks:
                bl = blocks if scope == "combined" else [scope]
                for k, kn in START.items():
                    for h in range(1, H + 1):
                        per_seed, bt = [], {c: [] for c in code}
                        for s in seeds:
                            nd = {c: [sum(S[(m, t, s, b, k, h, c)][j] for b in bl) for j in (0, 1)] for c in code}
                            num, den = nd["taxi"]
                            per_seed.append(num.sum() / den.sum())
                            srows.append(dict(method=m, target=t, scope=scope, start=kn, h=h, seed=s,
                                              n_chains=int(den.sum()), custody=per_seed[-1]))
                            for c in code:
                                with np.errstate(invalid="ignore", divide="ignore"):
                                    bt[c].append((W[c] @ nd[c][0]) / (W[c] @ nd[c][1]))
                        key = (m, t, scope, kn, h)
                        est[key] = float(np.mean(per_seed))
                        boots[key] = {c: np.nanmean(np.vstack(bt[c]), axis=0) for c in code}
                        q = {c: (np.nanquantile(boots[key][c], a), np.nanquantile(boots[key][c], 1 - a)) for c in code}
                        rows.append(dict(method=m, target=t, scope=scope, start=kn, h=h, n_chains=int(den.sum()),
                                         custody=est[key], seed_min=float(np.min(per_seed)), seed_max=float(np.max(per_seed)),
                                         lo_taxi=q["taxi"][0], hi_taxi=q["taxi"][1], lo_day=q["day"][0], hi_day=q["day"][1],
                                         lo=min(q["taxi"][0], q["day"][0]), hi=max(q["taxi"][1], q["day"][1]),
                                         B=B, level=LEVEL, meets_min30=bool(den.sum() >= 30)))
    drows = []
    for ma, mb in combinations(METHODS, 2):
        for t in targets:
            for scope in ["combined"] + blocks:
                for kn in START.values():
                    for h in range(1, H + 1):
                        ka, kb = (ma, t, scope, kn, h), (mb, t, scope, kn, h)
                        q = {c: np.nanquantile(boots[ka][c] - boots[kb][c], [a, 1 - a]) for c in code}
                        lo, hi = min(q["taxi"][0], q["day"][0]), max(q["taxi"][1], q["day"][1])
                        drows.append(dict(method_a=ma, method_b=mb, target=t, scope=scope, start=kn, h=h,
                                          diff=est[ka] - est[kb], lo_taxi=q["taxi"][0], hi_taxi=q["taxi"][1],
                                          lo_day=q["day"][0], hi_day=q["day"][1], lo=lo, hi=hi,
                                          reading=("a higher" if lo > 0 else "a lower" if hi < 0 else "not distinguished")))
    for df, name in ((pd.DataFrame(rows), "custody.csv"), (pd.DataFrame(srows), "custody_seeds.csv"),
                     (pd.DataFrame(drows), "custody_diffs.csv")):
        with open(OUT / name, "w", encoding="utf-8") as fh:
            fh.write(f"# {HEADER}\n")
            df.to_csv(fh, index=False)
    numbers(pd.DataFrame(rows))
    print(f"[custody] {len(rows)} rows, {len(drows)} differences -> {OUT}; clusters taxi={len(taxis)} day={len(days)}")


WORD = {0.9: "Ninety", 0.93: "NinetyThree", 0.95: "NinetyFive", 0.97: "NinetySeven", 0.98: "NinetyEight"}
MN = {"mvp_log": "Mvplog", "qr_ogd": "Qrogd", "static": "Static", "aci_g0005": "Aci", "mondrian_hour_hop_speed": "Mondrian",
      "qr_groups": "Qrgroups", "qr_groups_refit": "Qrrefit", "qr_groups_refit7": "Qrrefitseven",
      "spatula_rule|fixed": "Spatula", "citytrac_nominal": "Citytrac"}
HW = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}
SN = {"initiated": "Init", "reacquired": "Reacq", "all": "All"}


def numbers(R):
    L = [f"% {HEADER}", "% AUTO-GENERATED by posthoc_custody_confirm2.py from custody.csv (scope=combined): custody (seed mean), "
         "Lo/Hi = conservative 95% bounds of the taxi and day cluster bootstraps (B=2000), SeedMin/SeedMax; 3 decimals."]
    for r in R[R.scope == "combined"].itertuples():
        base = f"custody{MN[r.method]}{SN[r.start]}T{WORD[round(r.target, 2)]}H{HW[r.h]}"
        src = f"% custody.csv scope=combined method={r.method} target={r.target} start={r.start} h={r.h}"
        for suf, v in (("", r.custody), ("Lo", r.lo), ("Hi", r.hi), ("SeedMin", r.seed_min), ("SeedMax", r.seed_max)):
            L.append(f"\\newcommand{{\\{base}{suf}}}{{{v:.3f}}} {src} col={suf or 'custody'}")
    f = OUT / "custody_numbers.tex"
    keep = ""      # decomposition block written by posthoc_custody_decomp_confirm2.py, kept across re-runs
    if f.exists() and "% ---- BEGIN decomposition block" in f.read_text():
        t = f.read_text(); keep = t[t.index("% ---- BEGIN decomposition block"):]
    f.write_text("\n".join(L) + "\n" + keep)


if __name__ == "__main__":
    main()
