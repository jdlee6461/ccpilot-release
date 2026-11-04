"""POST-HOC (after the confirm2 results were seen): decomposition of track custody for chains that start with a
re-acquisition (David v3 instruction 4.3; JD addition 2026-10-18: common chains).

    python posthoc_custody_decomp_confirm2.py

Chains and hits exactly as posthoc_custody_confirm2.py / evaluate.custody_table (chain = (trip_id, chain), first evaluated
hop = hop 0, rows sorted by hop; position j = 1..5). Target 0.95, chains whose first hop is a re-acquisition
(hopkind 2), both blocks pooled and per block, evaluation seeds 0-4 (per seed, then the mean).

(1) all re-acquisition chains, per method:
    cond_hit_j (j = 2..5) = #(chains with a j-th hop whose hops 1..j all hit) / #(chains with a j-th hop whose hops
                            1..j-1 all hit)                      (conditional hit rate of hop j given the earlier hops)
    custody_5            = share of chains with a 5th hop whose hops 1..5 all hit (= custody_table, h = 5)
    cost_j               = mean cost per hop of the j-th hops of all re-acquisition chains (same hops for every method);
                           ratio to static
    later_share_j        = share of the j-th hops with hopkind 0 (later hop)
(2) common chains, per pair (marginal M in static, ACI; group G in qr_groups_refit, mvp_log): chains in which both M and
    G hit hop 1 (per seed); for each of M and G: cond_hit_j (j = 2..5) and survival_5 = share of common chains with a 5th
    hop whose hops 2..5 all hit.
Intervals: taxi-cluster bootstrap, 95% percentile, B = 2000 (rng seed = bootstrap seed of configs/confirm2_analysis.yaml),
the same weights for every method, seed and statistic, so differences (group - marginal) are paired.
Outputs (results/porto_cctv_confirm2_posthoc/custody/): decomp_all_chains.csv, decomp_common_chains.csv, decomp_diffs.csv,
and a marked macro block in custody_numbers.tex (`--numbers-only` rewrites only that block from the CSVs).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "results/porto_cctv_confirm2/runs"
OUT = ROOT / "results/porto_cctv_confirm2_posthoc/custody"
A = yaml.safe_load(open(ROOT / "configs/confirm2_analysis.yaml"))
PRED = A["predictor"]
T = 0.95
HMAX = 5
B = int(A["bootstrap"]["other"]["B"])
CAL8 = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd",
        "mvp_log"]
MARG = ["static", "aci_g0005"]
GROUP = ["qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log"]
PAIRS = [(m, g) for m in MARG for g in ["qr_groups_refit", "mvp_log"]]
HEADER = "Post hoc analysis (run after the confirm2 results were seen; metric definitions as in Table 18 of the earlier manuscript)"


def load():
    """per (block, seed): chain-level table of re-acquisition chains with hit_j / cost_j / hk_j per method (j = 1..5)."""
    tm = pd.read_parquet(ROOT / "work/porto_cctv_confirm2/taxi_map.parquet").set_index("trip_id").taxi_id
    out = {}
    for blk in A["blocks"]:
        for s in A["seeds"]["method"]:
            d = RUNS / blk / f"t{int(round(T * 1000)):04d}" / f"s{s}"
            cols = ["trip_id", "chain", "hop", "hopkind"] + [f"hit|{PRED}|{m}" for m in CAL8] + [f"cost|{PRED}|{m}" for m in CAL8]
            H = pd.read_parquet(d / "hits.parquet", columns=cols)
            H["key"] = H.trip_id.astype(np.int64) * 1000 + H.chain.astype(np.int64)
            H = H.sort_values(["key", "hop"], kind="stable")
            H = H[H.groupby("key").hop.transform("min") == 0]
            H["j"] = H.groupby("key").cumcount() + 1
            H = H[H.j <= HMAX]
            first = H[H.j == 1].set_index("key")
            keys = first.index[first.hopkind == 2]
            H = H[H.key.isin(keys)]
            W = {"taxi": tm.reindex(first.loc[keys, "trip_id"]).to_numpy(), "key": keys.to_numpy()}
            assert not pd.isna(W["taxi"]).any()
            P = H.pivot(index="key", columns="j")
            tab = pd.DataFrame({"taxi": W["taxi"]}, index=keys)
            for m in CAL8:
                for j in range(1, HMAX + 1):
                    tab[f"hit_{m}_{j}"] = P[(f"hit|{PRED}|{m}", j)].reindex(keys).to_numpy()
                    tab[f"cost_{m}_{j}"] = P[(f"cost|{PRED}|{m}", j)].reindex(keys).to_numpy()
            for j in range(1, HMAX + 1):
                tab[f"hk_{j}"] = P[("hopkind", j)].reindex(keys).to_numpy()
            out[(blk, s)] = tab
            print(f"[decomp] {blk} s={s}: {len(tab)} re-acquisition chains", flush=True)
    return out


def ratio_boot(num, den, W):
    """point and bootstrap replicates of sum(num)/sum(den), num/den per taxi."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return num.sum() / den.sum(), (W @ num) / (W @ den)


