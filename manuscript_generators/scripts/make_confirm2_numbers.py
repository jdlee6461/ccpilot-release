"""Generate paper/generated/confirm2_numbers.tex: the \\ctwo... macros of the confirm2 manuscript draft.

    python scripts/make_confirm2_numbers.py          (run from paper/; `make confirm2numbers` does this)

Request list: notes/2026-10-17_confirm2_macros.md (David, 2026-10-17). Rules there and in CLAUDE.md section 9:
  * values come only from the frozen confirm2 result files (results/porto_cctv_confirm2/analysis, h3_sensitivity),
    the frozen analysis configuration, git tag confirm2-plan, and (appendix A only) the held-out seed repetition;
  * pooled 56 days (scope=combined), seed means, conservative bounds over the two cluster types (columns lo, hi);
  * shortfalls in percentage points with one decimal (0.012 -> 1.2), ratios as multiples with two decimals,
    percentages as integers; "range" = min-max over the five targets unless stated otherwise;
  * macros of results/porto_cctv_confirm2/analysis/confirm2_numbers.tex that the manuscript uses by name (\\cTwo...)
    are copied verbatim (value and source comment), not recomputed;
  * every macro carries a comment with its source (file, filter, column, formula, ccpilot commit that last changed
    the source file); generated/confirm2_numbers_manifest.csv lists name, value, raw value, source.
Macros whose result contradicts the manuscript sentence are not written (they stay stub placeholders) and are listed
in MISMATCH for REPORT.md.
"""
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))   # work copy outside ccpilot: CCPILOT_REPO=/home/user/ccpilot
sys.path.insert(0, str(PAPER / "scripts"))
from ch6lib import POSTGAP_HEAD  # noqa: E402
A = "results/porto_cctv_confirm2/analysis"
H3S = "results/porto_cctv_confirm2/h3_sensitivity/h3_sensitivity.csv"
CFG = "configs/confirm2_analysis.yaml"
SEEDS_OLD = "results/porto_cctv_confirm_posthoc/seeds_prereg25/seeds_all.csv"
ONLINE = ["mvp_log", "qr_ogd"]
MARGINAL = ["static", "aci_g0005"]
QR_FAMILY = ["qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log"]
MACROS = []      # (name, text, raw, source)
MISMATCH = []    # (name, computed text, raw, reason)


def commit_of(path):
    out = subprocess.run(["git", "log", "-1", "--format=%h", "--", path], cwd=REPO, capture_output=True, text=True)
    return out.stdout.strip() or "untracked"


def add(name, text, raw, source, path):
    assert (re.fullmatch(r"(ctwo|citytrac)[A-Za-z]+", name) or name in ("candRadiusM", "candRadiusKm")) and name not in {m[0] for m in MACROS}, name
    paths = path if isinstance(path, list) else [path]
    MACROS.append((name, text, raw, source + " | commit " + ", ".join(f"{p} @ {commit_of(p)}" for p in paths)))


def pp(x):
    return f"{100 * x:.1f}"


def r2(x):
    return f"{x:.2f}"


def ipct(x):
    return f"{round(100 * x):d}"


def thou(n):
    return format(int(n), ",").replace(",", "{,}")


def rd(name):
    return pd.read_csv(REPO / A / name)


