"""Chapter 6 table bodies (tabular only) and their data files.

    python scripts/make_tables.py            (run from paper/; `make tables`)

Writes generated/tables/<name>.tex and generated/data/<name>.csv. Deterministic: reruns give identical files.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch6lib as L  # noqa: E402
from ch6lib import (REPO, PAPER, PRED, DIM_NAME, DIMS25, LEVEL_NAME, METHODS, MLATE, STYLE, write_csv, write_tex, f1, f2, f3, fi)  # noqa: E402

ATTRS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
LAYOUTS = [("virtual", "Virtual", {1: "results/porto", 2: "results/porto_rep"}),
           ("real", "Real CCTV", {1: "results/porto_cctv", 2: "results/porto_cctv_rep"})]
HOPKIND_LEVEL = {"later": 0, "first(trip)": 1, "first(resume)": 2}


# ---------------------------------------------------------------- step 0: layout dependence of the failure factors
def layout_spread(d):
    """Static recall per attribute level, pooled over the test segments of one exploratory period.

    Source: factors/univariate_miss_static.csv (factor_analysis.py; static = split conformal, primary predictor).
    The stored group table conditional_coverage.csv lacks entropy_bin/nn_bin for the virtual layout; where both
    files have a level, recall and n are checked to agree exactly.
    """
    U = pd.read_csv(REPO / d / "factors/univariate_miss_static.csv")
    U = U[U.factor.isin(ATTRS)].copy()
    U["level"] = U.level.replace(HOPKIND_LEVEL).astype(float).astype(int)
    U["recall"] = 1 - U.miss_rate
    C = pd.read_csv(REPO / d / "conditional_coverage.csv")
    C = C[(C.predictor == PRED) & (C.method == "static") & C.dim.isin(ATTRS)].copy()
    C["hits"] = C.coverage * C.n
    P = C.groupby(["dim", "group"])[["hits", "n"]].sum().reset_index()
    P["recall"] = P.hits / P.n
    M = P.merge(U, left_on=["dim", "group"], right_on=["factor", "level"], suffixes=("_c", "_u"))
    assert len(M) == len(P) and (M.n_c == M.n_u).all() and np.allclose(M.recall_c, M.recall_u, atol=1e-12, rtol=0)
    assert (U.n >= 200).all()
    return U, sorted(P.dim.unique())


def tab_layout_factors():
    rows, srcs, notes = [], [], []
    for lk, lname, per in LAYOUTS:
        for p, d in per.items():
            U, in_cc = layout_spread(d)
            srcs += [f"{d}/factors/univariate_miss_static.csv", f"{d}/conditional_coverage.csv"]
            for a in ATTRS:
                u = U[U.factor == a]
                rows.append({"layout": lk, "period": p, "attribute": a, "n_levels": len(u), "min_level_n": int(u.n.min()),
                             "recall_min": u.recall.min(), "recall_max": u.recall.max(),
                             "spread_pp": 100 * (u.recall.max() - u.recall.min()),
                             "in_conditional_coverage": a in in_cc})
    D = pd.DataFrame(rows)
    write_csv(D, "tab_layout_factors", sorted(set(srcs)), "exploratory",
              "appendix; the two layouts have different hop sets (different cameras); values = max - min of static recall "
              "across the levels of each attribute (pp). static (split conformal), predictor src_zone_hour_speed, exploratory periods 1 (test_same+test_holiday) and "
              "2 (test_mar+test_easter+test_apr) pooled per period; spread = max - min recall over the levels of an attribute "
              "(all levels n >= 200); attribute levels identical to the 25-group definition")
    head = " & ".join(f"{lname} {p}" for _, lname, per in LAYOUTS for p in per)
    lines = ["\\begin{tabular}{lrrrr}", "\\toprule",
             "& \\multicolumn{2}{c}{Synthetic layout} & \\multicolumn{2}{c}{Real CCTV layout} \\\\",
             "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
             "Attribute & Period 1 & Period 2 & Period 1 & Period 2 \\\\", "\\midrule"]
    for a in ATTRS:
        vals = [D[(D.layout == lk) & (D.period == p) & (D.attribute == a)].spread_pp.iloc[0] for lk, _, per in LAYOUTS for p in per]
        lines.append(f"{DIM_NAME[a]} & " + " & ".join(f1(v) for v in vals) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_layout_factors")
    return D


# ---------------------------------------------------------------- step 1: labels shared by all tables and figures
def group_labels():
    """Short English group names (proposal; David confirms). Order: all, time of day, track state, exit speed,
    exit zone, branching, isolation."""
    rows = []
    for d in DIMS25:
        for g, nm in LEVEL_NAME[d].items():
            rows.append({"order": len(rows) + 1, "dim": d, "group": g, "key": f"{d}={g}", "attribute": DIM_NAME[d], "label": nm})
    write_csv(pd.DataFrame(rows), "group_labels", ["ccpilot/evaluate.py", "ccpilot/events.py", "configs/porto_cctv_confirm.yaml"],
              "main", "definitions: hgroup edges [0,6,10,16,20,24] h (config); hopkind 0 later / 1 first hop of a trip / "
              "2 first hop after re-acquisition (evaluate.py); zone 0=E 1=N 2=W 3=S sector of the exit point (events.py); "
              "speed_bin, entropy_bin (branching), nn_bin (distance to nearest camera = isolation) are training-period quartiles")
    M = pd.DataFrame([{"order": i + 1, "key": k, "label": lab.replace("\\_", "_"), "added_after_main": MLATE[k],
                       "color": STYLE[k][0], "marker": STYLE[k][1]} for i, (k, lab, _, _) in enumerate(METHODS)])
    write_csv(M, "method_styles", ["paper/scripts/ch6lib.py"], "main", "method order, colour (Okabe-Ito) and marker used in every table and figure")


# ---------------------------------------------------------------- step 2: Table 1 and appendix worst groups
SEEDS_CRIT = L.PH + "/seeds_prereg25/seeds_criteria.csv"
SEED_LABEL = {"spatula": "spatula_rule/fixed", "citytrac095": "citytrac_rule/target095",
              "citytrac099": "citytrac_rule/target099", "static": "static", "mondrian": "mondrian_hour_hop_speed",
              "aci": "aci_g0005", "mvp_log": "mvp_log", "mvp_global": "mvp_global", "qr_groups": "qr_groups",
              "qr_ogd": "qr_ogd", "oracle": "oracle(post-hoc)"}          # mvp_groups was not in the seed runs


_HELD = {}
SEEDS_ALL = L.PH + "/seeds_prereg25/seeds_all.csv"
SUMMARY_KEY = {"spatula": ("spatula_rule", "fixed"), "static": (PRED, "static"), "aci": (PRED, "aci_g0005"),
               "mondrian": (PRED, "mondrian_hour_hop_speed"), "qr_groups": (PRED, "qr_groups"), "mvp_groups": (PRED, "mvp_groups"),
               "mvp_global": (PRED, "mvp_global"), "qr_ogd": (PRED, "qr_ogd"), "mvp_log": (PRED, "mvp_log"),
               "oracle": (PRED, "oracle(post-hoc)")}


def summary_cost(k, seg):
    """Mean cost (camera-seconds per hop) from the stored summaries: frozen confirmation summary; the CityTrac-style
    rule (added later) from the seed-0 row of the seed runs. hits.parquet stores float32 costs, so its mean differs
    in the 5th significant digit."""
    if k.startswith("citytrac"):
        A = pd.read_csv(REPO / SEEDS_ALL)
        return A[(A.seed == 0) & (A.label == f"citytrac_rule/target0{k[-2:]}") & (A.segment == seg)].cost_mean_cam_s.iloc[0]
    F = pd.read_csv(REPO / L.HELD_SUMMARY)
    pr, me = SUMMARY_KEY[k]
    return F[(F.predictor == pr) & (F.method == me) & (F.segment == seg)].cost_mean_cam_s.iloc[0]


def held_rows():
    """Per method and segment: recall, worst group, counts below 0.94 / 0.95, cost ratio (held-out, seed 0)."""
    if "rows" in _HELD:
        return _HELD["rows"], _HELD["groups"]
    H = L.load_held()
    oc = L.held_oracle_cost()
    rows, groups = [], []
    for k in L.MKEYS:
        for seg, sn in L.SEGS:
            m = (H.seg == seg).to_numpy()
            G = L.group_table(H, L.hitcol(k), m)
            S = L.summarize(G)
            cost = summary_cost(k, seg)
            assert abs(cost - (oc[seg] if k == "oracle" else H.loc[m, L.costcol(k)].mean())) < 1e-3 * cost   # hits store float32 costs
            rows.append({"method": k, "segment": seg, "seg": sn, "n": int(m.sum()), "recall": H.loc[m, L.hitcol(k)].mean(),
                         "cost_cam_s": cost, "oracle_cost_cam_s": oc[seg], "cost_ratio": cost / oc[seg], **S})
            groups.append(G.assign(method=k, segment=seg))
    C = pd.read_csv(REPO / SEEDS_CRIT)
    seeds = C.groupby("label").C1.agg(["sum", "size"])
    R = pd.DataFrame(rows)
    R["seeds_c1"] = R.method.map(lambda k: seeds.loc[SEED_LABEL[k], "sum"] if k in SEED_LABEL else np.nan)
    R["seeds_n"] = R.method.map(lambda k: seeds.loc[SEED_LABEL[k], "size"] if k in SEED_LABEL else np.nan)
    _HELD["rows"], _HELD["groups"] = R, pd.concat(groups, ignore_index=True)
    return _HELD["rows"], _HELD["groups"]


def tab_main():
    R, _ = held_rows()
    write_csv(R, "tab_main", [L.HELD_HITS, L.HELD_SUMMARY, SEEDS_ALL, SEEDS_CRIT], "main",
              "held-out period, evaluation seed 0, 25-group definition, groups judged if n >= 200; 95% Wilson; "
              "cost ratio = mean cost / hindsight-oracle mean cost of the primary predictor, same segment (also for "
              "Spatula-/CityTrac-style); mean costs from the frozen summary (CityTrac-style: seeds_all.csv seed 0); oracle hits reconstructed from stored scores (recall equals frozen summary); "
              "seeds = evaluation seeds 0-4 meeting the group criterion (no group significantly below 0.94 in A and B); "
              "mvp_groups was not part of the seed runs (--); hindsight oracle: -- (a reference, not a method). "
              "Evaluation-seed invariance (checked in seeds_all.csv, seeds 0-4: identical recall, worst group, cost, counts): "
              "static, Mondrian, Spatula-style, CityTrac-style (0.95, 0.99) and the hindsight oracle do not change with the "
              "seed; ACI, qr_ogd, mvp_log, mvp_global and qr_groups do (qr_groups: its calibration subsample of 80,000 "
              "hops is drawn with the evaluation seed, multigroup.qr_group_taus)")
    lines = ["\\begin{tabular}{l rrrrr rrrrr r}", "\\toprule",
             "& \\multicolumn{5}{c}{Segment A} & \\multicolumn{5}{c}{Segment B} & \\\\",
             "\\cmidrule(lr){2-6}\\cmidrule(lr){7-11}",
             "Method & Recall & Worst & $<$0.94 & $<$0.95 & Cost & Recall & Worst & $<$0.94 & $<$0.95 & Cost & Seeds \\\\",
             "\\midrule"]
    for k in L.MKEYS:
        cells = []
        for sn in ["A", "B"]:
            r = R[(R.method == k) & (R.seg == sn)].iloc[0]
            cells += [f3(r.recall), f3(r.worst), fi(r.below94), fi(r.below95), f2(r.cost_ratio)]
        r0 = R[R.method == k].iloc[0]
        cells.append("--" if np.isnan(r0.seeds_c1) or k == "oracle" else f"{int(r0.seeds_c1)}/{int(r0.seeds_n)}")
        lines.append(L.tex_label(k) + " & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_main")


def tab_worst_groups():
    R, _ = held_rows()
    W = R[["method", "segment", "seg", "worst_key", "worst_name", "worst", "worst_n", "worst_lo", "worst_ub", "n_groups_judged"]]
    write_csv(W, "tab_worst_groups", [L.HELD_HITS, L.HELD_SUMMARY], "main",
              "held-out period, evaluation seed 0, 25-group definition; worst = lowest recall among groups with n >= 200; 95% Wilson")
    lines = ["\\begin{tabular}{l lrrc lrrc}", "\\toprule",
             "& \\multicolumn{4}{c}{Segment A} & \\multicolumn{4}{c}{Segment B} \\\\",
             "\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}",
             "Method & Group & Recall & $n$ & 95\\% CI & Group & Recall & $n$ & 95\\% CI \\\\", "\\midrule"]
    for k in L.MKEYS:
        cells = []
        for sn in ["A", "B"]:
            r = W[(W.method == k) & (W.seg == sn)].iloc[0]
            cells += [r.worst_name, f3(r.worst), f"{int(r.worst_n):,}".replace(",", "{,}"), f"[{f3(r.worst_lo)}, {f3(r.worst_ub)}]"]
        lines.append(L.tex_label(k) + " & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_worst_groups")


# ---------------------------------------------------------------- Table 2: ablation of the threshold scale
ABL = {1: "results/porto_cctv_posthoc/scale_ablation/scale_ablation_summary.csv",
       2: "results/porto_cctv_rep_posthoc/scale_ablation/scale_ablation_summary.csv"}
ABL_ROWS = [("unif_nocap", "Uniform", "UnifNoCap"),
            ("unif_cap002", "Uniform + bound", "UnifCap"),
            ("mvp_log", "Log + bound (mvp\\_log)", "LogCap"),
            ("log_cap1e6_m89", "Log, no bound$^{a}$", "LogNoCapMatched"),
            ("log_cap001", "$a_{\\min}=0.001$", "LogCapLow"),
            ("log_cap005", "$a_{\\min}=0.005$", "LogCapHigh")]


def tab_ablation():
    import csv
    man = {r["macro"]: float(r["raw"]) for r in csv.DictReader(open(PAPER / "generated/numbers_manifest.csv"))}
    rows = []
    for meth, lab, mac in ABL_ROWS:
        r = {"variant": meth, "label": lab}
        for p, f in ABL.items():
            T = pd.read_csv(REPO / f)
            T = T[(T["mode"] == "normal") & (T.method == meth)]
            r[f"cost_ratio_p{p}"] = T.cost_over_oracle.mean()
            r[f"segments_failed_p{p}"] = int((T["n_sig_below_0.94"] > 0).sum())
            r[f"segments_p{p}"] = len(T)
        r["cost_ratio_mean"] = (r["cost_ratio_p1"] + r["cost_ratio_p2"]) / 2
        r["macro_mean"] = man[f"abl{mac}RatioMean"]
        assert abs(r["cost_ratio_mean"] - r["macro_mean"]) < 1e-9, (meth, r["cost_ratio_mean"], r["macro_mean"])
        rows.append(r)
    D = pd.DataFrame(rows)
    write_csv(D, "tab_ablation", list(ABL.values()), "additional",
              "exploratory periods 1 (test_same, test_holiday) and 2 (test_mar, test_apr, test_easter), no outage "
              "(mode=normal), evaluation seed 0; cost ratio = mean over segments of cost / hindsight oracle; failed = "
              "segments with at least one group significantly below 0.94 (25-group definition, n >= 200); "
              "mean column equals the 4th-chapter macros abl*RatioMean exactly; table note a = matched resolution "
              "(m = 89, log_cap1e6_m89)")
    lines = ["\\begin{tabular}{@{}l rr rr r@{}}", "\\toprule",
             "& \\multicolumn{2}{c}{Period 1} & \\multicolumn{2}{c}{Period 2} & \\\\",
             "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
             "Scale & Cost & Fail & Cost & Fail & Mean \\\\", "\\midrule"]
    for _, r in D.iterrows():
        lines.append(f"{r.label} & {f2(r.cost_ratio_p1)} & {r.segments_failed_p1}/{r.segments_p1} & "
                     f"{f2(r.cost_ratio_p2)} & {r.segments_failed_p2}/{r.segments_p2} & {f2(r.cost_ratio_mean)} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_ablation")


# ---------------------------------------------------------------- Table 3: sensitivity (held-out, seed 0)
SENS = L.PH + "/sensitivity_summary.csv"
SENS_FB = [("fb010", "10\\%, delayed"), ("fb030", "30\\%, delayed"), ("fb100", "100\\%, delayed"),
           ("fb100_nodelay", "100\\%, immediate")]          # 10% / 30% immediate were never run
SENS_DET = [("det095", "0.95", "0.95"), ("det095_adj", "0.95", "adj."), ("det090", "0.90", "0.95"), ("det090_adj", "0.90", "adj.")]
SENS_METH = {"mvp_log": "mvp_log", "static": "static"}


def groups25_from_tables(sc, meth, seg):
    """25-group statistics of a sensitivity run without hop-level results: the six attributes from the run's
    conditional_coverage.csv (n, recall) and the all-hops group from the summary; hits = recall * n (exact integers).
    Checked on fb030 (= pre-registered setting) against the hop-level results: identical."""
    S = pd.read_csv(REPO / SENS)
    sr = S[(S.scenario == sc) & (S.predictor == PRED) & (S.method == meth) & (S.segment == seg)].iloc[0]
    C = pd.read_csv(REPO / f"{L.PH}/{sc}/conditional_coverage.csv")
    c = C[(C.predictor == PRED) & (C.method == meth) & (C.segment == seg) & C.dim.isin(L.DIMS25)]
    D = pd.DataFrame([("grp_all", 0, sr.n, sr.coverage)] + list(zip(c.dim, c.group, c.n, c.coverage)),
                     columns=["dim", "group", "n", "recall"])
    D["k"] = np.rint(D.recall * D.n)
    assert len(D) == 25 and np.allclose(D.k / D.n, D.recall, atol=1e-12, rtol=0)
    D["ub95"] = L.wilson(D.k, D.n)[1]
    J = D[D.n >= L.MIN_N]
    return {"worst": J.recall.min(), "below94": int((J.ub95 < 0.94).sum()), "below95": int((J.ub95 < 0.95).sum()),
            "recall": sr.coverage, "recall_detected": sr.coverage_detected, "cost_ratio": sr.cost_over_oracle,
            "target_used": sr.target_used, "cost_cam_s": sr.cost_mean_cam_s,
            "cost_ratio_clean_oracle": sr.cost_mean_cam_s / L.held_oracle_cost()[seg]}


def tab_sensitivity():
    rows = []
    for sc, lab in SENS_FB:
        r = {"part": "feedback", "scenario": sc or "not run", "label": lab, "method": "mvp_log"}
        for seg, sn in L.SEGS:
            g = groups25_from_tables(sc, "mvp_log", seg) if sc else {}
            for k in ["worst", "below94", "below95", "recall", "cost_ratio"]:
                r[f"{k}_{sn}"] = g.get(k, np.nan)
        rows.append(r)
    for meth in SENS_METH:
        for sc, pdet, tgt in SENS_DET:
            r = {"part": "detection", "scenario": sc, "label": f"{pdet} & {tgt}", "method": meth, "p_det": float(pdet)}
            for seg, sn in L.SEGS:
                g = groups25_from_tables(sc, meth, seg)
                for k in ["worst", "below94", "below95", "recall", "recall_detected", "cost_ratio", "target_used",
                          "cost_cam_s", "cost_ratio_clean_oracle"]:
                    r[f"{k}_{sn}"] = g[k]
            rows.append(r)
    D = pd.DataFrame(rows)
    D["cost_ratio_mean"] = (D.cost_ratio_A + D.cost_ratio_B) / 2
    D["cost_ratio_clean_oracle_mean"] = (D.cost_ratio_clean_oracle_A + D.cost_ratio_clean_oracle_B) / 2
    srcs = [SENS] + [f"{L.PH}/{sc}/conditional_coverage.csv" for sc, _ in SENS_FB if sc] + [f"{L.PH}/{sc}/conditional_coverage.csv" for sc, *_ in SENS_DET]
    write_csv(D, "tab_sensitivity", srcs, "additional",
              "held-out period, evaluation seed 0, posthoc_sensitivity.py; 25-group statistics rebuilt from each run's "
              "conditional_coverage.csv + summary (no hop-level results were saved; method checked on fb030); "
              "feedback 10%/30% without delay were never run and are not in the table; recall = true-location recall. "
              "Cost column: (a) feedback: stored cost_over_oracle (hindsight oracle of the same run and segment; the oracle "
              "does not depend on feedback, so this equals the no-error oracle), mean of A and B; (b) detection errors: "
              "cost_ratio_clean_oracle = mean cost / mean cost of the hindsight oracle of the run WITHOUT detection errors "
              "(frozen confirmation summary, primary predictor, same segment), mean of A and B, for both the unadjusted and "
              "the adjusted target; cost_ratio (same-run oracle) kept for reference only")
    lines = ["\\begin{tabular}{l rr rr r}", "\\toprule",
             "\\multicolumn{6}{l}{\\emph{(a) Feedback, mvp\\_log}} \\\\",
             "& \\multicolumn{2}{c}{Worst group} & \\multicolumn{2}{c}{$<$0.94} & \\\\",
             "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
             "Fraction, delay & A & B & A & B & Cost \\\\", "\\midrule"]
    for _, r in D[D.part == "feedback"].iterrows():
        lines.append(f"{r.label} & {f3(r.worst_A)} & {f3(r.worst_B)} & {fi(r.below94_A)} & {fi(r.below94_B)} & {f2(r.cost_ratio_mean)} \\\\")
    lines += ["\\midrule", "\\multicolumn{6}{l}{\\emph{(b) Detection errors}} \\\\",
              "& \\multicolumn{2}{c}{Recall (true)} & \\multicolumn{2}{c}{Worst group} & \\\\",
              "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
              "$p_{\\mathrm{det}}$, target & A & B & A & B & Cost \\\\"]
    for meth in SENS_METH:
        lines.append("\\midrule")
        lines.append(f"\\multicolumn{{6}}{{l}}{{{L.MLABEL[meth]}}} \\\\")
        for _, r in D[(D.part == "detection") & (D.method == meth)].iterrows():
            lab = r.label.replace(" & ", ", ")
            lines.append(f"{lab} & {f3(r.recall_A)} & {f3(r.recall_B)} & {f3(r.worst_A)} & {f3(r.worst_B)} & {f2(r.cost_ratio_clean_oracle_mean)} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_sensitivity")


# ---------------------------------------------------------------- Table 4 and appendix: camera outages
OUT_ALL = L.PH + "/outage_suite/all_periods_summary.csv"
OUT_METH = [("static", "static"), ("aci_g0005", "aci"), ("qr_ogd", "qr_ogd"), ("mvp_log", "mvp_log")]
OUT_SCEN = [("rand10", "Random 10\\%"), ("rand20", "Random 20\\%"), ("rand30", "Random 30\\%"), ("region_fixed", "Region (20 sites)")]
OUT_PRED = [("src_zone_hour_speed", "base"), ("src_zone_hour_speed_oa", "outage-aware")]
PRED_SHORT = {"base": "base", "outage-aware": "aware"}
PERIOD_NAME = {"porto_cctv_confirm": "held-out period", "porto_cctv": "exploratory period 1", "porto_cctv_rep": "exploratory period 2"}


def outage_table(period, segment, name):
    A = pd.read_csv(REPO / OUT_ALL)
    A = A[(A.period == period) & (A.segment == segment)]
    rows = []
    for sc, slab in OUT_SCEN:
        for pred, plab in OUT_PRED:
            r = {"scenario": sc, "predictor": plab, "label_scenario": slab}
            for meth, key in OUT_METH:
                g = A[(A.scenario == sc) & (A.predictor == pred) & (A.method == meth)]
                r[f"n_site_seeds_{key}"] = g.site_seed.nunique()
                r[f"site_seeds_{key}"] = " ".join(str(x) for x in sorted(g.site_seed.unique()))
                r[f"recall_{key}"] = g.coverage.mean()
                r[f"below94_{key}"] = g["n_sig_below_0.94"].mean()
                r[f"cost_ratio_none_{key}"] = g.cost_over_oracle_none.mean()
            rows.append(r)
    D = pd.DataFrame(rows)
    write_csv(D, name, [OUT_ALL], "additional",
              f"{PERIOD_NAME[period]}, segment {segment} (B_early = first 48 h after the outage start, B_late = after), "
              "evaluation seed 0; random outages: mean over site seeds 1,2,3,4,7; region_fixed: single draw (site seed 7, "
              "20 fixed sites); 25-group definition, n >= 200; below94 = groups significantly below 0.94 (seed mean); "
              "cost ratio = mean cost / hindsight-oracle cost of the base predictor in the no-outage run, same period and segment")
    lines = ["\\begin{tabular}{@{}ll " + " ".join(["rrr"] * len(OUT_METH)) + "@{}}", "\\toprule",
             "& & " + " & ".join(f"\\multicolumn{{3}}{{c}}{{{L.MLABEL[k]}}}" for _, k in OUT_METH) + " \\\\",
             "".join(f"\\cmidrule(lr){{{3 + 3 * i}-{5 + 3 * i}}}" for i in range(len(OUT_METH))),
             "Outage & Pred. & " + " & ".join(["Recall & $<$0.94 & Cost"] * len(OUT_METH)) + " \\\\", "\\midrule"]
    for i, (_, r) in enumerate(D.iterrows()):
        cells = []
        for _, k in OUT_METH:
            single = r[f"n_site_seeds_{k}"] == 1
            cells += [f3(r[f"recall_{k}"]), fi(r[f"below94_{k}"]) if single else f1(r[f"below94_{k}"]), f2(r[f"cost_ratio_none_{k}"])]
        lab = r.label_scenario if i % 2 == 0 else ""
        lines.append(f"{lab} & {PRED_SHORT[r.predictor]} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), name)
    return D


# ---------------------------------------------------------------- step 3: appendix tables (all "additional")
CEIL_SCEN = ["rand10", "rand30"]
CEIL_SEEDS = [1, 2, 3, 4, 7]
A_MIN = 0.002


def tab_ceiling():
    """Per group: share of B_late hops whose true-target score is below tau_min (q = 1 at a_min = 0.002)."""
    rows, srcs = [], []
    for sc in CEIL_SCEN:
        for sd in CEIL_SEEDS:
            f = f"{L.PH}/outage_suite/{sc}_s{sd}/hits.parquet"
            srcs.append(f)
            H = pd.read_parquet(REPO / f)
            H = H[H.segment == "B_late"]
            for pred, plab in OUT_PRED:
                below = (H[f"score|{pred}"] < H[f"taumin{A_MIN:g}|{pred}"].iloc[0]).astype(int)
                for d in L.DIMS25:
                    for g, gg in below.groupby(H[d]):
                        rows.append({"scenario": sc, "site_seed": sd, "predictor": plab, "dim": d, "group": int(g),
                                     "key": L.group_key(d, g), "name": L.group_name(d, g), "n": len(gg), "p_below": gg.mean()})
    R = pd.DataFrame(rows)
    # check: the all-hops share equals 1 - ceiling_0.002 of the outage summary
    A = pd.read_csv(REPO / OUT_ALL)
    A = A[(A.period == "porto_cctv_confirm") & (A.segment == "B_late") & (A.method == "mvp_log")]
    for _, r in R[R.dim == "grp_all"].iterrows():
        pred = dict((b, a) for a, b in OUT_PRED)[r.predictor]
        c = A[(A.scenario == r.scenario) & (A.site_seed == r.site_seed) & (A.predictor == pred)]["ceiling_0.002"].iloc[0]
        assert abs((1 - c) - r.p_below) < 1e-12, (r.scenario, r.site_seed, r.predictor)
    M = R.groupby(["scenario", "predictor", "dim", "group", "key", "name"], sort=False).agg(
        p_below_mean=("p_below", "mean"), p_below_min=("p_below", "min"), p_below_max=("p_below", "max"),
        n_mean=("n", "mean")).reset_index()
    M["over_alpha"] = M.p_below_mean > 0.05
    write_csv(M, "tab_ceiling", srcs + [OUT_ALL], "additional",
              "held-out period, B_late, evaluation seed 0, site seeds 1,2,3,4,7 (mean); share of hops with true-target "
              "score < tau_min (mvp_log lower threshold at q = 1, a_min = 0.002, predictor-specific); all-hops value "
              "checked against 1 - ceiling_0.002 of all_periods_summary.csv; dagger = mean > alpha = 0.05")
    cols = [(sc, plab) for sc in CEIL_SCEN for _, plab in OUT_PRED]
    lines = ["\\begin{tabular}{l rr rr}", "\\toprule",
             "& \\multicolumn{2}{c}{Random 10\\%} & \\multicolumn{2}{c}{Random 30\\%} \\\\",
             "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
             "Group & Base & Outage-aware & Base & Outage-aware \\\\", "\\midrule"]
    keys = M[["key", "name", "dim"]].drop_duplicates()
    prev = None
    for _, k in keys.iterrows():
        if prev is not None and k.dim != prev:
            lines.append("\\addlinespace[2pt]")
        prev = k.dim
        cells = []
        for sc, plab in cols:
            v = M[(M.key == k.key) & (M.scenario == sc) & (M.predictor == plab)].iloc[0]
            cells.append(f"{v.p_below_mean:.3f}" + ("$^\\dagger$" if v.over_alpha else ""))
        lines.append(f"{k['name']} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_ceiling")


LOST_SPLIT = L.PH + "/exit_split/hop_loss_split.csv"
LOST_SCEN = [("rand10", "Random 10\\%"), ("rand20", "Random 20\\%"), ("rand30", "Random 30\\%"), ("region", "Region (6 sites)")]


def tab_lost_hops():
    """Hops removed or changed by the outage (start 2014-06-21, whole segment B), initial outage draw (site seed 7)."""
    S = pd.read_csv(REPO / LOST_SPLIT)
    S = S[(S.start == "2014-06-21") & (S.window == "all_post")]
    rows, srcs = [], [LOST_SPLIT]
    for sc, lab in LOST_SCEN:
        r0 = S[S.scenario == sc].iloc[0]
        b = r0.baseline_hops
        r = {"scenario": sc, "label": lab, "n_offline": int(r0.n_offline), "baseline_hops": int(b), "outage_hops": int(r0.outage_hops),
             "pct_src_offline": 100 * r0.a_src_offline / b, "pct_exit_converted": 100 * r0.b_exit_converted / b,
             "pct_rerouted_skip1": 100 * r0.rerouted_skip1 / b, "pct_rerouted_skip2plus": 100 * r0.rerouted_skip2plus / b,
             "rerouted": int(r0.rerouted)}
        fo = f"{L.PH}/exit_split/outage_hops_20140621_{sc}.parquet"
        fh = f"{L.PH}/outage_aware/start_20140621/{sc}/hits.parquet"
        srcs += [fo, fh]
        O = pd.read_parquet(REPO / fo)
        H = pd.read_parquet(REPO / fh)
        J = O.merge(H, on=["trip_id", "t_exit"], how="left", indicator=True)
        assert (J._merge == "both").all()
        rr = J[J.category == "rerouted"]
        assert len(rr) == r["rerouted"]
        for pred, plab in OUT_PRED:
            r[f"recall_rerouted_mvp_log_{plab}"] = rr[f"hit|{pred}|mvp_log"].mean()
            r[f"recall_unchanged_mvp_log_{plab}"] = J[J.category == "unchanged"][f"hit|{pred}|mvp_log"].mean()
            r[f"recall_nonrerouted_mvp_log_{plab}"] = J[J.category != "rerouted"][f"hit|{pred}|mvp_log"].mean()   # unchanged + new
        rows.append(r)
    D = pd.DataFrame(rows)
    write_csv(D, "tab_lost_hops", srcs, "additional",
              "held-out period, outage from 2014-06-21 (whole segment B = B_early + B_late), initial outage draw "
              "(posthoc_outage.py sites, seed 7; region = 6 sites within 800 m), evaluation seed 0; shares in % of the "
              "no-outage hops of segment B; categories from posthoc_exit_split.py; recall of re-linked (rerouted) hops "
              "for mvp_log from the outage-aware run of the same scenario (both predictors), joined on (trip_id, t_exit)")
    lines = ["\\begin{tabular}{l r rr rr rr}", "\\toprule",
             "& & \\multicolumn{2}{c}{Removed (\\%)} & \\multicolumn{2}{c}{Rerouted (\\%)} & \\multicolumn{2}{c}{Recall, rerouted} \\\\",
             "\\cmidrule(lr){3-4}\\cmidrule(lr){5-6}\\cmidrule(lr){7-8}",
             "Outage & Sites off & Source off & To exit & Skip 1 & Skip $\\geq$2 & Base & Outage-aware \\\\", "\\midrule"]
    for _, r in D.iterrows():
        lines.append(f"{r.label} & {r.n_offline} & {f1(r.pct_src_offline)} & {f1(r.pct_exit_converted)} & {f1(r.pct_rerouted_skip1)} & "
                     f"{f1(r.pct_rerouted_skip2plus)} & {f3(r.recall_rerouted_mvp_log_base)} & {f3(r['recall_rerouted_mvp_log_outage-aware'])} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_lost_hops")


ORC_GROUPS = L.PH + "/review/oa_rand10_Blate_mvp_vs_oracle_by_group.csv"


def tab_oracle_groups():
    """Outage-aware predictor, random 10% (site seed 7 only: the oracle's per-hop cost was saved for this run only)."""
    O = pd.read_csv(REPO / ORC_GROUPS)
    O["dim"] = O.group.str.split("=").str[0].replace({"all": "grp_all"})
    O["g"] = O.group.str.split("=").str[1].fillna(0).astype(int)
    O["name"] = [L.group_name(d, g) for d, g in zip(O.dim, O.g)]
    write_csv(O, "tab_oracle_groups", [ORC_GROUPS], "additional",
              "held-out period, random 10% outage (site seed 7, single draw), outage-aware predictor, B_late, evaluation "
              "seed 0; posthoc_oa_oracle_groups.py (oracle per-hop cost from the refitted predictor; three checks passed); "
              "cost ratio = mvp_log mean cost / oracle mean cost within the group. Not a seed mean: the oracle per-hop "
              "cost exists only for this run")
    lines = ["\\begin{tabular}{l r rr r}", "\\toprule",
             "& & \\multicolumn{2}{c}{Recall} & \\\\", "\\cmidrule(lr){3-4}",
             "Group & $n$ & mvp\\_log & Oracle & Cost ratio \\\\", "\\midrule"]
    prev = None
    for _, r in O.iterrows():
        if prev is not None and r.dim != prev:
            lines.append("\\addlinespace[2pt]")
        prev = r.dim
        n = format(int(r.n), ",").replace(",", "{,}")
        lines.append(f"{r['name']} & {n} & {f3(r.mvp_log_coverage)} & {f3(r.oracle_coverage)} & {f2(r.cost_ratio_mvp_over_oracle)} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_oracle_groups")


# ---------------------------------------------------------------- review response (2026-10-01): seeds table (Sean M4)
def tab_seeds():
    A = pd.read_csv(REPO / SEEDS_ALL)
    rows = []
    for sd in sorted(A.seed.unique()):
        r = {"seed": int(sd), "main_result": sd == 0}
        for meth, key in [("mvp_log", "mvp_log"), ("qr_ogd", "qr_ogd")]:
            g = A[(A.seed == sd) & (A.label == meth)].set_index("segment")
            for seg, sn in L.SEGS:
                wk = g.loc[seg, "worst_group"]; d, lv = wk.split("=")
                r[f"{key}_worst_{sn}"] = g.loc[seg, "worst_group_cov"]
                r[f"{key}_worst_key_{sn}"] = wk
                r[f"{key}_worst_name_{sn}"] = L.group_name(d, int(lv))
                r[f"{key}_below94_{sn}"] = int(g.loc[seg, "n_groups_sig_below_bar"])
            r[f"{key}_cost_ratio_mean"] = g.cost_over_oracle.mean()
        rows.append(r)
    D = pd.DataFrame(rows)
    # seed 0 must equal Table 1 (tab_main)
    T, _ = held_rows()
    for key in ["mvp_log", "qr_ogd"]:
        for sn in ["A", "B"]:
            t = T[(T.method == key) & (T.seg == sn)].iloc[0]
            assert abs(D.loc[D.seed == 0, f"{key}_worst_{sn}"].iloc[0] - t.worst) < 1e-12
            assert D.loc[D.seed == 0, f"{key}_below94_{sn}"].iloc[0] == t.below94
    write_csv(D, "tab_seeds", [SEEDS_ALL], "additional",
              "held-out period, evaluation seeds 0-4 (posthoc_seeds.py); seed 0 is the main result (equal to Table 1); 25-group "
              "definition, groups with n >= 200; worst group and number of groups significantly below 0.94 per segment; cost "
              "ratio = mean over A and B of cost / hindsight oracle (primary predictor, same seed and segment)")
    sp = "@{\\hspace{5pt}}"          # 15 columns: narrower column gaps keep the two-column width
    lines = ["\\begin{tabular}{@{}" + sp.join("r l r r l r r r l r r l r r r".split()) + "@{}}", "\\toprule",
             "& \\multicolumn{7}{c}{mvp\\_log} & \\multicolumn{7}{c}{qr\\_ogd} \\\\",
             "\\cmidrule(lr){2-8}\\cmidrule(lr){9-15}",
             "& \\multicolumn{3}{c}{Segment A} & \\multicolumn{3}{c}{Segment B} & & \\multicolumn{3}{c}{Segment A} & \\multicolumn{3}{c}{Segment B} & \\\\",
             "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\\cmidrule(lr){9-11}\\cmidrule(lr){12-14}",
             "Seed & Group & Worst & $<$0.94 & Group & Worst & $<$0.94 & Cost & Group & Worst & $<$0.94 & Group & Worst & $<$0.94 & Cost \\\\", "\\midrule"]
    for _, r in D.iterrows():
        cells = [f"{r.seed}"]
        for key in ["mvp_log", "qr_ogd"]:
            for sn in ["A", "B"]:
                cells += [r[f"{key}_worst_name_{sn}"], f3(r[f"{key}_worst_{sn}"]), fi(r[f"{key}_below94_{sn}"])]
            cells.append(f2(r[f"{key}_cost_ratio_mean"]))
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_seeds")


# ---------------------------------------------------------------- review response (2026-10-01): parameters table (Sean M6)
def tab_parameters():
    """Every value is read from configs/porto_cctv_confirm.yaml or from the code (function defaults via inspect,
    literal rules via the source text); nothing is typed in by hand except the wording."""
    import inspect, re as _re, yaml as _y
    sys.path.insert(0, str(REPO))
    from ccpilot import events as EV, predictors as PR, multigroup as MG, calibration as CA, cameras as CM
    cfgp = "configs/porto_cctv_confirm.yaml"
    c = _y.safe_load(open(REPO / cfgp, encoding="utf-8"))
    po, cam, ev, ex = c["porto"], c["cameras"], c["events"], c["eval"]
    mg = ex["multigroup"]
    porto_src = (REPO / "ccpilot/porto.py").read_text()
    min_pts = int(_re.search(r"len\(pts\) < (\d+)", porto_src).group(1))
    h_head = inspect.signature(EV.extract_sightings).parameters["h_heading_s"].default
    max_ovl = ev.get("max_overlap", inspect.signature(EV.extract_sightings).parameters["max_overlap"].default)
    mvp_sig = inspect.signature(MG.mvp_taus).parameters
    mvp_v = {v["name"]: v for v in mg["mvp_variants"]}["mvp_log"]
    m_ = mvp_v.get("m", mvp_sig["m"].default); r_ = mvp_v.get("r", mvp_sig["r"].default); eps_ = mvp_v.get("eps", mvp_sig["eps"].default)
    K = MG._K_eps(eps_)
    eta = lambda G: float(np.sqrt(np.log(G * m_) / (2 * K * G * m_)))  # noqa: E731
    aci = {v["name"]: v for v in ex["aci_variants"]}["aci_g0005"]
    aci_clip = inspect.signature(CA.aci_taus).parameters["alpha_clip"].default
    mond = ex["mondrian"]["mondrian_hour_hop_speed"]
    qr_floor = inspect.signature(MG.qr_group_taus).parameters["floor"].default
    n_raw = len(__import__("json").load(open(REPO / cam["geojson"], encoding="utf-8"))["features"])
    n_sites = sum(1 for _ in open(REPO / c["work_dir"] / "cameras.csv")) - 1
    sp = ex["splits"]; B = int(np.ceil(ev["t_max_s"] / ev["bin_s"]))
    seeds = sorted(pd.read_csv(REPO / SEEDS_ALL).seed.unique())
    lv = mg["dims"]
    t0_, t1_ = pd.Timestamp(sp["train"][0]), pd.Timestamp(sp["train"][1]) - pd.Timedelta(days=1)   # config ranges are end-exclusive
    train_incl = f"{t0_:%m/%d}--{t1_:%m/%d}, {t1_:%Y}"
    cost_factor = _re.search(r"\| C2 \|[^\n]*≤ ([0-9.]+)", (REPO / "PREREGISTRATION.md").read_text()).group(1)
    # code identifiers in the configuration -> descriptive English (2026-10-02, Sean review 3); an unmapped key stops the build
    KEY_WORDS = {"src": "source site", "zone": "exit zone", "hgroup": "time of day", "speed_bin": "exit-speed quartile",
                 "hopfirst": "first hop of a track"}
    for k in list(ex["predictors"][PRED]) + list(mond):
        assert k in KEY_WORDS, k
    R_ = [
     ("Data and preprocessing", None),
     ("Bounding box (lon, lat)", "", f"[{po['bbox'][0]}, {po['bbox'][2]}] $\\times$ [{po['bbox'][1]}, {po['bbox'][3]}]", "a trip is kept if at least one GPS point lies inside"),
     ("Minimum points per trip", "", f"{min_pts}", "trips with fewer points are dropped"),
     ("Maximum speed", "", f"{po['max_speed_mps']} m/s", "any step faster: whole trip dropped"),
     ("Missing-data trips", "", "dropped", "trips flagged in the data set as having missing points"),
     ("GPS interval / interpolation step", "", f"{po['gps_interval_s']} s / {ev['interp_step_s']:g} s", "linear interpolation, no map matching"),
     ("Cameras", None),
     ("Cameras in the file", "", f"{n_raw}", "camera layer of the Porto open-data portal (version retrieved in July 2025)"),
     ("Tunnel cameras", "", "excluded" if cam["exclude_tunnel"] else "kept", "cameras flagged as inside a tunnel; cameras without the flag are treated as outside"),
     ("Merging", "", f"complete linkage, {cam['merge_radius_m']} m", f"{n_sites} sites"),
     ("Observation radius", "", f"{ev['camera_radius_m']} m", f"disk around each site; at most {max_ovl} sites queried per point"),
     ("Hops and groups", None),
     ("Delay bin / horizon / bins", "$\\Delta$, $T_{\\max}$, $B$", f"{ev['bin_s']} s, {ev['t_max_s']} s, {B}", "no re-appearance within $T_{\\max}$: exit"),
     ("Time-of-day edges", "", ", ".join(str(x) for x in ev["hour_group_edges"]) + " h", "local time of the exit"),
     ("Exit zone", "", "4 sectors", "E, N, W, S sector of the last point in the source disk relative to the site, boundaries at $\\pm45^\\circ$"),
     ("Exit speed", "", f"last {h_head:g} s in the disk", f"straight-line distance between the last interpolated point in the source site's disk and the point {h_head:g} s earlier (or the first point of the sighting), divided by the elapsed time"),
     ("Branching", "", "entropy", "entropy of the source site's next-site distribution over training non-exit hops"),
     ("Isolation", "", "distance", "distance from the source site to the nearest other site"),
     ("Quartile edges", "", "training period", f"speed, branching and isolation, over the training hops; set for each period from its own training period (held-out: {train_incl}, dates inclusive)"),
     ("Source unseen in training", "", "", "branching: highest quartile; predictor: flat matrix at $\\epsilon_0$"),
     ("Predictor", None),
     ("Candidate radius", "$R_{\\mathrm{cand}}$", f"{ex['candidate_radius_m']} m", "plus every next site observed in training"),
     ("Shrinkage", "$\\lambda$", f"{ex['model']['lam']:g}", "toward the parent key"),
     ("Base probability", "$\\epsilon_0$", f"{ex['model']['eps']:g}", "prior of the coarsest level"),
     ("Delay smoothing", "$\\sigma_g$", f"{ex['model']['sigma_bins']:g} bin", "Gaussian along the delay axis"),
     ("Context keys", "", ", ".join(KEY_WORDS[k] for k in ex["predictors"][PRED]), "backed off to the deepest key seen in training"),
     ("Feedback", None),
     ("Feedback fraction", "$\\rho$", f"{ex['aci']['feedback_fraction']:g}", "random over evaluation hops (evaluation seed)"),
     ("Resolution time", "", "arrival / $t_{\\mathrm{exit}}+T_{\\max}$", "hit resolved at re-appearance, miss at the end of the horizon"),
     ("Calibration methods", None),
     ("ACI", "$\\gamma_A$, $W$", f"{aci['gamma']:g}, {ex['aci']['window']}", f"window initialized with the last {ex['aci']['window']} calibration scores; $\\alpha_t$ clipped to [{aci_clip[0]:g}, {aci_clip[1]:g}]"),
     ("Mondrian", "", " $\\times$ ".join(KEY_WORDS[k] for k in mond), f"cells with fewer than {ex['min_group_n']} calibration hops use the global threshold"),
     ("qr\\_groups", "", f"level $\\alpha$, log score", f"intercept + reference-coded indicators of the six attributes; subsample of at most {mg['qr_max_n']:,} calibration hops; score floor {qr_floor:g}".replace(",", "{,}")),
     ("qr\\_ogd", "$\\gamma$, clip", f"{mg['qr_ogd']['gamma']:g}, $\\pm${mg['qr_ogd']['clip']:g}", "offsets start at 0 (threshold of qr\\_groups), log scale"),
     ("MVP (mvp\\_log)", "$m$, $r$, $\\epsilon$", f"{m_}, {r_}, {eps_:g}", f"$\\eta$ = {eta(len(lv) and 25):.4f} (25 groups), {eta(1):.4f} (1 group)"),
     ("", "$a_{\\min}$", f"{mvp_v['a_min']:g}", "warm start: all calibration hops in time order with immediate feedback"),
     ("Evaluation", None),
     ("Target / group bar", "$1-\\alpha$", f"{ex['target_recall']:g} / {ex['group_bar']:g}", "groups significantly below the bar: 95\\% Wilson upper bound"),
     ("Cost criterion", "", cost_factor, "mean of A and B, cost / hindsight oracle"),
     ("Minimum group size", "", f"{ex['min_group_n']}", "smaller groups not judged"),
     ("Evaluation seeds", "", f"{ex['seed']} (main); " + ", ".join(str(x) for x in seeds), "additional seed runs"),
    ]
    assert abs(eta(25) - 0.0319) < 5e-5
    rows = []
    for r in R_:
        if r[1] is None:
            rows.append({"section": r[0], "item": "", "symbol": "", "value": "", "note": ""})
        else:
            rows.append({"section": "", "item": r[0], "symbol": r[1], "value": r[2], "note": r[3]})
    write_csv(pd.DataFrame(rows), "tab_parameters", [cfgp, "ccpilot/porto.py", "ccpilot/events.py", "ccpilot/evaluate.py",
              "ccpilot/predictors.py", "ccpilot/calibration.py", "ccpilot/multigroup.py", cam["geojson"], SEEDS_ALL, "PREREGISTRATION.md"], "main",
              "settings of the confirmation run, read from the configuration file and the code (function defaults via inspect); "
              "the cost criterion 1.20 is the pre-registered value (PREREGISTRATION.md C2)")
    lines = ["\\begin{tabular}{@{}p{3.6cm}p{1.9cm}p{3.4cm}p{7.5cm}@{}}", "\\toprule",
             "Item & Symbol & Value & Note \\\\", "\\midrule"]
    first = True
    for r in R_:
        if r[1] is None:
            if not first:
                lines.append("\\addlinespace[3pt]")
            lines.append(f"\\multicolumn{{4}}{{@{{}}l}}{{\\emph{{{r[0]}}}}} \\\\"); first = False
        else:
            lines.append(f"{r[0]} & {r[1]} & {r[2]} & {r[3]} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_parameters")


# ---------------------------------------------------------------- review response (2026-10-01): custody over hop chains (M5)
CUST_METH = [("static", "static"), ("aci", "aci"), ("qr_ogd", "qr_ogd"), ("mvp_log", "mvp_log"), ("oracle", "oracle")]
CUST_K = [1, 2, 3, 4, 5]


def custody_rows():
    """Chain = hops of one trip between exits (trip_id, chain); only chains whose first hop (hop 0) is an evaluation
    hop; segment = segment of the first hop (as evaluate.custody_table). Empirical custody at k = share of chains with
    >= k hops whose first k hops all hit. Independence value = product over positions j <= k of the mean hit rate at
    position j among the same chains (keeps each position's marginal recall, removes dependence between hops)."""
    H = L.load_held()
    H = H.sort_values(["trip_id", "chain", "hop"]).reset_index(drop=True)
    first = H.groupby(["trip_id", "chain"]).hop.transform("min") == 0
    H = H[first].copy()
    H["pos"] = H.hop + 1
    st = H[H.hop == 0].set_index(["trip_id", "chain"])
    H = H.join(st[["seg", "hopkind"]].rename(columns={"seg": "seg0", "hopkind": "start_kind"}), on=["trip_id", "chain"])
    clen = H.groupby(["trip_id", "chain"]).pos.transform("max")
    rows = []
    for key, lab in CUST_METH:
        col = L.hitcol(key)
        H["ok"] = H.groupby(["trip_id", "chain"])[col].cummin()
        for seg, sn in L.SEGS:
            for start, sname in [(None, "all"), (1, "initiated"), (2, "re-acquired")]:
                m = (H.seg0 == seg) & ((H.start_kind == start) if start else True)
                for k in CUST_K:
                    sel = m & (clen >= k)
                    chains = H[sel & (H.pos == k)]
                    n = len(chains)
                    emp = chains.ok.mean() if n else np.nan
                    pj = [H[sel & (H.pos == j)][col].mean() for j in range(1, k + 1)]
                    rows.append({"method": key, "segment": seg, "seg": sn, "start": sname, "k": k, "n_chains": n,
                                 "custody": emp, "indep": float(np.prod(pj)) if n else np.nan,
                                 "mean_recall_first_k": float(np.mean(pj)) if n else np.nan})
    return pd.DataFrame(rows)


def tab_custody():
    D = custody_rows()
    write_csv(D, "tab_custody", [L.HELD_HITS, L.HELD_SUMMARY], "additional",
              "held-out period, evaluation seed 0, no outage; chain = hops of a trip between exits (trip_id, chain), only "
              "chains starting in the evaluation period, segment of the first hop (same definition as evaluate.custody_table, "
              "results/porto_cctv_confirm/custody_by_hops.csv); custody(k) = share of chains with >= k hops whose first k hops "
              "all hit; indep = product of the position-wise mean hit rates over the same chains; start = hopkind of the "
              "first hop (initiated = first hop of a trip, re-acquired = first hop after an exit); oracle hits reconstructed "
              "from stored scores")
    sp = "@{\\hspace{4.5pt}}"         # 14 columns: narrower column gaps keep the two-column width
    lines = ["\\begin{tabular}{@{}" + sp.join("l l r r r r r r r r r r r r".split()) + "@{}}", "\\toprule",
             "& & \\multicolumn{6}{c}{Segment A} & \\multicolumn{6}{c}{Segment B} \\\\",
             "\\cmidrule(lr){3-8}\\cmidrule(lr){9-14}",
             "Start & Method & $k=1$ & 2 & 3 & 4 & 5 & Indep.\\ 5 & $k=1$ & 2 & 3 & 4 & 5 & Indep.\\ 5 \\\\", "\\midrule"]
    for si, (start, slab) in enumerate([("all", "All"), ("initiated", "Initiated"), ("re-acquired", L.POSTGAP_HEAD)]):
        if si:
            lines.append("\\addlinespace[2pt]")
        n_cells = []
        for sn in ["A", "B"]:
            d = D[(D.start == start) & (D.seg == sn) & (D.method == "static")]
            n_cells += [format(int(d[d.k == k].n_chains.iloc[0]), ",").replace(",", "{,}") for k in CUST_K] + [""]
        lines.append(f"{slab} & chains & " + " & ".join(n_cells) + " \\\\")
        for key, _ in CUST_METH:
            cells = []
            for sn in ["A", "B"]:
                d = D[(D.start == start) & (D.seg == sn) & (D.method == key)].set_index("k")
                cells += [f3(d.loc[k, "custody"]) for k in CUST_K] + [f3(d.loc[5, "indep"])]
            lines.append(f" & {L.tex_label(key)} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_custody")


# ---------------------------------------------------------------- review response (2026-10-01): group-condition hindsight references (M1)
GORC = L.PH + "/group_oracle/group_oracle_summary.csv"
GORC_G = L.PH + "/group_oracle/group_oracle_groups.csv"
LATER_ROWS = [("oracle", "Hindsight oracle (global)"), ("aci", "ACI"), ("qr_ogd", "qr\\_ogd"), ("mvp_log", "mvp\\_log")]
GORC_ROWS = [("oracle", "Hindsight oracle (global)"), ("group_min", "Group-minimum rule (a)"),
             ("hindsight_qr", "Hindsight group QR (b)"), ("qr_ogd", "qr\\_ogd"), ("mvp_log", "mvp\\_log")]


def thou(x):
    return format(int(round(x)), ",").replace(",", "{,}")


def tab_group_oracle():
    D = pd.read_csv(REPO / GORC)
    T, _ = held_rows()
    for k in ["oracle", "mvp_log", "qr_ogd"]:            # same hits as Table 1 (tab_main)
        for seg, sn in L.SEGS:
            d = D[(D.method == k) & (D.segment == seg)].iloc[0]; t = T[(T.method == k) & (T.segment == seg)].iloc[0]
            assert abs(d.recall_mean - t.recall) < 1e-12 and abs(d.worst - t.worst) < 1e-12 and d.below94 == t.below94
            assert abs(d.cost_cam_s - t.cost_cam_s) < 1e-3 * t.cost_cam_s
    D["worst_name"] = [L.group_name(*k.split("=")) for k in D.worst_key]
    D["block"] = "all hops"
    # later hops only (hopkind = 0): recall and cost per method, cost relative to the oracle on the same hops
    G = pd.read_csv(REPO / GORC_G); G = G[G.key == "hopkind=0"].set_index(["segment", "method"])
    lat = []
    for seg, sn in L.SEGS:
        for k, _ in LATER_ROWS:
            g = G.loc[(seg, k)]
            lat.append({"segment": seg, "method": k, "block": "later hops", "n_hops": int(g.n), "recall_mean": g.recall, "cost_cam_s": g.cost_cam_s,
                        "ratio_vs_oracle": g.cost_cam_s / G.loc[(seg, "oracle"), "cost_cam_s"]})
    Lt = pd.DataFrame(lat)
    for seg, _ in L.SEGS:                                  # the statement of Section 6: multigroup recall lower, cost higher
        o = Lt[(Lt.segment == seg) & (Lt.method == "oracle")].iloc[0]
        for k in ["qr_ogd", "mvp_log"]:
            x = Lt[(Lt.segment == seg) & (Lt.method == k)].iloc[0]
            assert x.recall_mean < o.recall_mean and x.cost_cam_s > o.cost_cam_s
    D = pd.concat([D, Lt], ignore_index=True)
    write_csv(D, "tab_group_oracle", [GORC, GORC_G], "additional",
              "held-out period, segments A and B, primary predictor, evaluation seed 0, no outage (posthoc_group_oracle.py); "
              "(a) group-minimum rule: per pre-registered group the largest threshold with in-sample group recall >= 0.95, each "
              "hop takes the minimum over its groups; (b) hindsight group QR: qr_groups design fitted without subsampling to the "
              "segment's own scores; recall/worst/below over the 25-group definition with n >= 200 (Wilson 95% upper bound); "
              "n_groups_lt200_used = groups with n < 200 that enter the reference's construction; ratio_vs_oracle = cost / "
              "global hindsight oracle cost, ratio_vs_group_min = cost / cost of (a), same segment; block 'later hops': hops whose "
              "track state is 'later' (hopkind = 0) only, recall and mean cost of each method on these hops (group_oracle_groups.csv), "
              "ratio_vs_oracle = cost / cost of the hindsight oracle on the same later hops")
    lines = ["\\begin{tabular}{@{}ll rrlrr rrr@{}}", "\\toprule",
             "Seg. & Reference / method & Recall & Worst & Worst group & $<$0.94 & $<$0.95 & Cost & $\\times$oracle & $\\times$(a) \\\\",
             "\\midrule"]
    A_ = D[D.block == "all hops"]
    for i, (seg, sn) in enumerate(L.SEGS):
        if i:
            lines.append("\\addlinespace[2pt]")
        for j, (k, lab) in enumerate(GORC_ROWS):
            d = A_[(A_.method == k) & (A_.segment == seg)].iloc[0]
            cells = [sn if j == 0 else "", lab, f3(d.recall_mean), f3(d.worst), d.worst_name, fi(d.below94), fi(d.below95),
                     thou(d.cost_cam_s), f2(d.ratio_vs_oracle), f2(d.ratio_vs_group_min)]
            lines.append(" & ".join(cells) + " \\\\")
    Lb = D[D.block == "later hops"]
    lines += ["\\midrule", "\\multicolumn{10}{@{}l}{\\emph{Later hops only}} \\\\"]
    for i, (seg, sn) in enumerate(L.SEGS):
        if i:
            lines.append("\\addlinespace[2pt]")
        for j, (k, lab) in enumerate(LATER_ROWS):
            d = Lb[(Lb.method == k) & (Lb.segment == seg)].iloc[0]
            cells = [sn if j == 0 else "", lab, f3(d.recall_mean), "--", "", "--", "--", thou(d.cost_cam_s), f2(d.ratio_vs_oracle), "--"]
            lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_group_oracle")


# ---------------------------------------------------------------- review response (2026-10-01): geometry / horizon sensitivity (M3)
GEOM = L.PH + "/geometry/geometry_summary.csv"
GEOM_SEEDS = L.PH + "/geometry/geometry_seed_pass.csv"
GEOM_SET = [("base", "Confirmation settings (radius 50\\,m, $T_{\\max}=600$\\,s)"), ("r30", "Radius 30\\,m"),
            ("r75", "Radius 75\\,m"), ("tmax300", "$T_{\\max}=300$\\,s"), ("tmax900", "$T_{\\max}=900$\\,s")]
GEOM_METH = ["static", "aci", "qr_ogd", "mvp_log", "oracle"]


def tab_geometry():
    D = pd.read_csv(REPO / GEOM)
    P = pd.read_csv(REPO / GEOM_SEEDS).set_index(["setting", "method"])
    D["seeds_pass"] = [int(P.loc[(st, k), "n_pass"]) for st, k in zip(D.setting, D.method)]
    D["seeds_n"] = [int(P.loc[(st, k), "n_seeds"]) for st, k in zip(D.setting, D.method)]
    C = pd.read_csv(REPO / SEEDS_ALL)                     # base: seed pass counts equal the seed repetition (Table seeds)
    for k, lab in [("mvp_log", "mvp_log"), ("qr_ogd", "qr_ogd"), ("aci", "aci_g0005")]:
        npass = int((C[C.label == lab].groupby("seed").n_groups_sig_below_bar.sum() == 0).sum())
        assert npass == P.loc[("base", k), "n_pass"], (k, npass)
    T, _ = held_rows()
    for k in GEOM_METH:                                   # base rows equal Table 1 (tab_main)
        for seg, sn in L.SEGS:
            d = D[(D.setting == "base") & (D.method == k) & (D.segment == seg)].iloc[0]
            t = T[(T.method == k) & (T.segment == seg)].iloc[0]
            assert abs(d.recall - t.recall) < 1e-12 and abs(d.worst - t.worst) < 1e-12 and d.below94 == t.below94
            assert abs(d.cost_ratio - t.cost_ratio) < 1e-9
    write_csv(D, "tab_geometry", [GEOM, GEOM_SEEDS], "additional",
              "held-out period, primary predictor, evaluation seed 0, reduced method set; each setting rebuilds sites, hops, "
              "training/calibration data and group quartile edges (posthoc_geometry.py, configs/porto_cctv_confirm_geom_*.yaml); "
              "base = confirmation run; 25-group definition with n >= 200; below94 = groups whose Wilson 95% upper bound < 0.94; "
              "cost_ratio = cost / hindsight oracle of the same setting and segment; structural_miss = share of hops of the "
              "segment whose next site lies outside the candidate set (hindsight oracle row of summary.csv); exit share over all "
              "held-out transitions; seeds_pass = evaluation seeds 0-4 with no group below 0.94 in either segment (static and the "
              "oracle do not depend on the seed; base = posthoc_seeds.py seeds_prereg25). Evaluation-seed invariance (checked in "
              "geometry_seeds.csv, seeds 0-4: identical recall, worst group, cost, counts in every setting): static and the hindsight "
              "oracle do not change with the seed; in the table the oracle's Seeds entry is -- (a reference, as in Table 4) and static's 0/5 is the seed-0 result repeated, not five independent runs; "
              "ACI, qr_ogd and mvp_log were rerun with seeds 1-4")
    for c in ["n_sites", "camera_radius_m", "merge_radius_m", "t_max_s"]:
        assert D.groupby("setting")[c].nunique().max() == 1
    lines = ["\\begin{tabular}{@{}l rrrr rrrr r@{}}", "\\toprule",
             "& \\multicolumn{4}{c}{Segment A} & \\multicolumn{4}{c}{Segment B} & \\\\",
             "\\cmidrule(lr){2-5}\\cmidrule(lr){6-9}",
             "Method & Recall & Worst & $<$0.94 & Cost & Recall & Worst & $<$0.94 & Cost & Seeds \\\\", "\\midrule"]
    for i, (st, lab) in enumerate(GEOM_SET):
        X = D[D.setting == st]
        a = X[(X.segment == "test_jun_a")].iloc[0]; b = X[(X.segment == "test_jun_b")].iloc[0]
        meta1 = f"{lab}: {fi(a.n_sites)} sites; exit share {f3(a.exit_share_heldout)}"
        meta2 = (f"hops A/B {thou(a.n_hops_segment)}/{thou(b.n_hops_segment)}; "
                 f"structural miss A/B {100 * a.structural_miss:.3f}\\%/{100 * b.structural_miss:.3f}\\%")
        if i:
            lines.append("\\addlinespace[3pt]")
        lines.append(f"\\multicolumn{{10}}{{@{{}}l}}{{\\textit{{{meta1}}}}} \\\\")
        lines.append(f"\\multicolumn{{10}}{{@{{}}l}}{{\\textit{{\\quad {meta2}}}}} \\\\")
        for k in GEOM_METH:
            cells = [L.tex_label(k)]
            for seg, _ in L.SEGS:
                d = X[(X.method == k) & (X.segment == seg)].iloc[0]
                cells += [f3(d.recall), f3(d.worst), fi(d.below94), f2(d.cost_ratio)]
            cells.append("--" if k == "oracle" else f"{int(d.seeds_pass)}/{int(d.seeds_n)}")   # oracle: a reference, as in Table 4
            lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_geometry")


# ---------------------------------------------------------------- 2026-10-02: appendix/supplementary split
EXPL_METH = [("aci", "ACI"), ("qr_ogd", "qr\\_ogd"), ("mvp_log", "mvp\\_log")]
EXPL_SCEN_SHORT = {"rand10": "Rand.\\ 10\\%", "rand20": "Rand.\\ 20\\%", "rand30": "Rand.\\ 30\\%", "region_fixed": "Region"}


def tab_outage_expl():
    """Exploratory periods 1 and 2, outage-aware predictor only, one-column width. Values equal tab_outage_expl1/2."""
    parts = []
    for period, pn, name in [("porto_cctv", 1, "tab_outage_expl1"), ("porto_cctv_rep", 2, "tab_outage_expl2")]:
        D = outage_table(period, "B_late", name)        # regenerates the full tables (supplementary) as well
        A = D[D.predictor == "outage-aware"].copy(); A.insert(0, "period", pn)
        F = pd.read_csv(PAPER / "generated" / "data" / f"{name}.csv", comment="#")
        F = F[F.predictor == "outage-aware"].reset_index(drop=True)
        for _, k in OUT_METH[1:]:
            for c in ("recall", "below94", "cost_ratio_none"):
                assert np.allclose(A[f"{c}_{k}"].to_numpy(), F[f"{c}_{k}"].to_numpy(), rtol=0, atol=1e-12), (name, c, k)
        parts.append(A)
    D = pd.concat(parts, ignore_index=True)
    keep = ["period", "scenario", "predictor", "label_scenario"] + [c for c in D.columns if any(c.endswith("_" + k) for k, _ in EXPL_METH)]
    D = D[keep]
    write_csv(D, "tab_outage_expl", [OUT_ALL], "additional",
              "exploratory periods 1 and 2, outage-aware predictor only, from 48 h after the outage start (segment B_late) to the end "
              "of the last evaluation segment; evaluation seed 0; random outages: mean over site seeds 1,2,3,4,7; region_fixed: single "
              "draw (20 sites); below94 = groups significantly below 0.94 (25 groups, seed mean); cost = mean cost / hindsight-oracle "
              "cost of the base predictor without outage, same period and segment. Values equal the outage-aware rows of "
              "tab_outage_expl1 and tab_outage_expl2 (checked)")
    sp = "@{\\hspace{2.5pt}}"                         # 11 columns in one column width
    lines = ["\\begin{tabular}{@{}" + sp.join("llrrrrrrrrr") + "@{}}", "\\toprule",
             "& & " + " & ".join(f"\\multicolumn{{3}}{{c}}{{{lab}}}" for _, lab in EXPL_METH) + " \\\\",
             "".join(f"\\cmidrule(lr){{{3 + 3 * i}-{5 + 3 * i}}}" for i in range(len(EXPL_METH))),
             "Per. & Outage & " + " & ".join(["Rec. & $<$.94 & Cost"] * len(EXPL_METH)) + " \\\\", "\\midrule"]
    for i, (_, r) in enumerate(D.iterrows()):
        if i and r.period != D.period.iloc[i - 1]:
            lines.append("\\addlinespace[2pt]")
        cells = []
        for k, _ in EXPL_METH:
            single = r.scenario == "region_fixed"
            cells += [f3(r[f"recall_{k}"]), fi(r[f"below94_{k}"]) if single else f1(r[f"below94_{k}"]), f2(r[f"cost_ratio_none_{k}"])]
        per = str(r.period) if (i == 0 or r.period != D.period.iloc[i - 1]) else ""
        lines.append(f"{per} & {EXPL_SCEN_SHORT[r.scenario]} & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_outage_expl")


EXTRA = L.PH + "/review/oa_rand10_Blate_mvp_vs_oracle_by_category.csv"
EXTRA_CAT = [("unchanged", "Not rerouted"), ("rerouted_skip1", "Rerouted, 1 failed site skipped"),
             ("rerouted_skip2plus", "Rerouted, $\\ge$2 failed sites skipped"),
             ("new", "New (source episode changed)"), ("reacq_by_outage", f"{L.POSTGAP_HEAD} hop caused by the outage")]


def tab_extra_cost():
    C = pd.read_csv(REPO / EXTRA).set_index("category")
    assert set(C.index) == {k for k, _ in EXTRA_CAT}
    assert abs(C.share_of_hops.sum() - 1) < 1e-9 and abs(C.share_of_total_extra_cost.sum() - 1) < 1e-9
    D = C.loc[[k for k, _ in EXTRA_CAT]].reset_index()
    write_csv(D, "tab_extra_cost", [EXTRA], "additional",
              "held-out period, random outage of 10% of the sites (site seed 7), outage-aware predictor, segment B_late (from 48 h "
              "after the outage start), evaluation seed 0; mvp_log against the hindsight oracle of the same scenario; hop categories "
              "from posthoc_exit_split.py (rerouted split by the number of consecutive failed sites skipped); share_of_total_extra_cost = "
              "category's sum of (mvp_log cost - oracle cost) / total; the oracle's per-hop cost from the refitted predictor "
              "(posthoc_oa_oracle_groups.py, checks against the saved run)")
    lines = ["\\begin{tabular}{@{}p{2.9cm} rrrr@{}}", "\\toprule",
             "Hop type & Hops & \\multicolumn{2}{c}{Recall} & Extra \\\\", "\\cmidrule(lr){3-4}",
             " & (\\%) & mvp\\_log & Oracle & cost (\\%) \\\\", "\\midrule"]
    for k, lab in EXTRA_CAT:
        r = C.loc[k]
        lines.append(f"{lab} & {f1(100 * r.share_of_hops)} & {f3(r.mvp_log_coverage)} & {f3(r.oracle_coverage)} & {f1(100 * r.share_of_total_extra_cost)} \\\\")
    lines += ["\\midrule", f"All & 100.0 & {f3((C.share_of_hops * C.mvp_log_coverage).sum())} & {f3((C.share_of_hops * C.oracle_coverage).sum())} & 100.0 \\\\",
              "\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_extra_cost")


# ---------------------------------------------------------------- confirm2 precheck B1 (2026-10-02): cluster bootstrap intervals
CLUSTER_CI = "results/porto_cctv_confirm_posthoc/cluster_ci/cluster_ci.csv"


def tab_cluster_ci():
    R = pd.read_csv(REPO / CLUSTER_CI)
    cols = []
    for bar in L.BARS:
        for _, sn in L.SEGS:
            for iv in ("wilson", "taxi", "day"):
                cols.append((bar, sn, iv))
    rows = []
    for key in L.MKEYS:
        r = {"method": key}
        for bar, sn, iv in cols:
            g = R[(R.method == key) & (R.seg == sn) & (R.n >= L.MIN_N)]
            assert len(g) == 25
            r[f"below{int(round(bar * 100))}_{sn}_{iv}"] = int((g[f"{iv}_ub"] < bar).sum())
        rows.append(r)
    D = pd.DataFrame(rows)
    # Wilson counts must equal the main table's
    T, _ = held_rows()
    for _, t in T.iterrows():
        if t.method in L.MKEYS:
            assert D.loc[D.method == t.method, f"below94_{t.seg}_wilson"].iloc[0] == t.below94, (t.method, t.seg)
    write_csv(D, "tab_cluster_ci", [CLUSTER_CI], "additional",
              "held-out period, evaluation seed 0, primary predictor, 25-group definition (n >= 200); number of groups whose "
              "95% interval upper end is below the bar: Wilson (as in C1), percentile cluster bootstrap with clusters = taxi "
              "(427 in A, 425 in B) or = local day of exit (12 in A, 10 in B), 4,000 resamples within segment (posthoc_cluster.py)")
    sp = "@{\\hspace{4pt}}"
    lines = ["\\begin{tabular}{@{}l" + sp + sp.join(["r"] * 12) + "@{}}", "\\toprule",
             "& \\multicolumn{6}{c}{Below 0.94} & \\multicolumn{6}{c}{Below 0.95} \\\\",
             "\\cmidrule(lr){2-7}\\cmidrule(lr){8-13}",
             "& \\multicolumn{3}{c}{Segment A} & \\multicolumn{3}{c}{Segment B} & \\multicolumn{3}{c}{Segment A} & \\multicolumn{3}{c}{Segment B} \\\\",
             "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\\cmidrule(lr){8-10}\\cmidrule(lr){11-13}",
             "Method" + " & W & T & D" * 4 + " \\\\", "\\midrule"]
    for _, r in D.iterrows():
        cells = [L.tex_label(r.method)] + [str(r[f"below{int(round(b * 100))}_{sn}_{iv}"]) for b, sn, iv in cols]
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    write_tex("\n".join(lines), "tab_cluster_ci")


TABLES = {"tab_layout_factors": tab_layout_factors, "group_labels": group_labels, "tab_main": tab_main,
          "tab_worst_groups": tab_worst_groups, "tab_ablation": tab_ablation, "tab_sensitivity": tab_sensitivity,
          "tab_outage": lambda: outage_table("porto_cctv_confirm", "B_late", "tab_outage"),
          "tab_outage_early": lambda: outage_table("porto_cctv_confirm", "B_early", "tab_outage_early"),
          "tab_outage_expl1": lambda: outage_table("porto_cctv", "B_late", "tab_outage_expl1"),
          "tab_outage_expl2": lambda: outage_table("porto_cctv_rep", "B_late", "tab_outage_expl2"),
          "tab_ceiling": tab_ceiling, "tab_lost_hops": tab_lost_hops, "tab_oracle_groups": tab_oracle_groups,
          "tab_seeds": tab_seeds, "tab_parameters": tab_parameters, "tab_custody": tab_custody,
          "tab_group_oracle": tab_group_oracle, "tab_geometry": tab_geometry,
          "tab_outage_expl": tab_outage_expl, "tab_extra_cost": tab_extra_cost,
          "tab_cluster_ci": tab_cluster_ci}


def main():
    only = sys.argv[1:] or list(TABLES)
    for name in only:
        TABLES[name]()
        print("table:", name)


if __name__ == "__main__":
    main()