def main():
    data = load()
    blocks, seeds = list(A["blocks"]), A["seeds"]["method"]
    taxis = pd.Index(np.sort(pd.concat([t.taxi for t in data.values()]).unique()))
    rng = np.random.default_rng(A["seeds"]["bootstrap"])
    W = rng.multinomial(len(taxis), np.full(len(taxis), 1 / len(taxis)), size=B).astype(float)

    def per_taxi(tab, v):
        return np.bincount(taxis.get_indexer(tab.taxi), weights=v, minlength=len(taxis))

    stats = {}    # (table, scope, stat, method[, pair]) -> (point over seeds mean, boot mean over seeds)

    def put(key, pts, boots):
        stats[key] = (float(np.mean(pts)), np.nanmean(np.vstack(boots), axis=0))

    for scope in ["combined"] + blocks:
        bl = blocks if scope == "combined" else [scope]
        # (1) all re-acquisition chains
        for m in CAL8:
            acc = {}
            for s in seeds:
                tab = pd.concat([data[(b, s)] for b in bl])
                hit = np.column_stack([tab[f"hit_{m}_{j}"].to_numpy() for j in range(1, HMAX + 1)])   # NaN = no j-th hop
                ok = np.nancumprod(np.where(np.isnan(hit), 1, hit), axis=1) * ~np.isnan(hit)      # hops 1..j all hit
                for j in range(2, HMAX + 1):
                    has = ~np.isnan(hit[:, j - 1])
                    num = per_taxi(tab, (has & (ok[:, j - 1] == 1)).astype(float))
                    den = per_taxi(tab, (has & (ok[:, j - 2] == 1)).astype(float))
                    acc.setdefault(("cond", j), []).append(ratio_boot(num, den, W))
                    c = tab[f"cost_{m}_{j}"].to_numpy(); hc = ~np.isnan(c)
                    acc.setdefault(("cost", j), []).append(ratio_boot(per_taxi(tab, np.where(hc, c, 0)), per_taxi(tab, hc.astype(float)), W))
                    if m == CAL8[0]:
                        hk = tab[f"hk_{j}"].to_numpy(); hh = ~np.isnan(hk)
                        acc.setdefault(("later", j), []).append(ratio_boot(per_taxi(tab, (hk == 0).astype(float)), per_taxi(tab, hh.astype(float)), W))
                has5 = ~np.isnan(hit[:, HMAX - 1])
                acc.setdefault(("custody5", 5), []).append(ratio_boot(per_taxi(tab, (has5 & (ok[:, HMAX - 1] == 1)).astype(float)),
                                                                      per_taxi(tab, has5.astype(float)), W))
            for (st, j), lst in acc.items():
                put(("all", scope, st, j, m), [p for p, _ in lst], [b for _, b in lst])
        # (2) common chains: both methods of the pair hit hop 1
        for mm, gg in PAIRS:
            for who in (mm, gg):
                acc = {}
                for s in seeds:
                    tab = pd.concat([data[(b, s)] for b in bl])
                    common = (tab[f"hit_{mm}_1"].to_numpy() == 1) & (tab[f"hit_{gg}_1"].to_numpy() == 1)
                    sub = tab[common]
                    hit = np.column_stack([sub[f"hit_{who}_{j}"].to_numpy() for j in range(1, HMAX + 1)])
                    ok = np.nancumprod(np.where(np.isnan(hit), 1, hit), axis=1) * ~np.isnan(hit)
                    for j in range(2, HMAX + 1):
                        has = ~np.isnan(hit[:, j - 1])
                        acc.setdefault(("cond", j), []).append(ratio_boot(per_taxi(sub, (has & (ok[:, j - 1] == 1)).astype(float)),
                                                                          per_taxi(sub, (has & (ok[:, j - 2] == 1)).astype(float)), W))
                    has5 = ~np.isnan(hit[:, HMAX - 1])
                    acc.setdefault(("survival5", 5), []).append(ratio_boot(per_taxi(sub, (has5 & (ok[:, HMAX - 1] == 1)).astype(float)),
                                                                           per_taxi(sub, has5.astype(float)), W))
                    acc.setdefault(("n_common", 1), []).append((float(common.sum()), np.full(B, np.nan)))
                    acc.setdefault(("n_common5", 5), []).append((float((common & ~np.isnan(tab[f"hit_{who}_5"].to_numpy())).sum()), np.full(B, np.nan)))
                for (st, j), lst in acc.items():
                    put(("common", scope, st, j, who, f"{mm} vs {gg}"), [p for p, _ in lst], [b for _, b in lst])

    def q(b):
        return (np.nanquantile(b, 0.025), np.nanquantile(b, 0.975)) if np.isfinite(b).any() else (np.nan, np.nan)

    rows_a, rows_c, rows_d = [], [], []
    for k, (pt, bt) in stats.items():
        lo, hi = q(bt)
        if k[0] == "all":
            rows_a.append(dict(scope=k[1], stat=k[2], j=k[3], method=k[4], value=pt, lo=lo, hi=hi))
        else:
            rows_c.append(dict(scope=k[1], pair=k[5], stat=k[2], j=k[3], method=k[4], value=pt, lo=lo, hi=hi))
    A_ = pd.DataFrame(rows_a)
    # cost ratio to static
    for scope in ["combined"] + blocks:
        for j in range(2, HMAX + 1):
            ps, bs = stats[("all", scope, "cost", j, "static")]
            for m in CAL8:
                pm, bm = stats[("all", scope, "cost", j, m)]
                lo, hi = q(bm / bs)
                rows_a.append(dict(scope=scope, stat="cost_ratio_to_static", j=j, method=m, value=pm / ps, lo=lo, hi=hi))
    # paired differences group - marginal (all chains: every group method vs static and ACI; common chains: the pair)
    for scope in ["combined"] + blocks:
        for st, js in (("cond", range(2, HMAX + 1)), ("custody5", [5])):
            for j in js:
                for mm in MARG:
                    for gg in GROUP + ["mondrian_hour_hop_speed"]:
                        pg, bg = stats[("all", scope, st, j, gg)]; pm, bm = stats[("all", scope, st, j, mm)]
                        lo, hi = q(bg - bm)
                        rows_d.append(dict(table="all", scope=scope, stat=st, j=j, group_method=gg, marginal=mm,
                                           diff=pg - pm, lo=lo, hi=hi,
                                           reading="group higher" if lo > 0 else "group lower" if hi < 0 else "not distinguished"))
        for mm, gg in PAIRS:
            for st, js in (("cond", range(2, HMAX + 1)), ("survival5", [5])):
                for j in js:
                    key = f"{mm} vs {gg}"
                    pg, bg = stats[("common", scope, st, j, gg, key)]; pm, bm = stats[("common", scope, st, j, mm, key)]
                    lo, hi = q(bg - bm)
                    rows_d.append(dict(table="common", scope=scope, stat=st, j=j, group_method=gg, marginal=mm,
                                       diff=pg - pm, lo=lo, hi=hi,
                                       reading="group higher" if lo > 0 else "group lower" if hi < 0 else "not distinguished"))
    for df, name in ((pd.DataFrame(rows_a), "decomp_all_chains.csv"), (pd.DataFrame(rows_c), "decomp_common_chains.csv"),
                     (pd.DataFrame(rows_d), "decomp_diffs.csv")):
        with open(OUT / name, "w", encoding="utf-8") as fh:
            fh.write(f"# {HEADER}\n")
            df.to_csv(fh, index=False)
    print(f"[decomp] -> {OUT}: decomp_all_chains.csv ({len(rows_a)}), decomp_common_chains.csv ({len(rows_c)}), "
          f"decomp_diffs.csv ({len(rows_d)})")