def main():
    cfg = yaml.safe_load(open(REPO / CFG))
    T = cfg["targets"]
    costs = rd("costs.csv").query("scope == 'combined'")
    main_e = rd("main_estimands.csv").query("scope == 'combined'")
    deficits = rd("deficits.csv")
    ratios = rd("cost_ratios.csv").query("scope == 'combined'")
    gcr = rd("group_cost_ratio_to_static.csv").query("scope == 'combined'")
    inter = rd("intersections.csv").query("scope == 'combined'")
    alt = rd("alt_partitions.csv").query("scope == 'combined' and cell == 'SUMMARY'")
    seedr = rd("seed_range.csv").query("scope == 'combined'")
    reacq = cfg["group_keys"]["reacquired"]

    # ------------------------------------------------------------------ 1. design values
    for blk, nm in (("block1", "One"), ("block2", "Two")):
        n = deficits.query("scope == @blk and cell == @reacq")["n"].unique()
        assert len(n) == 1, n
        add(f"ctwoReacqHopsBlock{nm}", thou(n[0]), int(n[0]),
            f"{A}/deficits.csv: scope={blk}, cell={reacq} (re-acquired); n (hops of the evaluation segment; equal for all "
            f"targets and methods)", f"{A}/deficits.csv")
    days = sum((pd.Timestamp(b["eval"][1]) - pd.Timestamp(b["eval"][0])).days for b in cfg["blocks"].values())
    add("ctwoEvalDays", f"{days:d}", days, f"{CFG}: blocks.*.eval [start, end), sum of days over the two blocks", CFG)
    add("ctwoNumSeeds", f"{len(cfg['seeds']['method']):d}", len(cfg["seeds"]["method"]), f"{CFG}: len(seeds.method)", CFG)
    add("ctwoTargetList", ", ".join(f"{t:.2f}" for t in T), T, f"{CFG}: targets", CFG)
    B = main_e["B"].unique()
    assert len(B) == 1 and int(B[0]) == cfg["bootstrap"]["main"]["B"], B
    add("ctwoBootReps", thou(B[0]), int(B[0]), f"{A}/main_estimands.csv: column B (all rows); = {CFG} bootstrap.main.B",
        [f"{A}/main_estimands.csv", CFG])
    lock = subprocess.run(["git", "rev-list", "-n1", "--abbrev-commit", "confirm2-plan"], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()[:7]
    tagdate = subprocess.run(["git", "for-each-ref", "--format=%(taggerdate:iso)", "refs/tags/confirm2-plan"], cwd=REPO,
                             capture_output=True, text=True).stdout.strip()   # e.g. 2026-10-15 11:53:29 -0400
    d_, hm, tz = tagdate.split()[0], tagdate.split()[1][:5], tagdate.split()[2]
    tz_txt = {"-0400": "EDT (UTC$-$4)", "-0500": "EST (UTC$-$5)"}[tz]
    add("ctwoLockCommit", f"\\texttt{{{lock}}}", lock, "git tag confirm2-plan: tagged commit (git rev-list -n1)", CFG)
    add("ctwoLockTime", f"{d_} {hm} {tz_txt}", tagdate,
        "git tag confirm2-plan: tagger date (git for-each-ref %(taggerdate:iso)), minutes, local time zone of the tagger", CFG)

    # ------------------------------------------------------------------ 2. results
    D = costs.set_index(["method", "target"])
    sub = D.loc[MARGINAL, "D"]
    add("ctwoDbarMarginalMin", pp(sub.min()), sub.min(),
        f"{A}/costs.csv: scope=combined, method in static, aci_g0005, five targets; column D (worst-group shortfall, seed "
        f"mean); min, pp", f"{A}/costs.csv")
    add("ctwoDbarMarginalMax", pp(sub.max()), sub.max(), f"{A}/costs.csv: same rows; max of D, pp", f"{A}/costs.csv")
    allshort = (costs.query("method in @MARGINAL")["target"] - costs.query("method in @MARGINAL")["recall_all"]).abs()
    add("ctwoAllShortMarginalMaxAbs", pp(allshort.max()), allshort.max(),
        f"{A}/costs.csv: scope=combined, method in static, aci_g0005, five targets; max |target - recall_all|, pp",
        f"{A}/costs.csv")
    sub = D.loc[QR_FAMILY, "D"]
    add("ctwoDbarQRFamilyMax", pp(sub.max()), sub.max(),
        f"{A}/costs.csv: scope=combined, method in {', '.join(QR_FAMILY)}, five targets; max of D, pp "
        f"(attained by {sub.idxmax()[0]} at t={sub.idxmax()[1]})", f"{A}/costs.csv")

    E = main_e.set_index(["estimand", "proposed", "comparator", "target"])
    ra = E.loc["reacq_deficit_diff"]
    sub = ra.loc[(ONLINE, MARGINAL), :]
    add("ctwoReacqGainMarginalMin", pp(sub.point.min()), sub.point.min(),
        f"{A}/main_estimands.csv: scope=combined, estimand=reacq_deficit_diff, proposed in mvp_log, qr_ogd, comparator in "
        f"static, aci_g0005, five targets; min of point (D_comparator - D_method), pp", f"{A}/main_estimands.csv")
    add("ctwoReacqGainMarginalMax", pp(sub.point.max()), sub.point.max(),
        f"{A}/main_estimands.csv: same rows; max of point, pp", f"{A}/main_estimands.csv")
    add("ctwoReacqGainMarginalLowerMin", pp(sub.lo.min()), sub.lo.min(),
        f"{A}/main_estimands.csv: same rows; min of lo (99% simultaneous, conservative), pp", f"{A}/main_estimands.csv")
    wd = E.loc["worst_deficit_diff"].loc[(ONLINE, MARGINAL), :]
    k = int((wd["class"] == "improvement").sum())
    add("ctwoDbarGainMarginalCount", f"{k:d}", k,
        f"{A}/main_estimands.csv: scope=combined, estimand=worst_deficit_diff, proposed in mvp_log, qr_ogd, comparator in "
        f"static, aci_g0005, five targets ({len(wd)} cells); count of class == improvement", f"{A}/main_estimands.csv")

    G = gcr.query("method in @ONLINE and group in ['reacquired', 'isolation_q4']")
    cnt = G.assign(ok=G.lo > 1).groupby(["method", "group"]).ok.sum()
    add("ctwoMechCountMin", f"{int(cnt.min()):d}", int(cnt.min()),
        f"{A}/group_cost_ratio_to_static.csv: scope=combined, method in mvp_log, qr_ogd, group in reacquired, "
        f"isolation_q4; per (method, group) number of targets with lo (95%, conservative) > 1; min over (method, group)",
        f"{A}/group_cost_ratio_to_static.csv")
    add("ctwoMechRatioMin", r2(G.cost_ratio_to_static.min()), G.cost_ratio_to_static.min(),
        f"{A}/group_cost_ratio_to_static.csv: same rows (2 methods x 2 groups x 5 targets); min of cost_ratio_to_static",
        f"{A}/group_cost_ratio_to_static.csv")
    add("ctwoMechRatioMax", r2(G.cost_ratio_to_static.max()), G.cost_ratio_to_static.max(),
        f"{A}/group_cost_ratio_to_static.csv: same rows; max of cost_ratio_to_static", f"{A}/group_cost_ratio_to_static.csv")

    def count(prop, comp, cls):
        return int((ra.loc[(prop, comp), "class"] == cls).sum())

    src_cls = (f"{A}/main_estimands.csv: scope=combined, estimand=reacq_deficit_diff, proposed={{p}}, comparator={{c}}, "
               f"five targets; count of class == {{cls}} (99% simultaneous, conservative)")
    k = count("mvp_log", "qr_groups", "worsening")
    add("ctwoWorseCountQrGroupsMvpLog", f"{k:d}", k, src_cls.format(p="mvp_log", c="qr_groups", cls="worsening"),
        f"{A}/main_estimands.csv")
    neg = -ra.loc[("mvp_log", "qr_groups"), "point"]
    for agg in ("Min", "Max"):
        v = neg.min() if agg == "Min" else neg.max()
        add(f"ctwoDiffQrGroupsMvpLog{agg}", pp(v), v,
            f"{A}/main_estimands.csv: scope=combined, estimand=reacq_deficit_diff, proposed=mvp_log, comparator=qr_groups, "
            f"all five targets; {agg.lower()} of -point (= D_mvp_log - D_qr_groups, positive = mvp_log more short), pp",
            f"{A}/main_estimands.csv")
    k = count("qr_ogd", "qr_groups", "undetermined")
    add("ctwoEqualCountQrGroupsQrOgd", f"{k:d}", k, src_cls.format(p="qr_ogd", c="qr_groups", cls="undetermined"),
        f"{A}/main_estimands.csv")
    sub = D.loc["mondrian_hour_hop_speed", "D"]
    add("ctwoDbarMondrianMin", pp(sub.min()), sub.min(),
        f"{A}/costs.csv: scope=combined, method=mondrian_hour_hop_speed, five targets; min of D, pp", f"{A}/costs.csv")
    add("ctwoDbarMondrianMax", pp(sub.max()), sub.max(), f"{A}/costs.csv: same rows; max of D, pp", f"{A}/costs.csv")
    for comp, cn in (("qr_groups_refit7", "RefitSeven"), ("qr_groups_refit", "Refit")):
        for prop, pn in (("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")):
            k = count(prop, comp, "worsening")
            add(f"ctwoWorseCount{cn}{pn}", f"{k:d}", k, src_cls.format(p=prop, c=comp, cls="worsening"),
                f"{A}/main_estimands.csv")
    # v6 VI-D uses one macro for both refits (verdict 16 B4): the two counts must agree
    assert count("mvp_log", "qr_groups_refit", "worsening") == count("mvp_log", "qr_groups_refit7", "worsening")

    def tlist(ts):
        ts = [f"{t:.2f}" for t in ts]
        return ts[0] if len(ts) == 1 else " and ".join(ts) if len(ts) == 2 else ", ".join(ts[:-1]) + ", and " + ts[-1]

    for comp, cls, nm in (("qr_groups_refit7", "improvement", "ctwoQrOgdBetterRefitSevenTargets"),
                          ("qr_groups_refit", "worsening", "ctwoQrOgdWorseRefitTargets")):
        r = ra.loc[("qr_ogd", comp)]
        ts = sorted(r.index[r["class"] == cls])
        assert ts
        add(nm, tlist(ts), ts, src_cls.format(p="qr_ogd", c=comp, cls=cls).replace("count of", "targets with"),
            f"{A}/main_estimands.csv")
    sub = D.loc["static", "D"]
    for agg in ("Min", "Max"):
        v = sub.min() if agg == "Min" else sub.max()
        add(f"ctwoDbarStatic{agg}", pp(v), v,
            f"{A}/costs.csv: scope=combined, method=static, five targets; {agg.lower()} of D, pp", f"{A}/costs.csv")
    # v3: ctwoDiffRefitSeven{Min,Max} deprecated; per-method differences over the targets classified 'worsening'
    for prop, comp, nm in (("mvp_log", "qr_groups_refit7", "ctwoDiffRefitSevenMvpLog"), ("mvp_log", "qr_groups_refit", "ctwoDiffRefitMvpLog"),
                           ("qr_ogd", "qr_groups_refit", "ctwoDiffRefitQrOgd")):
        r = ra.loc[(prop, comp)]
        w = -r.loc[r["class"] == "worsening", "point"]
        assert len(w) > 0
        for agg in ("Min", "Max"):
            v = w.min() if agg == "Min" else w.max()
            add(f"{nm}{agg}", pp(v), v,
                f"{A}/main_estimands.csv: scope=combined, estimand=reacq_deficit_diff, proposed={prop}, comparator={comp}, "
                f"targets with class == worsening ({', '.join(str(x) for x in w.index)}); {agg.lower()} of -point "
                f"(= D_{prop} - D_{comp}, positive = {prop} more short), pp", f"{A}/main_estimands.csv")
    sub = D.loc[["qr_groups_refit", "qr_groups_refit7"], "D"]
    add("ctwoDbarRefitMin", pp(sub.min()), sub.min(),
        f"{A}/costs.csv: scope=combined, method in qr_groups_refit, qr_groups_refit7, five targets; min of D, pp",
        f"{A}/costs.csv")
    add("ctwoDbarRefitMax", pp(sub.max()), sub.max(), f"{A}/costs.csv: same rows; max of D, pp", f"{A}/costs.csv")

    R = ratios.set_index(["method", "reference", "target"]).ratio
    lowT, highT = [t for t in T if t <= 0.95], [t for t in T if t > 0.95]
    for nm, ts in (("Low", lowT), ("High", highT)):
        sub = R.loc[(ONLINE, "H2", ts)] - 1
        for agg in ("Min", "Max"):
            v = sub.min() if agg == "Min" else sub.max()
            add(f"ctwoHTwoExtra{nm}{agg}", ipct(v), v,
                f"{A}/cost_ratios.csv: scope=combined, reference=H2, method in mvp_log, qr_ogd, target in "
                f"{', '.join(map(str, ts))}; {agg.lower()} of (ratio - 1), integer %", f"{A}/cost_ratios.csv")
    # v3: ctwoAllOverMax deprecated (the online methods' overall recall never exceeded the target)
    short = (costs.query("method in @ONLINE").target - costs.query("method in @ONLINE").recall_all)
    assert (short > 0).all()
    add("ctwoAllShortOnlineMax", pp(short.max()), short.max(),
        f"{A}/costs.csv: scope=combined, method in mvp_log, qr_ogd, five targets; max of (target - recall_all), pp "
        f"(all {len(short)} cells positive, min {short.min():.7f})", f"{A}/costs.csv")
    sub = 1 - R.loc[(ONLINE, "H4", T)]
    for agg in ("Min", "Max"):
        v = sub.min() if agg == "Min" else sub.max()
        add(f"ctwoHFourSave{agg}", ipct(v), v,
            f"{A}/cost_ratios.csv: scope=combined, reference=H4, method in mvp_log, qr_ogd, five targets; "
            f"{agg.lower()} of (1 - ratio), integer %", f"{A}/cost_ratios.csv")
    cm = costs.set_index(["method", "target"]).cost_mean
    ct = pd.concat([cm.loc["citytrac_nominal"] / cm.loc[m] for m in ONLINE])
    for agg in ("Min", "Max"):
        v = ct.min() if agg == "Min" else ct.max()
        add(f"ctwoCityTracRatio{agg}", r2(v), v,
            f"{A}/costs.csv: scope=combined, five targets; cost_mean(citytrac_nominal, t) / cost_mean(method, t) for "
            f"method in mvp_log, qr_ogd; {agg.lower()} (reference = the online methods, not H1)", f"{A}/costs.csv")

    for m, mn in (("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")):
        r = deficits.query("scope == 'combined' and cell == @reacq and method == @m")
        assert len(r) == len(T)
        add(f"ctwoReacqShort{mn}Min", pp(r.deficit.min()), r.deficit.min(),
            f"{A}/deficits.csv: scope=combined, cell={reacq}, method={m}, five targets; min of deficit, pp",
            f"{A}/deficits.csv")
        add(f"ctwoReacqShort{mn}Max", pp(r.deficit.max()), r.deficit.max(),
            f"{A}/deficits.csv: same rows; max of deficit, pp", f"{A}/deficits.csv")
        add(f"ctwoReacqShort{mn}UpperMax", pp(r.hi.max()), r.hi.max(),
            f"{A}/deficits.csv: same rows; max of hi (95%, conservative), pp", f"{A}/deficits.csv")

    al = alt.query("method in @ONLINE")
    add("ctwoAltDiffUpperMax", pp(al.diff_hi.max()), al.diff_hi.max(),
        f"{A}/alt_partitions.csv: scope=combined, cell=SUMMARY, method in mvp_log, qr_ogd, six partitions, five targets "
        f"({len(al)} rows); max of diff_hi (partition max shortfall - D, 95% conservative), pp", f"{A}/alt_partitions.csv")
    lg = al[al.diff_lo > 0]
    add("ctwoAltDiffMin", pp(lg.diff_vs_D.min()), lg.diff_vs_D.min(),
        f"{A}/alt_partitions.csv: same rows with diff_lo > 0 (reading 'larger than the 25 groups', {len(lg)} rows); "
        f"min of diff_vs_D, pp", f"{A}/alt_partitions.csv")
    add("ctwoAltDiffMax", pp(lg.diff_vs_D.max()), lg.diff_vs_D.max(),
        f"{A}/alt_partitions.csv: same rows with diff_lo > 0; max of diff_vs_D, pp", f"{A}/alt_partitions.csv")

    I = inter.query("method in @ONLINE").groupby(["method", "target"]).deficit.max()
    add("ctwoInterShortMin", pp(I.min()), I.min(),
        f"{A}/intersections.csv: scope=combined, method in mvp_log, qr_ogd, cells I1-I6; per (method, target) the "
        f"largest deficit over I1-I6; min over (method, target), pp", f"{A}/intersections.csv")
    add("ctwoInterShortMax", pp(I.max()), I.max(),
        f"{A}/intersections.csv: same; max over (method, target) of the largest deficit over I1-I6, pp",
        f"{A}/intersections.csv")
    v = seedr.query("method == 'qr_ogd' and target == 0.9").seed_range_over_ci_width.item()
    add("ctwoQrOgdSeedSpreadRatio", r2(v), v,
        f"{A}/seed_range.csv: scope=combined, method=qr_ogd, target=0.9; seed_range_over_ci_width "
        f"((D_seed_max - D_seed_min) / (hi - lo))", f"{A}/seed_range.csv")

    # ---- v2 additions (request list v2, 2026-10-17 evening)
    sub = R.loc[(ONLINE, "H3", T)]
    for agg in ("Min", "Max"):
        v = sub.min() if agg == "Min" else sub.max()
        add(f"ctwoHThreeOnline{agg}", r2(v), v,
            f"{A}/cost_ratios.csv: scope=combined, reference=H3 (threshold fixed at the full-sample fit), method in mvp_log, "
            f"qr_ogd, five targets; {agg.lower()} of ratio (point estimates)", f"{A}/cost_ratios.csv")
    allm = costs.set_index(["target", "method"]).D.unstack()
    best = allm.idxmin(axis=1)
    k = int(best.isin(["qr_groups_refit", "qr_groups_refit7"]).sum())
    add("ctwoRefitSmallestCount", f"{k:d}", k,
        f"{A}/costs.csv: scope=combined, all {allm.shape[1]} methods; per target the method with the smallest D; number of "
        f"targets where it is qr_groups_refit or qr_groups_refit7 ({dict(best)})", f"{A}/costs.csv")
    nre = deficits.query("scope == 'combined' and cell == @reacq")["n"].unique()
    nall = deficits.query("scope == 'combined' and cell == 'grp_all=0'")["n"].unique()
    assert len(nre) == 1 and len(nall) == 1
    v = nre[0] / nall[0]
    add("ctwoReacqSharePct", f"{100 * v:.1f}", v,
        f"{A}/deficits.csv: scope=combined; n(cell={reacq}) / n(cell=grp_all=0) = {int(nre[0])} / {int(nall[0])}; percent "
        f"with one decimal (an integer would round to 0)", f"{A}/deficits.csv")

    # ---- v3 additions (David, 2026-10-18)
    WORDT = {0.9: "Ninety", 0.93: "NinetyThree", 0.95: "NinetyFive", 0.97: "NinetySeven", 0.98: "NinetyEight"}
    ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth"}
    g25 = deficits.query("scope == 'combined' and family == 'g25' and cell != 'WORST'")
    ranks = {}
    for m in MARGINAL:
        for t in T:
            x = g25.query("method == @m and target == @t").sort_values("deficit", ascending=False).reset_index(drop=True)
            assert len(x) == 25
            ranks[(m, t)] = int(x.index[x.cell == cfg["group_keys"]["isolation_q4"]][0]) + 1
    r95 = sorted({ranks[(m, 0.95)] for m in MARGINAL})
    add("ctwoIsoRankMarginal", " and ".join(ORD[r] for r in r95), r95,
        f"{A}/deficits.csv: scope=combined, family=g25 (25 groups, WORST row excluded), method in static, aci_g0005, "
        f"target=0.95; rank of cell {cfg['group_keys']['isolation_q4']} by deficit (descending), English ordinal (one word "
        f"if both methods agree). All ranks (method, target): {ranks}", f"{A}/deficits.csv")
    BC = f"{A}/block_comparison.csv"
    bc = pd.read_csv(REPO / BC).query("method == 'mondrian_hour_hop_speed'")
    dt = bc.loc[bc.reading != "within sampling uncertainty", "target"].tolist()
    add("ctwoMondrianBlockDiffTargets", " and ".join(f"{t:.2f}" for t in dt) if len(dt) <= 2 else ", ".join(f"{t:.2f}" for t in dt),
        dt, f"{BC}: method=mondrian_hour_hop_speed; targets whose reading is not 'within sampling uncertainty'", BC)
    v = bc[["D_block1", "D_block2"]].min().min()
    add("ctwoDbarMondrianBlockMin", pp(v), v,
        f"{BC}: method=mondrian_hour_hop_speed; min over D_block1, D_block2 and five targets, pp", BC)

    # ---- S2 majority variant (claims_10_8.csv, statement S2), checked against the main_estimands counts
    CL = f"{A}/claims_10_8.csv"
    cl = pd.read_csv(REPO / CL)
    for m, nm in (("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")):
        idx = cl.index[(cl.method == m) & (cl.statement == "S2")]
        assert len(idx) == 1
        det = cl.loc[idx[0], "detail"]
        w = {v: int(re.search(rf"{v}: improvement \d+, worsening (\d+)", det).group(1)) for v in ("refit", "refit7")}
        assert w["refit"] == count(m, "qr_groups_refit", "worsening") and w["refit7"] == count(m, "qr_groups_refit7", "worsening")
        maj = [v for v in ("refit7", "refit") if w[v] >= cfg["estimands"]["claim_majority"]]
        txt = ("both refitted variants" if len(maj) == 2 else
               r"\texttt{qr\_groups\_refit7}" if maj == ["refit7"] else r"\texttt{qr\_groups\_refit}" if maj == ["refit"] else "none")
        add(f"ctwoSTwoMajorityVariant{nm}", txt, maj,
            f"{CL}: row {idx[0] + 2} (file line; header = line 1), method={m}, statement=S2, detail '{det}'; variants with "
            f"worsening >= claim_majority ({cfg['estimands']['claim_majority']}); equal to main_estimands.csv counts",
            [CL, f"{A}/main_estimands.csv"])

    # ---- custody (post hoc, results/porto_cctv_confirm2_posthoc/custody; JD 2026-10-17, David v3 4.1)
    CU = "results/porto_cctv_confirm2_posthoc/custody/custody.csv"
    CAL8 = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit", "qr_groups_refit7",
            "qr_ogd", "mvp_log"]
    cuall = pd.read_csv(REPO / CU, comment="#")
    cu = cuall.query("scope == 'combined' and start == 'all' and h == 5")
    c8 = cu[cu.method.isin(CAL8)]
    assert len(c8) == 8 * len(T)
    p1 = lambda x: f"{100 * x:.1f}"
    for agg in ("Min", "Max"):
        r = c8.loc[c8.custody.idxmin() if agg == "Min" else c8.custody.idxmax()]
        add(f"ctwoCustodyFive{agg}", p1(r.custody), r.custody,
            f"{CU}: POST HOC; scope=combined, start=all, h=5, the eight calibration methods x five targets; {agg.lower()} of "
            f"custody (seed mean), % one decimal (attained by {r.method} at t={r.target})", CU)
    c95 = c8[c8.target == 0.95]
    for agg in ("Min", "Max"):
        r = c95.loc[c95.custody.idxmin() if agg == "Min" else c95.custody.idxmax()]
        add(f"ctwoCustodyFiveCalib{agg}", p1(r.custody), r.custody,
            f"{CU}: POST HOC; scope=combined, start=all, h=5, target=0.95, eight calibration methods; {agg.lower()} "
            f"(attained by {r.method}), % one decimal", CU)
    v = c95.custody.max() - c95.custody.min()
    add("ctwoCustodyFiveCalibDiffMax", p1(v), v,
        f"{CU}: POST HOC; same rows; max - min of custody, percentage points one decimal", CU)
    for m, nm in (("spatula_rule|fixed", "Spatula"), ("citytrac_nominal", "CityTrac")):
        v = cu.query("method == @m and target == 0.95").custody.item()
        add(f"ctwoCustodyFive{nm}", p1(v), v,
            f"{CU}: POST HOC; scope=combined, start=all, h=5, method={m}, target=0.95 (run target; CityTrac at nominal "
            f"0.95; the Spatula-style rule has no target and is identical at every target), % one decimal", CU)
    cs = costs.set_index(["method", "target"]).cost_mean
    for m, nm in (("spatula_rule|fixed", "Spatula"), ("citytrac_nominal", "CityTrac")):
        v = cs.loc[(m, 0.95)] / cs.loc[("static", 0.95)]
        add(f"ctwoCostRatioStatic{nm}", r2(v), v,
            f"{A}/costs.csv: scope=combined; cost_mean({m}, t=0.95) / cost_mean(static, t=0.95)", f"{A}/costs.csv")
    GRP5 = ["qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log"]
    rq = cuall.query("scope == 'combined' and start == 'reacquired' and target == 0.95")
    for nm, k, ms, desc in (("ReacqOneGroup", 1, GRP5, "the five quantile-regression group methods (Mondrian excluded)"),
                            ("ReacqOneMarginal", 1, ["static", "aci_g0005"], "static and ACI"),
                            ("ReacqFive", 5, CAL8, "the eight calibration methods")):
        x = rq[(rq.h == k) & rq.method.isin(ms)]
        assert len(x) == len(ms)
        for agg in ("Min", "Max"):
            r = x.loc[x.custody.idxmin() if agg == "Min" else x.custody.idxmax()]
            add(f"ctwoCustody{nm}{agg}", p1(r.custody), r.custody,
                f"{CU}: POST HOC; scope=combined, start=reacquired, h={k}, target=0.95, {desc}; {agg.lower()} (attained by "
                f"{r.method}), % one decimal", CU)
    x = rq[(rq.h == 5) & rq.method.isin(CAL8)]
    v = x.custody.max() - x.custody.min()
    add("ctwoCustodyReacqFiveDiffMax", p1(v), v,
        f"{CU}: POST HOC; scope=combined, start=reacquired, h=5, target=0.95, eight calibration methods; max - min, "
        f"percentage points one decimal", CU)
    k1 = cuall.query("scope == 'combined' and h == 1 and method == 'mvp_log' and target == 0.95").set_index("start").n_chains
    v = k1["reacquired"] / k1["all"]
    add("ctwoReacqChainSharePct", p1(v), v,
        f"{CU}: scope=combined, h=1 (chains starting in the evaluation segments): n_chains(reacquired) / n_chains(all) = "
        f"{int(k1['reacquired'])} / {int(k1['all'])}, % one decimal (same for every method and target)", CU)

    # ---- held-out re-analysis (plan section 12; handover item 15): counts and S4 status words of both periods
    HA = "results/porto_cctv_heldout_reanalysis/analysis"
    he = pd.read_csv(REPO / HA / "main_estimands.csv").query("scope == 'combined' and estimand == 'reacq_deficit_diff'")
    def hcount(p, c, cls):
        return int(((he.proposed == p) & (he.comparator == c) & (he["class"] == cls)).sum())
    k = hcount("mvp_log", "qr_groups", "undetermined")
    add("ctwoHeldEqualCountQrGroupsMvpLog", f"{k:d}", k,
        f"{HA}/main_estimands.csv: scope=combined, estimand=reacq_deficit_diff, proposed=mvp_log, comparator=qr_groups, "
        f"five targets; count of class == undetermined (99% simultaneous, conservative)", f"{HA}/main_estimands.csv")
    k = hcount("qr_ogd", "qr_groups", "improvement")
    add("ctwoHeldImprovedCountQrGroupsQrOgd", f"{k:d}", k,
        f"{HA}/main_estimands.csv: same rows with proposed=qr_ogd; count of class == improvement", f"{HA}/main_estimands.csv")
    # re-acquisition recall in the held-out re-analysis (S4 qualified sentence of plan 10.8; instruction 05 §2)
    hd = pd.read_csv(REPO / HA / "deficits.csv").query("scope == 'combined' and cell == 'hopkind=2' and target == 0.95")
    for m, nm in (("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")):
        r = hd[hd.method == m]
        assert len(r) == 1
        add(f"ctwoHeldReacqRecall{nm}", r2(r.recall.iloc[0]), r.recall.iloc[0],
            f"{HA}/deficits.csv: scope=combined (held-out period, one block), cell=hopkind=2 (re-acquired), target=0.95, "
            f"method={m}; recall = target - seed-mean deficit = mean over evaluation seeds 0-4 of the group recall "
            f"(n = {int(r.n.iloc[0])} hops), two decimals", f"{HA}/deficits.csv")
    # seed 0 of the same group (verdict 06 §2: the manuscript's appendix A reports seed 0; instruction 06 §2)
    hg = pd.read_csv(REPO / HA / "group_recall.csv").query(
        "scope == 'combined' and group == 'hopkind=2' and target == 0.95 and seed == 0 and method == 'qr_ogd'")
    assert len(hg) == 1
    add("ctwoHeldReacqRecallQrOgdSeedZero", r2(hg.recall.iloc[0]), hg.recall.iloc[0],
        f"{HA}/group_recall.csv: scope=combined (held-out period, one block), group=hopkind=2 (re-acquired), target=0.95, "
        f"method=qr_ogd, evaluation seed 0; recall (n = {int(hg.n.iloc[0])} hops), two decimals", f"{HA}/group_recall.csv")
    # S4 status, verbatim word of the locked judge (claims_10_8.csv status; the parenthetical of 'restrict' dropped)
    for per, path, pre in (("confirmation", f"{A}/claims_10_8.csv", "ctwo"), ("held-out", f"{HA}/claims_10_8.csv", "ctwoHeld")):
        cl4 = pd.read_csv(REPO / path)
        for m, nm in (("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")):
            i4 = cl4.index[(cl4.method == m) & (cl4.statement == "S4")]
            assert len(i4) == 1
            st = cl4.loc[i4[0], "status"].split(" (")[0]
            add(f"{pre}SFourStatus{nm}", st, cl4.loc[i4[0], "status"],
                f"{path}: row {i4[0] + 2} (file line), method={m}, statement=S4 ({per}); status word of the locked judge "
                f"(plan 10.8: 'remains' if the 95% lower bound of the re-acquisition shortfall is above zero at a majority "
                f"of targets, otherwise the restricted wording)", path)

    # ---- v3 final (sec7 implications): recall of later hops (hopkind 0) at target 0.95; not in a request list (see REPORT AM)
    lt = deficits.query("scope == 'combined' and cell == 'hopkind=0' and target == 0.95").set_index("method").recall
    add("ctwoLaterRecallStatic", f"{lt['static']:.3f}", lt["static"],
        f"{A}/deficits.csv: scope=combined, cell=hopkind=0 (later hops), target=0.95, method=static; recall (3 decimals)",
        f"{A}/deficits.csv")
    g5 = lt.loc[["qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log"]]
    for agg in ("Min", "Max"):
        v = g5.min() if agg == "Min" else g5.max()
        add(f"ctwoLaterRecallGroup{agg}", f"{v:.3f}", v,
            f"{A}/deficits.csv: same rows, the five quantile-regression group methods; {agg.lower()} of recall (3 decimals; "
            f"attained by {(g5.idxmin() if agg == 'Min' else g5.idxmax())})", f"{A}/deficits.csv")

    # v3g: one value for the five QR-based methods and their spread (recall scale)
    vals = sorted({f"{v:.3f}" for v in g5})
    assert len(vals) == 1, vals
    add("ctwoLaterRecallGroup", vals[0], list(g5.round(6)),
        f"{A}/deficits.csv: scope=combined, cell=hopkind=0, target=0.95, the five QR-based methods; recall, 3 decimals "
        f"(all five round to the same value)", f"{A}/deficits.csv")
    v = g5.max() - g5.min()
    add("ctwoLaterRecallGroupSpread", f"{v:.3f}", v,
        f"{A}/deficits.csv: same rows; max - min of recall on the recall scale, 3 decimals (raw {v:.5f}; "
        f"{100 * v:.2f} percentage points)", f"{A}/deficits.csv")

    # ---- handover v3h step 4 (read existing results only)
    al = alt.query("method in @ONLINE")
    one = al[al.diff_lo > 0]
    assert len(one) == 1
    r = one.iloc[0]
    PART = {"hour24": "one-hour periods", "hour3": "three-hour periods", "zone8": "eight exit sectors",
            "speed5": "exit-speed quintiles", "entropy5": "branching quintiles", "isolation5": "isolation quintiles"}
    add("ctwoAltDiffCell", rf"{PART[r.family]}, \texttt{{{r.method.replace('_', chr(92) + '_')}}}, target {r.target:.2f}", (r.family, r.method, r.target),
        f"{A}/alt_partitions.csv: scope=combined, cell=SUMMARY, method in mvp_log, qr_ogd; the only row with diff_lo > 0 "
        f"(1 of {len(al)} cells: 2 methods x 6 partitions x 5 targets); family, method, target", f"{A}/alt_partitions.csv")
    granks = {}
    for m, mn in (("static", "Static"), ("aci_g0005", "Aci")):
        for t in T:
            x = g25.query("method == @m and target == @t").sort_values("deficit", ascending=False).reset_index(drop=True)
            rk = int(x.index[x.cell == "entropy_bin=3"][0]) + 1
            granks[(m, t)] = rk
            add(f"ctwoBranchRank{mn}T{WORDT[t]}", ORD[rk], rk,
                f"{A}/deficits.csv: scope=combined, family=g25 (WORST excluded), method={m}, target={t}; rank of entropy_bin=3 "
                f"(branching Q4) by deficit, descending, English ordinal", f"{A}/deficits.csv")
    r95 = sorted({granks[(m, 0.95)] for m in MARGINAL})
    add("ctwoBranchRankMarginal", " and ".join(ORD[x] for x in r95), granks,
        f"{A}/deficits.csv: as ctwoBranchRank*; target 0.95, static and ACI (one word if both agree). All (method, target): {granks}",
        f"{A}/deficits.csv")
    k = hcount("mvp_log", "qr_groups", "improvement")
    add("ctwoHeldImprovedCountQrGroupsMvpLog", f"{k:d}", k,
        f"{HA}/main_estimands.csv: scope=combined, estimand=reacq_deficit_diff, proposed=mvp_log, comparator=qr_groups; count of "
        f"class == improvement (table S18 '1')", f"{HA}/main_estimands.csv")
    # ---- v6 preparation (instruction 12 §1; verdict Shannon01 §A)
    HS = f"{A}/hindsight.csv"
    h1 = pd.read_csv(REPO / HS).query("scope == 'combined' and reference == 'H1'")
    assert len(h1) == len(T) and set(h1.target) == set(T)
    for agg in ("Min", "Max"):
        v = h1.worst_deficit.min() if agg == "Min" else h1.worst_deficit.max()
        add(f"ctwoDbarHOne{agg}", pp(v), v,
            f"{HS}: scope=combined, reference=H1 (hindsight oracle, one global threshold), five targets; {agg.lower()} of "
            f"worst_deficit (worst group {', '.join(sorted(set(h1.worst_group)))}), pp", HS)
    sub = R.loc[(QR_FAMILY, "H2", T)]
    for agg in ("Min", "Max"):
        v = sub.min() if agg == "Min" else sub.max()
        add(f"ctwoHTwoQRFamily{agg}", r2(v), v,
            f"{A}/cost_ratios.csv: scope=combined, reference=H2, method in {', '.join(QR_FAMILY)}, five targets "
            f"({len(sub)} cells); {agg.lower()} of ratio (point estimates; attained by {sub.idxmin()[0] if agg == 'Min' else sub.idxmax()[0]} "
            f"at t={sub.idxmin()[2] if agg == 'Min' else sub.idxmax()[2]})", f"{A}/cost_ratios.csv")
        # instruction 24 §4 (verdict 28 C): extra search over H2 in percent, (ratio - 1) x 100 rounded to an integer
        add(f"ctwoHTwoQRFamilyExtraPct{agg}", f"{round(100 * (v - 1)):d}", 100 * (v - 1),
            f"{A}/cost_ratios.csv: as ctwoHTwoQRFamily{agg}; (ratio - 1) x 100, rounded to an integer, %", f"{A}/cost_ratios.csv")
    # instruction 24 §4: worst-group shortfall of the two online methods under label set (iv), target 0.95, one integer
    RVB = "results/porto_cctv_confirm2_posthoc/review/B_aci_estimates.csv"
    bv = pd.read_csv(REPO / RVB).query("scope == 'combined' and target == 0.95 and estimand == 'D' "
                                         "and method in ['iv_mvp_log', 'iv_qr_ogd']").set_index("method").point
    assert len(bv) == 2 and len({round(100 * x) for x in bv}) == 1, bv
    add("ctwoRevFeedFourOnlineDbarPpAbout", f"{round(100 * bv.mean()):d}", 100 * bv.mean(),
        f"{RVB} (POST HOC): methods iv_mvp_log {100 * bv.iv_mvp_log:.2f}, iv_qr_ogd {100 * bv.iv_qr_ogd:.2f} (label set (iv)), "
        "estimand D, scope combined, target 0.95, seed means; both round to this integer (pp)", RVB)
    # ---- v6 preparation, report 12 results (instruction 13 §2(b)-(e), (g); verdict 14 B). Exploratory inputs are POST HOC.
    IN = f"{A}/intersections.csv"
    it = pd.read_csv(REPO / IN).query("scope == 'combined'")
    o = it[it.method.isin(ONLINE) & it.cell.isin(["I1", "I2", "I4", "I6"])]
    assert len(o) == 2 * 4 * len(T)
    for agg in ("Min", "Max"):
        v = o.deficit.min() if agg == "Min" else o.deficit.max()
        r_ = o.loc[o.deficit.idxmin() if agg == "Min" else o.deficit.idxmax()]
        add(f"ctwoInterOnlineRemain{agg}", pp(v).replace("-", "$-$", 1), v,     # minus as in review_numbers.tex
            f"{IN}: scope=combined, method in mvp_log, qr_ogd, cell in I1, I2, I4, I6, five targets ({len(o)} rows); "
            f"{agg.lower()} of deficit (seed mean), pp (attained by {r_.method}, {r_.cell}, t={r_.target})", IN)
    q4 = it.query("method == 'qr_groups' and cell == 'I4'")
    for agg in ("Min", "Max"):
        v = q4.deficit.min() if agg == "Min" else q4.deficit.max()
        add(f"ctwoInterIFourQrGroups{agg}", pp(v), v,
            f"{IN}: scope=combined, method=qr_groups (without the intersections as groups), cell=I4, five targets; "
            f"{agg.lower()} of deficit, pp", IN)
    IQ = "exploratory/intersections_q/intersections_q.csv"
    iq = pd.read_csv(REPO / IQ, comment="#")
    x6 = iq.query("cell == 'I6' and target == 0.95").set_index("method").deficit
    add("ctwoInterISixQrGroups", pp(x6["qr_groups"]), x6["qr_groups"],
        f"{IQ} (POST HOC exploratory; = {IN}): cell=I6, target=0.95, method=qr_groups; deficit, pp", IQ)
    add("ctwoInterISixQrGroupsPlusI", pp(x6["A3_qr_groups_inter"]), x6["A3_qr_groups_inter"],
        f"{IQ} (POST HOC exploratory; from review/A_intersections.csv): cell=I6, target=0.95, method=A3_qr_groups_inter "
        f"(qr_groups with I1-I6 added as groups); deficit, pp", IQ)
    wq = iq[iq.cell.isin(["I1", "I2", "I6"])].pivot_table(index=["cell", "target"], columns="method", values="deficit")
    worse = wq.A3_qr_groups_inter > wq.qr_groups
    add("ctwoInterWorsenedCount", f"{int(worse.sum()):d}", int(worse.sum()),
        f"{IQ} (POST HOC exploratory): cells I1, I2, I6 x five targets ({len(worse)}); number with deficit of "
        f"A3_qr_groups_inter > deficit of qr_groups (point estimates); not worse: {list(worse.index[~worse])}", IQ)
    add("ctwoInterWorsenedN", f"{len(worse):d}", len(worse), f"{IQ}: denominator of ctwoInterWorsenedCount (3 cells x 5 targets)", IQ)

    QC = "exploratory/qrogd_clip/qrogd_clip.csv"
    qc = pd.read_csv(REPO / QC)
    assert len(qc) == 50 * 25
    pg = qc[qc.group == "hopkind=2"]
    for agg in ("Min", "Max"):
        v = pg.T_G.min() if agg == "Min" else pg.T_G.max()
        add(f"ctwoPostgapTG{agg}", thou(v), int(v),
            f"{QC} (POST HOC exploratory replay, 50 runs = 2 blocks x 5 targets x 5 seeds): group=hopkind=2; {agg.lower()} "
            f"over the runs of T_G (feedback outcomes applied to theta_G in the run's block)", QC)
    for agg in ("Min", "Max"):
        v = pg.bound_3_gT.min() if agg == "Min" else pg.bound_3_gT.max()
        add(f"ctwoPostgapOgdBound{agg}", r2(v), v,
            f"{QC}: group=hopkind=2; {agg.lower()} over the 50 runs of clip / (gamma T_G) (clip 3, gamma 0.005); "
            f"per-block seed means at target 0.95: see exploratory/qrogd_clip/tg_bound.csv", QC)
    th = qc[["theta_min", "theta_max"]].abs().max(axis=1)
    add("ctwoQrOgdThetaAbsMax", f"{th.max():.3f}", th.max(),
        f"{QC}: all 25 groups x 50 runs; max of |theta_G| over the run (max(|theta_min|, |theta_max|)), 3 decimals "
        f"(attained by {qc.loc[th.idxmax(), 'group']}, {qc.loc[th.idxmax(), 'block']}, t={qc.loc[th.idxmax(), 'target']}, "
        f"seed {qc.loc[th.idxmax(), 'seed']})", QC)
    k = int(qc.n_upd_clipped.sum() + qc.n_query_at_bound.sum())
    add("ctwoQrOgdClipHits", f"{k:d}", k,
        f"{QC}: sum over 25 groups x 50 runs of n_upd_clipped (updates where the clip acted) + n_query_at_bound "
        f"(hops queried at |theta_G| = clip)", QC)

    # ---- Gate 8 (instruction 18 §2(e), (g); verdict 21 A): POST HOC exploratory/gate8 and stored analysis outputs
    G8 = "exploratory/gate8"
    add("ctwoLogFloor", r"$10^{-8}$", 1e-8, "ccpilot/multigroup.py:196 qr_group_taus floor=1e-8 (default; evaluate.py:264-265 "
        "passes none), multigroup.py:263 qr_refit_taus log(max(score, 1e-8)): score floor of the QR log scale",
        "ccpilot/multigroup.py")
    cf = pd.read_csv(REPO / G8 / "cal_score_floor.csv", comment="#").query("hopkind == 'all'")
    sh = (cf["n_score_below_1e-8"] / cf.n_cal).to_numpy()
    for agg, v in (("Min", sh.min()), ("Max", sh.max())):
        add(f"ctwoCalFloorSharePct{agg}", f"{100 * v:.1f}", v,
            f"{G8}/cal_score_floor.csv (POST HOC): calibration week, primary predictor; share of calibration hops with "
            f"score < 1e-8, {agg.lower()} over the two blocks (block1 {sh[0]:.5f}, block2 {sh[1]:.5f}), %, one decimal",
            f"{G8}/cal_score_floor.csv")
    ex = pd.read_csv(REPO / G8 / "exit_by_group.csv", comment="#").query("scope == 'combined'").set_index("group")
    for nm, g in (("ctwoExitSharePostgapPct", "hopkind=2"), ("ctwoExitShareIsoQFourPct", "nn_bin=3")):
        v = ex.exit_share[g]
        add(nm, f"{100 * v:.1f}", v, f"{G8}/exit_by_group.csv (POST HOC): scope combined, group {g}; n_exit / n_transitions "
            f"of the evaluation transitions ({int(ex.n_exit[g])} / {int(ex.n_transitions[g])}), %, one decimal",
            f"{G8}/exit_by_group.csv")
    # ---- instruction 22 §3(c) (Shannon13 S5): candidate radius of the confirmation configs and structural misses
    CF2 = "configs/porto_cctv_confirm2.yaml"
    rc = {yaml.safe_load(open(f))["eval"]["candidate_radius_m"] for f in [REPO / CF2] + sorted((REPO / "configs/confirm2").glob("*.yaml"))}
    assert len(rc) == 1, rc
    rcm = rc.pop()
    add("candRadiusM", f"{rcm:g}", 2500, f"{CF2}:40 eval.candidate_radius_m (metres); equal in the ten configs/confirm2/*.yaml",
        CF2)
    # instruction 26 (verdict 30 A5): the same radius in km, as written in IV-A and the caption of Table 1
    add("candRadiusKm", f"{rcm / 1000:g}", rcm / 1000, f"{CF2}:40 eval.candidate_radius_m / 1000 (km); equal in the ten "
        "configs/confirm2/*.yaml", CF2)
    rb = pd.read_csv(REPO / A / "reachable_bound.csv").query("group == 'grp_all=0'").set_index("scope")
    for suf, sc in (("", "combined"), ("BlockOne", "block1"), ("BlockTwo", "block2")):
        n, u = int(rb.n[sc]), float(rb.U_G[sc]); k = round(n * (1 - u))
        assert abs(n * (1 - u) - k) < 1e-6
        src = (f"{A}/reachable_bound.csv: scope {sc}, group grp_all=0 (all evaluation hops, exits excluded), primary predictor; "
               f"structural miss = score <= 0 = no pair of the visibility set in the candidate set (ccpilot/predictors.py "
               f"score(), struct flag), plan 5.4: 1 - U_G")
        add(f"ctwoStructMissSharePct{suf}", f"{100 * (1 - u):.4f}", 1 - u, src + f" = {k} / {n}, %, four decimals", f"{A}/reachable_bound.csv")
        add(f"ctwoStructMissHops{suf}", thou(k), k, src + f"; count n (1 - U_G) = {k} of {n}", f"{A}/reachable_bound.csv")
        add(f"ctwoEvalHops{suf}", thou(n), n, src + "; n (evaluation hops)", f"{A}/reachable_bound.csv")
    # ---- instruction 23 §8 (re-discussion 2026-11-03 #15): overall recall of the two fixed rules at target 0.95, for the
    # footnote of Table 3 once its recall column is left out (same cells as tab_c2_main before, costs.csv recall_all)
    for nm, m in (("ctwoCityTracRecall", "citytrac_nominal"), ("ctwoSpatulaRecall", "spatula_rule|fixed")):
        v = float(costs.query("target == 0.95 and method == @m").recall_all.iloc[0])
        add(nm, f"{v:.3f}", v, f"{A}/costs.csv: scope=combined, target=0.95, method={m}, recall_all (seed mean), three decimals", f"{A}/costs.csv")
    af = pd.read_csv(REPO / G8 / "abs_cost_feedback.csv", comment="#").query("estimand == 'cost_mean'").set_index(
        ["target", "method"]).point
    fr = [af[(t, f"iii_{m}")] / af[(t, m)] for t in T for m in ONLINE]
    for agg, v in (("Min", min(fr)), ("Max", max(fr))):
        add(f"ctwoFeedThreeOnlineCostFrac{agg}", f"{100 * v:.1f}", v,
            f"{G8}/abs_cost_feedback.csv (POST HOC; review B_aci_estimates.csv): cost_mean under label set (iii) / cost_mean "
            f"under full feedback, same method and target, mvp_log and qr_ogd x five targets, scope combined, seed means; "
            f"{agg.lower()}, %, one decimal", f"{G8}/abs_cost_feedback.csv")
    pt = pd.read_csv(REPO / G8 / "postgap_theta.csv", comment="#")
    assert (pt.n_upd_clipped == 0).all()
    v = pt.dev_final.max()
    add("ctwoPostgapRealizedDevMax", r2(v), v,
        f"{G8}/postgap_theta.csv (POST HOC; exploratory/qrogd_clip): qr_ogd, group hopkind=2, 50 runs; max of "
        f"|theta_G,final| / (gamma T_G) = |(1/T_G) sum (err - alpha)| by (7) (clip never acted); two decimals", f"{G8}/postgap_theta.csv")
    g = qc.loc[th.idxmax(), "group"]
    assert g == "nn_bin=2"
    add("ctwoQrOgdThetaAbsMaxGroup", "isolation Q3", g,
        f"{QC}: group attaining ctwoQrOgdThetaAbsMax = {g} (isolation Q3); text as verdict 22 B", QC)
    cp = pd.read_csv(REPO / G8 / "custody_pairs.csv", comment="#").query("method == 'mvp_log' and start == 'reacquired'").iloc[0]
    for suf, v in (("", cp.diff_vs_static), ("Lo", cp.lo), ("Hi", cp.hi)):
        add(f"ctwoCustodyReacqFiveDiffPaired{suf}", f"{100 * v:.2f}".replace("-", "$-$"), v,
            f"{G8}/custody_pairs.csv (POST HOC; custody_diffs.csv @ ea77e49, stored pair {cp.stored_pair}): target 0.95, scope "
            f"combined, h 5, chains starting with a post-gap hop; custody(mvp_log) - custody(static), pp two decimals"
            + ("" if suf == "" else f", conservative 95% {'lower' if suf == 'Lo' else 'upper'} bound (taxi and day, B 2000)"),
            f"{G8}/custody_pairs.csv")
    qd = pd.read_csv(REPO / G8 / "qr_inter_design.csv", comment="#")
    r6 = qd[[c for c in qd.columns if c.startswith("I6_n_sub_s")]].to_numpy()
    for agg, v in (("Min", r6.min()), ("Max", r6.max())):
        add(f"ctwoInterISixCalRows{agg}", f"{int(v):d}", int(v),
            f"{G8}/qr_inter_design.csv (POST HOC): I6 rows in the 80,000-row calibration subsample of qr_groups + I1-I6 "
            f"(seed = evaluation seed 0-4, both blocks), {agg.lower()}", f"{G8}/qr_inter_design.csv")
    me = main_e.query("estimand in ['reacq_deficit_diff', 'isoq4_deficit_diff', 'worst_deficit_diff']")
    cl = me[me["class"] != "undetermined"]
    agree = cl.seed_agreement.str.split("/").str[0].astype(int)
    for nm, k in (("Five", 5), ("Four", 4), ("Three", 3)):
        add(f"ctwoSignAgree{nm}", f"{int((agree == k).sum()):d}", int((agree == k).sum()),
            f"{A}/main_estimands.csv: scope combined, the three estimands x 2 online methods x 6 comparators x 5 targets; "
            f"classified cells (99%, conservative) whose seed_agreement is {k}/5", f"{A}/main_estimands.csv")
    add("ctwoSignAgreeN", f"{len(cl):d}", len(cl), f"{A}/main_estimands.csv: same rows; number of classified cells "
        f"(improvement or worsening) of {len(me)}", f"{A}/main_estimands.csv")
    assert (agree >= 3).all()
    EN = {"reacq_deficit_diff": "Postgap", "isoq4_deficit_diff": "IsoQFour", "worst_deficit_diff": "Dbar"}
    MN = {"mvp_log": "MvpLog", "qr_ogd": "QrOgd"}
    for e, en in EN.items():
        for cls, cn in (("improvement", "Improve"), ("worsening", "Worsen")):
            for m, mn in list(MN.items()) + [(None, "All")]:
                x = me[(me.estimand == e) & (me["class"] == cls) & ((me.proposed == m) if m else True)]
                add(f"ctwoClassCount{en}{mn}{cn}", f"{len(x):d}", len(x),
                    f"{A}/main_estimands.csv: scope combined, estimand {e}, class {cls}, proposed "
                    f"{m or 'mvp_log and qr_ogd'}, 6 comparators x 5 targets", f"{A}/main_estimands.csv")
    add("ctwoClassCountN", f"{len(me[(me.estimand == 'reacq_deficit_diff') & (me.proposed == 'mvp_log')]):d}",
        30, f"{A}/main_estimands.csv: cells per estimand and online method (6 comparators x 5 targets)", f"{A}/main_estimands.csv")

    CA = "exploratory/chain_comp/arithmetic.csv"
    ca = pd.read_csv(REPO / CA, comment="#").query("scope == 'combined'")
    assert len(ca) == 4
    for nm, col, desc in (("ctwoChainSumShare", "S_over_D4", "S / D4, S = sum over hops 2-5 of the conditional recall "
                                                                 "differences, D4 = survival_5 difference"),
                          ("ctwoChainMarginShare", "L4_over_D4", "L4 / D4, L4 = 4 x (difference of recall over all later "
                                                                     "hops)")):
        for agg in ("Min", "Max"):
            v = ca[col].min() if agg == "Min" else ca[col].max()
            add(f"{nm}{agg}", r2(v), v,
                f"{CA} (POST HOC exploratory): scope=combined, target 0.95, common chains of the four pairs (mvp_log, "
                f"qr_groups_refit) x (static, aci_g0005); {agg.lower()} of {desc}", CA)
    CR = "exploratory/chain_comp/recall_state.csv"
    cr = pd.read_csv(REPO / CR, comment="#").query("start == 'every hop' and scope == 'combined' and state == 0").set_index("method").recall
    for m, mn in (("static", "Static"), ("mvp_log", "MvpLog"), ("qr_groups_refit", "Refit")):
        add(f"ctwoFollowOnRecall{mn}", f"{cr[m]:.4f}", cr[m],
            f"{CR} (POST HOC exploratory): start='every hop', scope=combined, state=0 (later hops, hopkind 0), target 0.95, "
            f"method={m}; recall (seed mean), 4 decimals (same quantity as ctwoLaterRecall*, 3 decimals)", CR)

    FW = "exploratory/feedback_iv_worst/feedback_iv_worst.csv"
    fw = pd.read_csv(REPO / FW, comment="#").query("label_set == '(iv)'")
    mt = fw.query("method == 'mvp_log' and worst_group == 'hopkind=2'").target.tolist()
    add("ctwoIvMvpLogPostgapTargets", " and ".join(f"{x:.2f}" for x in mt) if len(mt) <= 2 else ", ".join(f"{x:.2f}" for x in mt),
        mt, f"{FW} (POST HOC exploratory): label_set=(iv), method=mvp_log; targets whose worst group (argmax of the "
            f"seed-mean group deficits) is hopkind=2", FW)
    NM = {"hgroup": ("00--06 h", "06--10 h", "10--16 h", "16--20 h", "20--24 h"),   # en dash (verdict 35 A24)
          "hopkind": ("Later", "Initiated", POSTGAP_HEAD),
          "speed_bin": ("Speed Q1", "Speed Q2", "Speed Q3", "Speed Q4"), "zone": ("Exit E", "Exit N", "Exit W", "Exit S"),
          "entropy_bin": ("Branching Q1", "Branching Q2", "Branching Q3", "Branching Q4"),
          "nn_bin": ("Isolation Q1", "Isolation Q2", "Isolation Q3", "Isolation Q4")}
    gname = lambda c: NM[c.split("=")[0]][int(c.split("=")[1])]
    TL = [f"% GENERATED by scripts/make_confirm2_numbers.py from {FW} @ {commit_of(FW)} (POST HOC exploratory, instruction "
          f"13 §2(e)): worst group under label set (iv) (argmax of the seed-mean deficits over the 25 groups) and its "
          f"deficit in pp; refit (iv) = (ii) refit by construction, run at 0.93 and 0.95 only",
          r"\begin{tabular}{@{}l" + "l" * len(T) + "@{}}", r"\toprule", "Method & " + " & ".join(f"{t:.2f}" for t in T) + r" \\",
          r"\midrule"]
    for disp in ("ACI", "group-wise ACI", "mvp_log", "qr_ogd", "refit"):
        g = fw[fw.method == disp].set_index("target")
        lab = disp.replace("_", r"\_") if disp in ("mvp_log", "qr_ogd") else disp
        lab = rf"\texttt{{{lab}}}" if disp in ("mvp_log", "qr_ogd") else lab
        TL.append(lab + " & " + " & ".join(f"{gname(g.loc[t, 'worst_group'])} ({pp(g.loc[t, 'worst_deficit'])})"
                                            if t in g.index else "--" for t in T) + r" \\")
    TL += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "generated" / "tables" / "tab_iv_worst.tex").write_text("\n".join(TL) + "\n")

    RC = "results/porto_cctv_confirm2/runs/block1/t0950/s0/run_config.yaml"
    wq_ = yaml.safe_load(open(REPO / RC))["eval"]["citytrac"]["window_q"]
    loq = float(re.search(r"lo_q = ([0-9.]+)", (REPO / "ccpilot/predictors.py").read_text()).group(1))
    add("citytracWindowCoverage", r2(wq_ - loq), wq_ - loq,
        f"{RC}: eval.citytrac.window_q ({wq_}) minus lo_q ({loq}) of ccpilot/predictors.py CityTracRule.fit (line 379); "
        f"the factor applied to the accumulated probability (predictors.py:387, 412)", [RC, "ccpilot/predictors.py"])
    for t_, nm in ((0.95, "NinetyFive"), (0.97, "NinetySeven")):
        v = cm.loc[("citytrac_nominal", t_)]
        add(f"citytracCost{nm}", thou(round(v)), v,
            f"{A}/costs.csv: scope=combined, method=citytrac_nominal, target={t_}; cost_mean (camera-seconds per hop, seed "
            f"mean; the rule does not depend on the seed), integer", f"{A}/costs.csv")
    # ---- v6 abstract and conclusion (instruction 14 §1(b)): five-hop custody over all chains, two group methods vs static
    CD = "results/porto_cctv_confirm2_posthoc/custody/custody_diffs.csv"
    cd = pd.read_csv(REPO / CD, comment="#").query("target == 0.95 and scope == 'combined' and h == 5 and start == 'all'")
    cd = cd.set_index(["method_a", "method_b"])["diff"]
    ab = pd.Series({"mvp_log": abs(cd[("mvp_log", "static")]), "qr_groups_refit": abs(cd[("static", "qr_groups_refit")])})
    assert cd[("mvp_log", "static")] < 0 and cd[("static", "qr_groups_refit")] > 0       # both group methods lower
    for agg in ("Min", "Max"):
        v = ab.min() if agg == "Min" else ab.max()
        add(f"ctwoCustodyPairedAllAbs{agg}", pp(v), v,
            f"{CD} (POST HOC): target 0.95, scope combined, h 5, start all, pairs mvp_log-static and static-qr_groups_refit "
            f"(= review_numbers ctwoCustodyPairedAllMvpLog, ...Qrrefit); {agg.lower()} of |diff| (attained by "
            f"{ab.idxmin() if agg == 'Min' else ab.idxmax()}), pp, one decimal", CD)
    # custody macros: copy of the ccpilot post-hoc file into the paper repository (read by main.tex)
    CUN = "results/porto_cctv_confirm2_posthoc/custody/custody_numbers.tex"
    (PAPER / "generated" / "custody_numbers.tex").write_text(
        f"% COPY of ccpilot {CUN} @ {commit_of(CUN)} (POST HOC; written by scripts/make_confirm2_numbers.py) -- DO NOT EDIT\n"
        + (REPO / CUN).read_text())

    # ---- v3h/v3i macros (David 10-19 14:57)
    GNAME = {"entropy_bin=3": "hops from the sites with the most branching (branching Q4)",
             "nn_bin=3": "hops leaving the most isolated sites (isolation Q4)"}
    sec = set()
    for m in MARGINAL:
        x = g25.query("method == @m and target == 0.95").sort_values("deficit", ascending=False).reset_index(drop=True)
        assert x.cell[0] == reacq
        sec.add(x.cell[1])
    assert len(sec) == 1
    c2 = sec.pop()
    add("ctwoSecondWorstGroupMarginal", GNAME[c2], c2,
        f"{A}/deficits.csv: scope=combined, family=g25 (WORST excluded), target=0.95, method in static, aci_g0005; the group "
        f"ranked second by deficit (first: {reacq}); same for both methods", f"{A}/deficits.csv")
    inc0 = int(((al.diff_lo <= 0) & (al.diff_hi >= 0)).sum()); below = int((al.diff_hi < 0).sum()); above = int((al.diff_lo > 0).sum())
    add("ctwoAltCellsEqual", f"{inc0:d}", inc0,
        f"{A}/alt_partitions.csv: scope=combined, cell=SUMMARY, method in mvp_log, qr_ogd; rows whose paired 95% interval "
        f"[diff_lo, diff_hi] contains zero (not distinguished). Of {len(al)}: contains zero {inc0}, entirely below zero "
        f"(smaller than on the 25 groups) {below}, above zero {above}", f"{A}/alt_partitions.csv")
    add("ctwoAltCellsSmaller", f"{below:d}", below,
        f"{A}/alt_partitions.csv: same rows; diff_hi < 0 (partition shortfall smaller than on the 25 groups), of {len(al)}",
        f"{A}/alt_partitions.csv")
    add("ctwoAltCellsN", f"{len(al):d}", len(al), f"{A}/alt_partitions.csv: same rows; 2 methods x 6 partitions x 5 targets",
        f"{A}/alt_partitions.csv")
    add("ctwoAltDiffCellPp", pp(r.diff_vs_D), r.diff_vs_D,
        f"{A}/alt_partitions.csv: the row of ctwoAltDiffCell; diff_vs_D (partition max shortfall - D), pp", f"{A}/alt_partitions.csv")
    DA = "results/porto_cctv_confirm2_posthoc/custody/decomp_all_chains.csv"
    crall = pd.read_csv(REPO / DA, comment="#").query("scope == 'combined' and stat == 'cost_ratio_to_static'")
    for nm, ms, desc in (("ctwoLaterCostRatio", ["qr_groups_refit", "mvp_log"],
                          "the two group methods named in the sentence (mvp_log, qr_groups_refit)"),
                         ("ctwoLaterCostRatioAll", ["qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log"],
                          "all five QR-based methods")):
        cr = crall[crall.method.isin(ms)]
        assert len(cr) == 4 * len(ms)
        for agg in ("Min", "Max"):
            v = cr.value.min() if agg == "Min" else cr.value.max()
            add(f"{nm}{agg}", r2(v), v,
                f"{DA}: POST HOC; scope=combined, target 0.95, stat=cost_ratio_to_static, {desc} x j=2..5 (j-th hops of all "
                f"chains starting with a re-acquisition, same hops for every method); {agg.lower()}", DA)

    S = pd.read_csv(REPO / SEEDS_OLD)
    for m, mn in (("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")):
        s = S.query("method == @m and predictor == 'src_zone_hour_speed'")
        assert sorted(s.seed.unique()) == [0, 1, 2, 3, 4] and len(s) == 10
        v = s.groupby("seed").cost_over_oracle.mean().mean()
        add(f"ctwoOldSeedMeanHOne{mn}", f"{v:.3f}", v,
            f"{SEEDS_OLD}: method={m}, predictor=src_zone_hour_speed, seeds 0-4, segments test_jun_a, test_jun_b; mean "
            f"over seeds of the per-seed mean of cost_over_oracle (post-hoc oracle = H1-type); 3 decimals as in plan "
            f"PLAN_confirm2.md section 6.4", SEEDS_OLD)

    # v11 (verdict 35 A12, instruction 28 §1): counts spelled out where the sentence reads "three of five"
    WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    for base in ("ctwoWorseCountQrGroupsMvpLog", "ctwoEqualCountQrGroupsQrOgd", "ctwoWorseCountRefitMvpLog",
                 "ctwoWorseCountRefitQrOgd"):
        (_, _, raw_, src_), = [m for m in MACROS if m[0] == base]
        MACROS.append((base + "Word", WORDS[raw_], raw_, f"same as {base}, spelled out | commit " + src_.split(" | commit ")[-1]))

    # ------------------------------------------------------------------ verbatim copies of \cTwo macros used by name
    src_tex = (REPO / A / "confirm2_numbers.tex").read_text().splitlines()
    used = sorted({u for f in (PAPER / "sections").glob("*.tex") for u in re.findall(r"\\(cTwo[A-Za-z]+)", f.read_text())})
    copies = []
    for u in used:
        ln = [x for x in src_tex if x.startswith(f"\\newcommand{{\\{u}}}")]
        assert len(ln) == 1, u
        copies.append(ln[0])

    out = ["% AUTO-GENERATED by scripts/make_confirm2_numbers.py -- DO NOT EDIT.",
           "% Request list: notes/2026-10-17_confirm2_macros.md (ccpilot). Pooled 56 days (scope=combined), seed means,",
           "% conservative bounds over the taxi and day clusters. pp = percentage points, one decimal; ratios two decimals;",
           "% percentages integers. Each macro: source file | filter | column | formula | ccpilot commit of the source.", ""]
    for name, text, raw, src in MACROS:
        out.append(f"% {src} | raw {raw}")
        out.append(f"\\newcommand{{\\{name}}}{{{text}\\xspace}}")
    out.append("")
    out.append(f"% Verbatim copies from {A}/confirm2_numbers.tex @ {commit_of(A + '/confirm2_numbers.tex')} "
               "(macros the manuscript uses by their \\cTwo name; value and source comment unchanged)")
    out += copies
    (PAPER / "generated" / "confirm2_numbers.tex").write_text("\n".join(out) + "\n")
    with open(PAPER / "generated" / "confirm2_numbers_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "value", "raw", "source"])
        for name, text, raw, src in MACROS:
            w.writerow([name, text, raw, src])
        for name, text, raw, why in MISMATCH:
            w.writerow([name, "MISMATCH " + text, raw, why])
    print(f"[make_confirm2_numbers] {len(MACROS)} macros + {len(copies)} verbatim copies; mismatches: "
          f"{[m[0] for m in MISMATCH]}")
    for name, text, raw, src in MACROS:
        print(f"  {name:34s} {text:22s} {raw}")


if __name__ == "__main__":
    main()