BEGIN, END = "% ---- BEGIN decomposition block (posthoc_custody_decomp_confirm2.py)", "% ---- END decomposition block"
MN = {"static": "Static", "aci_g0005": "Aci", "qr_groups_refit": "Qrrefit", "mvp_log": "Mvplog"}


def numbers():
    """Common-chain and cost-ratio macros (target 0.95, re-acquisition chains, scope=combined), written as a marked block
    into custody_numbers.tex (the block is replaced on every run; posthoc_custody_confirm2.py keeps it)."""
    c = pd.read_csv(OUT / "decomp_common_chains.csv", comment="#").query("scope == 'combined'")
    d = pd.read_csv(OUT / "decomp_diffs.csv", comment="#").query("scope == 'combined'")
    a = pd.read_csv(OUT / "decomp_all_chains.csv", comment="#").query("scope == 'combined'")
    p1 = lambda x: (f"$-${-100 * x:.1f}" if f"{100 * x:.1f}".startswith("-") and f"{100 * x:.1f}" != "-0.0" else f"{abs(100 * x):.1f}" if f"{100 * x:.1f}" == "-0.0" else f"{100 * x:.1f}")
    L = [BEGIN, f"% {HEADER}", "% target 0.95, chains starting with a re-acquisition, both blocks pooled, seed means; intervals: "
         "taxi-cluster bootstrap 95% (B=2000). Survival in %, differences in percentage points, one decimal (negative values typeset as $-$); cost ratios 2 decimals."]
    def put(name, v, src):
        assert name.isalpha(), name
        L.append(f"\\newcommand{{\\{name}}}{{{v}}} % {src}")
    for mm, gg in PAIRS:
        pair = f"{mm} vs {gg}"
        for who, other in ((mm, gg), (gg, mm)):
            r = c[(c.pair == pair) & (c.method == who) & (c.stat == "survival5")].iloc[0]
            base = f"custodyCommonSurv{MN[who]}Vs{MN[other]}"
            src = f"decomp_common_chains.csv scope=combined pair='{pair}' method={who} stat=survival5 (hops 2-5 all found, common chains)"
            put(base, p1(r.value), src); put(base + "Lo", p1(r.lo), src + " col=lo"); put(base + "Hi", p1(r.hi), src + " col=hi")
        r = d[(d.table == "common") & (d.marginal == mm) & (d.group_method == gg) & (d.stat == "survival5")].iloc[0]
        base = f"custodyCommonDiff{MN[gg]}Minus{MN[mm]}"
        src = f"decomp_diffs.csv table=common scope=combined marginal={mm} group_method={gg} stat=survival5 (group - marginal, paired)"
        put(base, p1(r["diff"]), src); put(base + "Lo", p1(r.lo), src + " col=lo"); put(base + "Hi", p1(r.hi), src + " col=hi")
    x = d[(d.table == "common") & (d.stat == "cond")]
    assert len(x) == 4 * 4
    put("custodyCommonCondDiffMin", p1(x["diff"].min()), "decomp_diffs.csv table=common scope=combined stat=cond, 4 pairs x j=2..5; min of diff (group - marginal)")
    put("custodyCommonCondDiffMax", p1(x["diff"].max()), "same rows; max of diff")
    # unsigned magnitudes (the sentence states the direction; all common-chain differences are negative)
    sv = d[(d.table == "common") & (d.stat == "survival5")]["diff"]
    assert len(sv) == 4 and (sv < 0).all() and (x["diff"] < 0).all()
    put("ctwoCommonDiffAbsMin", f"{100 * sv.abs().min():.1f}", "decomp_diffs.csv table=common scope=combined stat=survival5, 4 pairs; min of |diff| (all negative: group below marginal)")
    put("ctwoCommonDiffAbsMax", f"{100 * sv.abs().max():.1f}", "same rows; max of |diff|")
    put("ctwoCommonHopDiffAbsMin", f"{100 * x['diff'].abs().min():.1f}", "decomp_diffs.csv table=common scope=combined stat=cond, 4 pairs x j=2..5; min of |diff| (all negative)")
    put("ctwoCommonHopDiffAbsMax", f"{100 * x['diff'].abs().max():.1f}", "same rows; max of |diff|")
    q = a[(a.stat == "cost_ratio_to_static") & a.method.isin(["qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log"])]
    assert len(q) == 5 * 4
    put("custodyReacqHopCostRatioMin", f"{q.value.min():.2f}", "decomp_all_chains.csv scope=combined stat=cost_ratio_to_static, five QR-based methods x j=2..5 (j-th hops of all re-acquisition chains, same hops for every method); min")
    put("custodyReacqHopCostRatioMax", f"{q.value.max():.2f}", "same rows; max")
    L.append(END)
    f = OUT / "custody_numbers.tex"
    txt = f.read_text()
    if BEGIN in txt:
        txt = txt[:txt.index(BEGIN)].rstrip("\n") + "\n" + txt[txt.index(END) + len(END):].lstrip("\n")
    f.write_text(txt.rstrip("\n") + "\n" + "\n".join(L) + "\n")
    print(f"[decomp] {len(L) - 4} macros -> {f}")


if __name__ == "__main__":
    import sys
    numbers() if "--numbers-only" in sys.argv else (main(), numbers())
