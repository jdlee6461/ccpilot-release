"""Gate 8 tables (instruction 18 §2(b)-(d), (f), §3; verdict 21): bodies only, captions are written by David.

    python scripts/make_gate8_tables.py        (run from paper/; CCPILOT_REPO=<ccpilot> for a work copy)

Outputs (generated/tables/):
  tab_c2_verdicts3.tex               the three estimates (post-gap d, isolation-Q4 d, Dbar) x six comparators x two online
                                     methods x five targets (plan 10.1: all three in the main text), class symbol with
                                     the seed sign agreement of classified cells as a superscript (plan 5.5, 9.3)
  tab_c2_custody_pairs.tex           POST HOC: paired five-hop custody difference, method - static, all chains and chains
                                     starting with a post-gap hop, target 0.95 (custody_diffs.csv, every stored pair)
  tab_review_predictors_targets.tex  POST HOC: predictor sensitivity, Dbar at the five targets (review C_estimates.csv;
                                     the refit at 0.95 only)
  tab_c2_exit_share.tex              POST HOC: exit share of the evaluation transitions per group (exploratory/gate8)
  tab_c2_inter_groups.tex            POST HOC: qr_groups and qr_groups + I1-I6 on I1-I6 (exploratory/intersections_q)
  tab_c2_intersections_merged.tex    Alex 25 (Shannon19 X32): tab_c2_partitions and tab_c2_inter_groups in one fragment
                                     (I1-I6 rows shared; static, mvp_log, qr_ogd, qr_groups, qr_groups + I1-I6)
  tab_c2_partitions_summary.tex      plan 8.3: target 0.95, Dbar on the 25 groups and the largest shortfall of each
                                     alternative partition, static and the two online methods (instruction 19 §3(a))
  tab_r23_seeds.tex, tab_r24_qrogd_step.tex  repository Tables R23 and R24 as supplementary floats, verbatim
                                     except the post-gap term (instructions 20 §3, 21 §4); R23 with panel (b) only
                                     (verdict 26 C, instruction 22 §2); R24 is written but not input by the supplement
  tab_c2_diagnostics_b.tex           panel (b) of tab_c2_diagnostics.tex (ACI variants), rows copied from that body
  tab_review_predictors_b.tex        panel (b) of the predictor table: 0.95, post-gap d and cost / H2 (instruction 21 §4)
  tab_r16_geometry_short.tex         POST HOC: repository Table R16 shortened (verdict 27 §6-1, §6-7 #5; instruction 23 §3):
                                     held-out period, seed 0, T_max 600 s, radius 30/50/75 m; worst-group shortfall and
                                     cost relative to the hindsight oracle per segment
  tab_r13_layout.tex                 repository Table R13 body (tab_layout_factors.tex, scripts/make_tables.py) verbatim
                                     (verdict 27 §6-7 #10; instruction 23 §3); it has no re-acquisition term
  tab_review_feedback_b4.tex         POST HOC: rows of the left-censored QR trial for S7 (REVIEW_PLAN B (b), B4; verdict 27
                                     §6-5; instruction 23 §2): label set (i), block 1, seed 0, target 0.95
"""
import os
import re
import sys
from pathlib import Path

import pandas as pd

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))   # work copy outside ccpilot: CCPILOT_REPO=/home/user/ccpilot
sys.path.insert(0, str(PAPER / "scripts"))
from make_confirm2_tables import COMPARATORS, ONLINE, SYM, ci, pp, srcline  # noqa: E402
from make_confirm2_appendix import seedsup  # noqa: E402
from ch6lib import DIMS25, LEVEL_NAME, POSTGAP_HEAD, POSTGAP_LABEL  # noqa: E402

A = "results/porto_cctv_confirm2/analysis"
CU = "results/porto_cctv_confirm2_posthoc/custody/custody_diffs.csv"
RVC = "results/porto_cctv_confirm2_posthoc/review/C_estimates.csv"
RVCD = "results/porto_cctv_confirm2_posthoc/review/C_differences.csv"
EXIT = "exploratory/gate8/exit_by_group.csv"
GEOM = "results/porto_cctv_confirm_posthoc/geometry/geometry_summary.csv"
RVB = "results/porto_cctv_confirm2_posthoc/review/B_refit_b_estimates.csv"
RVBLOG = "results/porto_cctv_confirm2_posthoc/review/refit_logs/block1_t0950_s0__Bi_refit_b_{}.csv"
INTQ = "exploratory/intersections_q/intersections_q.csv"
TABLES = PAPER / "generated" / "tables"
TARGETS = [0.90, 0.93, 0.95, 0.97, 0.98]
POSTHOC = "% POST HOC (added during revision (internal review); Gate 8, instruction 18)."


def write(name, lines):
    (TABLES / name).write_text("\n".join(lines) + "\n")


def tab_verdicts3():
    M = pd.read_csv(REPO / A / "main_estimands.csv").query("scope == 'combined'")
    EST = [("reacq_deficit_diff", f"{POSTGAP_HEAD} $d$"), ("isoq4_deficit_diff", "Isolation Q4 $d$"),
           ("worst_deficit_diff", r"\Dbar{}")]
    # instruction 23 §9 (re-discussion 2026-11-03 #14): rows against static, ACI and Mondrian left out (they stay in S2);
    # three comparators x three estimates; superscripts 3 and 4 only
    COMP = [(c, lab) for c, lab in COMPARATORS if c.startswith("qr_groups")]
    L = [srcline([f"{A}/main_estimands.csv"]),
         "% scope=combined; class (99% simultaneous over the five targets, B=10000, conservative bound of the taxi and day "
         "clusters): + improvement, = undetermined, - worsening; superscript = seeds whose paired difference has the sign "
         "of the class (seed_agreement, plan 5.5), on classified cells only, shown only when fewer than five; "
         "comparators qr_groups, qr_groups_refit, qr_groups_refit7 (static, ACI, Mondrian in S2). The verdict of a statement uses the "
         "post-gap row (plan 10.8).",
         r"\setlength{\tabcolsep}{1.0pt}",            # one column with \scriptsize (verdict 28 A4: 236 pt)
         r"\begin{tabular}{@{}ll" + "c" * len(TARGETS) + r"@{\hspace{6pt}}" + "c" * len(TARGETS) + "@{}}", r"\toprule",
         " & & " + " & ".join(rf"\multicolumn{{{len(TARGETS)}}}{{c}}{{{lab}}}" for _, lab in ONLINE) + r" \\",
         rf"\cmidrule(r){{3-{2 + len(TARGETS)}}}\cmidrule(l){{{3 + len(TARGETS)}-{2 + 2 * len(TARGETS)}}}",
         "Comparator & Estimate & " + " & ".join(f"{t:.2f}"[1:] for _ in ONLINE for t in TARGETS) + r" \\", r"\midrule"]
    for k, (c, clab) in enumerate(COMP):
        if k:
            L.append(r"\addlinespace")
        for j, (e, elab) in enumerate(EST):
            cells = [seedsup(M[(M.proposed == m) & (M.comparator == c) & (M.target == t) & (M.estimand == e)])
                     for m, _ in ONLINE for t in TARGETS]
            L.append(f"{clab if j == 0 else ''} & {elab} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_verdicts3.tex", L)


def tab_custody_pairs(t=0.95):
    D = pd.read_csv(REPO / CU, comment="#").query("target == @t and scope == 'combined' and h == 5")
    METH = ONLINE + [("qr_groups", r"\texttt{qr\_groups}"), ("qr_groups_refit", r"\texttt{qr\_groups\_refit}"),
                     ("qr_groups_refit7", r"\texttt{qr\_groups\_refit7}"), ("aci_g0005", "ACI"),
                     ("mondrian_hour_hop_speed", "Mondrian")]

    def get(m, start):
        r = D[(D.start == start) & (((D.method_a == m) & (D.method_b == "static")) | ((D.method_a == "static") & (D.method_b == m)))]
        assert len(r) == 1
        r = r.iloc[0]
        sg = 1 if r.method_a == m else -1
        lo, hi = sorted((sg * r.lo, sg * r.hi))
        return sg * r["diff"], lo, hi
    L = [srcline([CU]), POSTHOC,
         f"% target={t}, scope=combined, h=5; custody(method) - custody(static) in pp (two decimals) with the conservative 95% paired interval "
         "(taxi and day cluster bootstraps, B=2000, same weights for every method; the stored pair a-b is turned into "
         "method - static). Start: all chains; chains whose first hop is a post-gap hop (start=reacquired).",
         r"\begin{tabular}{@{}lrr@{}}", r"\toprule",
         rf"Method & All chains & Chains starting {POSTGAP_HEAD.lower()} \\", r"\midrule"]
    def ci2(d, lo, hi):                  # two decimals, as the custody macros (ctwoCustodyPaired..., verdict 21 A (n))
        f = lambda v: f"{100 * v:.2f}".replace("-", "$-$")
        return f"{f(d)} [{f(lo)}, {f(hi)}]"
    for m, lab in METH:
        a, b = get(m, "all"), get(m, "reacquired")
        L.append(f"{lab} & {ci2(*a)} & {ci2(*b)}" + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_custody_pairs.tex", L)


def tab_predictors_targets():
    E = pd.read_csv(REPO / RVC, comment="#").query("scope == 'combined' and estimand == 'D'")
    PRED = {"src": "source site", "src_zone": "+ exit zone", "src_zone_hour": "+ exit zone, time of day",
            "src_zone_speed": "+ exit zone, exit speed", "src_zone_hour_speed": "+ exit zone, time, speed (main)"}
    NAME = {"static": r"\texttt{static}", "aci_g0005": "ACI", "mondrian_hour_hop_speed": "Mondrian (40 cells)",
            "qr_groups": r"\texttt{qr\_groups}", "mvp_log": r"\texttt{mvp\_log}", "qr_ogd": r"\texttt{qr\_ogd}",
            "qr_groups_refit": r"\texttt{qr\_groups\_refit}$^{a}$"}
    # verdict 24 A2 (instruction 20 §3): paired difference against static and ACI, review C_differences.csv
    # (Delta = D_comparator - D_reference, positive = the group method smaller); smallest conservative 95% lower bound
    # over the targets of the row
    DF = pd.read_csv(REPO / RVCD, comment="#").query("scope == 'combined' and estimand == 'D_diff'")

    def lowest(lab, p, m):
        out = []
        for c in ("static", "aci_g0005"):
            r = DF[(DF.label == lab) & (DF.predictor == p) & (DF.reference == m) & (DF.comparator == c)]
            if not len(r):
                return "--"
            out.append(pp(r.lo.min()))
        return " / ".join(out)
    L = [srcline([RVC, RVCD]), POSTHOC,
         "% scope=combined, estimand D (worst-group shortfall) in pp with the conservative 95% interval (taxi and day, "
         "B=2000), seed means; label C_<predictor> (C_refit for the refit of src_zone_speed); the refit at 0.95 only. "
         "Last column: smallest conservative 95% lower bound, over the targets of the row, of D(static) - D(method) and "
         "D(ACI) - D(method) (C_differences.csv D_diff, paired; positive = method smaller); -- = not a group method.",
         r"\setlength{\tabcolsep}{3.0pt}",
         r"\begin{tabular}{@{}ll" + "r" * len(TARGETS) + "r@{}}", r"\toprule",
         "Predictor & Method & " + " & ".join(f"{t:.2f}" for t in TARGETS) + r" & $\Delta$ lower bound \\",
         " & & & & & & & vs \\texttt{static} / ACI \\\\", r"\midrule"]
    for k, (p, plab) in enumerate(PRED.items()):
        if k:
            L.append(r"\addlinespace")
        ms = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "mvp_log", "qr_ogd"]
        if p in ("src_zone_speed", "src_zone_hour_speed"):
            ms.append("qr_groups_refit")
        for j, m in enumerate(ms):
            lab = "C_refit" if (p == "src_zone_speed" and m == "qr_groups_refit") else f"C_{p}"
            g = E[(E.label == lab) & (E.predictor == p) & (E.method == m)].set_index("target")
            cells = [ci(g.point[t], g.lo[t], g.hi[t]) if t in g.index else "--" for t in TARGETS]
            cells.append(lowest(lab, p, m))
            L.append(f"{plab if j == 0 else ''} & {NAME[m]} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", "",
          r"\smallskip\parbox{\linewidth}{\footnotesize $^{a}$Refitted daily; run at target 0.95 only. --: not run. "
          r"$\Delta$ lower bound: smallest 95\% lower bound over the targets of the paired difference of \Dbar{}, "
          r"\texttt{static} or ACI minus the method (pp).}"]
    write("tab_review_predictors_targets.tex", L)


def tab_exit_share():
    X = pd.read_csv(REPO / EXIT, comment="#")
    L = [srcline([EXIT]), POSTHOC,
         "% evaluation transitions (t_exit in the block's evaluation range) of each group, exits included; exit share = "
         "n_exit / n_transitions in %, one decimal; groups rebuilt with ccpilot.evaluate._add_strata/_add_spatial on the "
         "block's run configuration (equal to hits.parquet for the non-exit hops; exploratory/gate8/exit_by_group_check.csv).",
         r"\setlength{\tabcolsep}{3.4pt}",
         r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r"Group & Transitions & \multicolumn{3}{c}{Exit share (\%)} \\", r"\cmidrule(l){3-5}",
         r" & (pooled) & Pooled & Block~1 & Block~2 \\", r"\midrule"]
    for k, d in enumerate(DIMS25):
        if k:
            L.append(r"\addlinespace")
        for v in sorted(LEVEL_NAME[d]):
            g = X[X.group == f"{d}={v}"].set_index("scope")
            n = format(int(g.n_transitions["combined"]), ",").replace(",", "{,}")
            L.append(f"{LEVEL_NAME[d][v]} & {n} & " + " & ".join(f"{100 * g.exit_share[s]:.1f}" for s in
                                                                  ("combined", "block1", "block2")) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_exit_share.tex", L)


def tab_inter_groups():
    Q = pd.read_csv(REPO / INTQ, comment="#")
    Q = Q[Q.method.isin(["qr_groups", "A3_qr_groups_inter"])]
    lab = {"qr_groups": r"\texttt{qr\_groups}", "A3_qr_groups_inter": r"\texttt{qr\_groups} + I1--I6$^{a}$"}
    L = [srcline([INTQ]), POSTHOC,
         "% shortfall d (pp) on the intersections I1-I6 with the conservative 95% interval (taxi and day, B=2000), "
         "scope combined, seed means; qr_groups from the frozen intersections.csv, qr_groups + I1-I6 from review "
         "A_intersections.csv (via exploratory/intersections_q).",
         r"\setlength{\tabcolsep}{3.0pt}",
         r"\begin{tabular}{@{}ll" + "r" * len(TARGETS) + "@{}}", r"\toprule",
         "Intersection & Method & " + " & ".join(f"{t:.2f}" for t in TARGETS) + r" \\", r"\midrule"]
    for k, c in enumerate(sorted(Q.cell.unique())):
        if k:
            L.append(r"\addlinespace")
        for j, m in enumerate(["qr_groups", "A3_qr_groups_inter"]):
            g = Q[(Q.cell == c) & (Q.method == m)].set_index("target")
            L.append(f"{c if j == 0 else ''} & {lab[m]} & " + " & ".join(ci(g.deficit[t], g.lo[t], g.hi[t]) for t in TARGETS)
                     + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", "",
          r"\smallskip\parbox{\linewidth}{\footnotesize $^{a}$Calibrated with I1--I6 added as groups and evaluated on "
          r"them (self-evaluation).}"]
    write("tab_c2_inter_groups.tex", L)


def tab_intersections_merged():
    """Alex 25 (Shannon19 X32, instruction 25 §3(b)): Tables S-partitions and S-inter_groups as one fragment. Upper panel:
    the alternative-partition rows of tab_c2_partitions.tex (online methods, five targets), unchanged; lower panel: one
    row per intersection and target, columns static, mvp_log, qr_ogd, qr_groups (frozen intersections.csv, scope
    combined) and qr_groups + I1-I6 (exploratory/intersections_q, as tab_c2_inter_groups.tex)."""
    from make_confirm2_appendixB import body, tabular_rows   # noqa: E402
    import make_confirm2_appendix as APX                      # noqa: E402
    APX.tab_alt()
    _, ra, _ = tabular_rows(body(TABLES / "tab_c2_app_alt.tex"))
    F = pd.read_csv(REPO / A / "intersections.csv").query("scope == 'combined'")
    Q = pd.read_csv(REPO / INTQ, comment="#")
    M = [("static", r"\texttt{static}"), ("mvp_log", r"\texttt{mvp\_log}"), ("qr_ogd", r"\texttt{qr\_ogd}"),
         ("qr_groups", r"\texttt{qr\_groups}"), ("A3_qr_groups_inter", r"\texttt{qr\_groups} + I1--I6$^{a}$")]
    NAME = {"I1": rf"I1 {POSTGAP_LABEL} $\times$ isolation Q4", "I2": rf"I2 {POSTGAP_LABEL} $\times$ branching Q4",
            "I3": rf"I3 {POSTGAP_LABEL} $\times$ speed Q4", "I4": r"I4 first hop of a trip $\times$ isolation Q4",
            "I5": r"I5 speed Q4 $\times$ isolation Q4", "I6": rf"I6 00--06 h $\times$ {POSTGAP_LABEL}"}
    def cell(m, c, t):
        if m == "A3_qr_groups_inter":
            r = Q[(Q.method == m) & (Q.cell == c) & (Q.target == t)].iloc[0]
        else:
            r = F[(F.method == m) & (F.cell == c) & (F.target == t)].iloc[0]
            q = Q[(Q.method == m) & (Q.cell == c) & (Q.target == t)]
            assert q.empty or abs(q.deficit.item() - r.deficit) < 1e-9, (m, c, t)   # same value as intersections_q
        return ci(r.deficit, r.lo, r.hi), int(r.n)
    T = len(TARGETS)
    L = [srcline([f"{A}/alt_partitions.csv", f"{A}/intersections.csv", INTQ]), POSTHOC.replace("Gate 8, instruction 18",
         "Gate 8, instruction 18; qr_groups + I1-I6 column only"),
         "% upper: rows of tab_c2_partitions.tex (alt_partitions.csv SUMMARY, diff_vs_D [diff_lo, diff_hi], pp, conservative "
         "95%); lower: shortfall d [lo, hi] (pp, conservative 95%), scope combined, seed means; static, mvp_log, qr_ogd, "
         "qr_groups from intersections.csv, qr_groups + I1-I6 from exploratory/intersections_q (review A_intersections.csv); "
         "n = hops (pooled).",
         r"\setlength{\tabcolsep}{3.0pt}",
         # panel headings above each panel's rules, as in Tables S9 and S11 (JD memo v12-1 Y7, instruction 31 §1)
         r"\emph{(a) Alternative partitions: largest shortfall minus \Dbar{} on the 25 groups}\par\smallskip",
         r"\begin{tabular}{@{}ll" + "r" * T + "@{}}", r"\toprule",
         r"Method & Partition & " + " & ".join(f"{t:.2f}" for t in TARGETS) + r" \\", r"\midrule"]
    L += ra
    L += [r"\bottomrule", r"\end{tabular}", r"\par\medskip",
          r"\emph{(b) Intersections I1--I6: shortfall}\par\smallskip",
          r"\begin{tabular}{@{}ll" + "r" * T + "@{}}", r"\toprule",
          r"Intersection (hops) & Target & " + " & ".join(lab for _, lab in M) + r" \\", r"\midrule"]
    for k, c in enumerate(["I1", "I2", "I3", "I4", "I5", "I6"]):
        if k:
            L.append(r"\addlinespace[2pt]")
        for j, t in enumerate(TARGETS):
            cells = [cell(m, c, t) for m, _ in M]
            n = {x[1] for x in cells[:4]}
            assert len(n) == 1, (c, t, n)
            head = f"{NAME[c]} ({n.pop():,})".replace(",", "{,}") if j == 0 else ""
            L.append(f"{head} & {t:.2f} & " + " & ".join(x[0] for x in cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", "",
          r"\smallskip\parbox{\linewidth}{\footnotesize $^{a}$Calibrated with I1--I6 added as groups and evaluated on "
          r"them (self-evaluation).}"]
    write("tab_c2_intersections_merged.tex", L)

def tab_partitions_summary(t=0.95):
    """plan 8.3 (verdict 22 B, instruction 19 §3(a)): target 0.95 summary of the alternative partitions; Dbar on the 25
    groups (deficits.csv WORST) and the largest shortfall over the cells of each alternative partition (alt_partitions.csv
    SUMMARY: seed mean of the per-seed maximum over cells with n >= min_group_n), static, mvp_log, qr_ogd."""
    from make_confirm2_appendix import FAMILY
    DF = pd.read_csv(REPO / A / "deficits.csv").query("scope == 'combined' and target == @t and cell == 'WORST'")
    AP = pd.read_csv(REPO / A / "alt_partitions.csv").query("scope == 'combined' and target == @t and cell == 'SUMMARY'")
    METH = [("static", r"\texttt{static}")] + ONLINE

    def one(T, m, fam=None):
        r = T[(T.method == m) & ((T.family == fam) if fam else True)]
        assert len(r) == 1
        r = r.iloc[0]
        return ci(r.deficit, r.lo, r.hi)
    L = [srcline([f"{A}/deficits.csv", f"{A}/alt_partitions.csv"]),
         f"% target={t}, scope=combined; first row: Dbar on the 25 groups (deficits.csv cell=WORST); other rows: largest "
         "shortfall over the cells of the partition (alt_partitions.csv cell=SUMMARY, seed mean of the per-seed maximum over "
         "cells with at least min_group_n hops); pp with the conservative 95% interval (taxi and day cluster bootstraps).",
         r"\setlength{\tabcolsep}{3.0pt}",
         r"\begin{tabular}{@{}l" + "c" * len(METH) + "@{}}", r"\toprule",
         "Groups & " + " & ".join(lab for _, lab in METH) + r" \\", r"\midrule",
         r"25 groups (\Dbar{}) & " + " & ".join(one(DF, m) for m, _ in METH) + r" \\", r"\addlinespace[2pt]"]
    for fam, lab in FAMILY.items():
        L.append(f"{lab} & " + " & ".join(one(AP, m, fam) for m, _ in METH) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_partitions_summary.tex", L)


def tab_predictors_panel_b(t=0.95):
    """verdict 25 A4 (instruction 21 §4): panel (b) of the predictor table, target 0.95: post-gap shortfall and cost
    relative to H2 per predictor for the three group methods run with every predictor (qr_groups, mvp_log, qr_ogd);
    review C_estimates.csv, the cells of the former 0.95 table (tab_review_predictors)."""
    E = pd.read_csv(REPO / RVC, comment="#").query("scope == 'combined' and target == @t")
    PRED = {"src": "source site", "src_zone": "+ exit zone", "src_zone_hour": "+ exit zone, time of day",
            "src_zone_speed": "+ exit zone, exit speed", "src_zone_hour_speed": "+ exit zone, time, speed (main)"}
    NAME = {"qr_groups": r"\texttt{qr\_groups}", "mvp_log": r"\texttt{mvp\_log}", "qr_ogd": r"\texttt{qr\_ogd}"}
    L = [srcline([RVC]), POSTHOC,
         f"% target={t}, scope=combined, labels C_<predictor>; post-gap shortfall (estimand reacq_d) in pp and cost relative "
         "to H2 (cost_ratio_H2), conservative 95% interval (taxi and day, B=2000), seed means.",
         r"\setlength{\tabcolsep}{3.0pt}",
         r"\begin{tabular}{@{}llrr@{}}", r"\toprule",
         rf"Predictor & Method & {POSTGAP_HEAD} $d$ & Cost / H2 \\", r"\midrule"]
    for k, (p, plab) in enumerate(PRED.items()):
        if k:
            L.append(r"\addlinespace")
        for j, m in enumerate(NAME):
            g = E[(E.label == f"C_{p}") & (E.predictor == p) & (E.method == m)].set_index("estimand")
            d, c = g.loc["reacq_d"], g.loc["cost_ratio_H2"]
            cc = f"{c.point:.2f} [{c.lo:.2f}, {c.hi:.2f}]"
            L.append(f"{plab if j == 0 else ''} & {NAME[m]} & {ci(d.point, d.lo, d.hi)} & {cc}" + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_review_predictors_b.tex", L)


def tab_r23_panel_b():
    """verdict 26 C (instruction 22 §2): panel (b) of R23 (the three ACI variants) as the body of S14; header and
    rows copied from generated/tables/tab_c2_diagnostics.tex (scripts/make_confirm2_appendixB.py), panel letter dropped."""
    L = (TABLES / "tab_c2_diagnostics.tex").read_text().splitlines()
    i = next(k for k, x in enumerate(L) if "{(b) ACI variants" in x); j = next(k for k, x in enumerate(L) if "{(c) " in x)
    head = L[:L.index(r"\midrule") + 1]                            # source lines, tabular, header row, first rule
    rows = [L[i].replace("{(b) ACI variants", "{ACI variants")] + L[i + 1:j - 1]   # j - 1: the rule before (c)
    write("tab_c2_diagnostics_b.tex", ["% verdict 26 C: panel (b) of tab_c2_diagnostics.tex (rows copied verbatim, "
                                       "panel letter dropped)"] + head + rows + [r"\bottomrule", r"\end{tabular}"])


def tab_bundle_floats():
    """instruction 20 §3 (verdict 24): repository Tables R23 (seed dependence, tab:c2_diagnostics) and R24 (tuning
    history with the qr_ogd step size, tab:c2_tuning) as supplementary floats, verbatim from the repository bundle
    (supplementary_tables/body_supplementary.tex: caption, label and the input of the generated body)."""
    src = (PAPER / "supplementary_tables" / "body_supplementary.tex").read_text()
    for label, name in (("tab:c2_diagnostics", "tab_r23_seeds.tex"), ("tab:c2_tuning", "tab_r24_qrogd_step.tex")):
        k = src.index(rf"\label{{{label}}}")
        a = src.rindex(r"\begin{table*}", 0, k); b = src.index(r"\end{table*}", k) + len(r"\end{table*}")
        fl = src[a:b].replace("re-acquisition", POSTGAP_LABEL)     # verdict 25 A2: the paper's term, otherwise verbatim
        if label == "tab:c2_diagnostics":                           # verdict 26 C: panel (b) only, clauses of (a), (c), (d) cut
            fl = re.sub(r"Range over seeds of .*?interval width;\s*three", "Three", fl, flags=re.S)
            fl = re.sub(r"; share of hops at .*?both blocks pooled\.\}", ".}", fl, flags=re.S)
            fl = fl.replace("tab_c2_diagnostics.tex", "tab_c2_diagnostics_b.tex").replace("tab\\_c2\\_diagnostics", "tab\\_c2\\_diagnostics\\_b")
            assert "Three ACI variants" in fl and "a_{\\min}" not in fl and "_b.tex" in fl
        write(name, [f"% float of the repository bundle (supplementary_tables/body_supplementary.tex, label {label}; "
                     "instruction 20 §3), verbatim except 're-acquisition' -> the paper's post-gap term (verdict 25 A2); "
                     "body: generated/tables by scripts/make_confirm2_appendixB.py", fl])


def tab_r16_geometry_short(t=0.95):
    """verdict 27 §6-1 (instruction 23 §3): R16 at T_max 600 s, radii 30, 50 (the confirmation setting) and 75 m; per
    method, worst-group shortfall t - worst (pp, seed 0) and cost / hindsight oracle, segment A/B; the full table is
    repository Table R16 (generated/tables/tab_geometry.tex)."""
    G = pd.read_csv(REPO / GEOM)
    SET = [("r30", "30\\,m"), ("base", "50\\,m"), ("r75", "75\\,m")]
    METH = [("static", r"\texttt{static}"), ("aci", "ACI"), ("qr_ogd", r"\texttt{qr\_ogd}"), ("mvp_log", r"\texttt{mvp\_log}"),
            ("oracle", "hindsight oracle")]
    assert (G[G.setting.isin([s for s, _ in SET])].t_max_s == 600).all()
    assert sorted(G[G.setting.isin([s for s, _ in SET])].camera_radius_m.unique()) == [30, 50, 75]
    L = [srcline([GEOM]), "% POST HOC (review M3, posthoc_geometry.py). Held-out period (earlier evaluation), primary predictor, "
         f"evaluation seed 0, T_max 600 s; shortfall = {t} - worst (worst group of the 25-group definition with n >= 200), pp, "
         "one decimal; cost = cost_ratio (cost / hindsight oracle of the same setting and segment); cells A/B = segments "
         "test_jun_a / test_jun_b. Radius 50 m = the confirmation setting (setting base).",
         r"\setlength{\tabcolsep}{3.0pt}",
         r"\begin{tabular}{@{}l" + "cc" * len(SET) + "@{}}", r"\toprule",
         " & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{Radius {lab}}}" for _, lab in SET) + r" \\",
         "".join(rf"\cmidrule(lr){{{2 + 2 * k}-{3 + 2 * k}}}" for k in range(len(SET))),
         "Method" + " & Shortfall & Cost" * len(SET) + r" \\", r"\midrule"]
    for m, lab in METH:
        cells = []
        for st, _ in SET:
            a, b = (G[(G.setting == st) & (G.method == m) & (G.segment == sg)].iloc[0] for sg in ("test_jun_a", "test_jun_b"))
            cells += [f"{pp(t - a.worst)}/{pp(t - b.worst)}", f"{a.cost_ratio:.2f}/{b.cost_ratio:.2f}" if m != "oracle" else "1/1"]
        L.append(f"{lab} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_r16_geometry_short.tex", L)


def tab_r13_layout():
    """verdict 27 §6-7 #10 (instruction 23 §3): body of repository Table R13 (tab:layout), verbatim."""
    src = TABLES / "tab_layout_factors.tex"
    body = src.read_text().splitlines()
    assert not any("re-acq" in x.lower() for x in body)          # nothing to replace by the post-gap term
    write("tab_r13_layout.tex", ["% repository Table R13 (supplementary_tables/body_supplementary.tex, label tab:layout): body "
                                 "generated/tables/tab_layout_factors.tex (scripts/make_tables.py) copied verbatim"] + body)


def tab_review_feedback_b4(t=0.95):
    """verdict 27 §6-5 (instruction 23 §2): rows for S7 from the left-censored QR trial (REVIEW_PLAN B (b); B4: supplementary
    table only), label set (i), block 1, seed 0, target 0.95, kappa 0.005 and 0.02, delta 0; with the daily refit (a) and
    the two online methods of the same block and seed for reference. Block 2 was not run."""
    E = pd.read_csv(REPO / RVB).query("scope == 'block1' and target == @t").set_index(["method", "estimand"])
    ROWS = [("Bi_refit_a", "refit"), ("Bi_refit_b_k0005", r"left-censored QR, $\kappa=0.005$"),
            ("Bi_refit_b_k002", r"left-censored QR, $\kappa=0.02$"), ("mvp_log", r"\texttt{mvp\_log}"),
            ("qr_ogd", r"\texttt{qr\_ogd}")]
    kept = []
    for k in ("k0005", "k002"):
        g = pd.read_csv(REPO / RVBLOG.format(k)).query("k > 0")
        kept.append(f"kappa {k}: refits {len(g)}, feedback hops resolved at the last refit {int(g.n_fb_resolved.iloc[-1])}, "
                    f"kept in step 2 {int(g.step2_kept.iloc[-1])} ({100 * g.step2_kept.iloc[-1] / g.n_fb_resolved.iloc[-1]:.1f}%), "
                    f"in step 3 {int(g.step3_kept.iloc[-1])} ({100 * g.step3_kept.iloc[-1] / g.n_fb_resolved.iloc[-1]:.1f}%)")
    L = [srcline([RVB, RVBLOG.format("k0005"), RVBLOG.format("k002")]), POSTHOC,
         f"% label set (i), scope block1 (block 2 not run), evaluation seed 0, target {t}; D and post-gap d (reacq_d) in pp, "
         "cost / H2, conservative 95% interval (taxi and day cluster bootstraps, B=2000); " + "; ".join(kept) + ".",
         r"\begin{tabular}{@{}llccc@{}}", r"\toprule",
         rf"Label set & Method & \Dbar{{}} & {POSTGAP_HEAD} $d$ & Cost / H2 \\", r"\midrule"]
    for j, (m, lab) in enumerate(ROWS):
        d, r, c = E.loc[(m, "D")], E.loc[(m, "reacq_d")], E.loc[(m, "cost_ratio_H2")]
        L.append(f"{'(i), block 1, seed 0' if j == 0 else ''} & {lab} & {ci(d.point, d.lo, d.hi)} & {ci(r.point, r.lo, r.hi)} & "
                 f"{c.point:.2f} [{c.lo:.2f}, {c.hi:.2f}]" + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_review_feedback_b4.tex", L)


def main():
    tab_verdicts3(); tab_custody_pairs(); tab_predictors_targets(); tab_exit_share(); tab_inter_groups()
    tab_partitions_summary(); tab_r23_panel_b(); tab_bundle_floats(); tab_predictors_panel_b()
    tab_r16_geometry_short(); tab_r13_layout(); tab_review_feedback_b4(); tab_intersections_merged()
    print("[make_gate8_tables] tab_c2_verdicts3, tab_c2_custody_pairs, tab_review_predictors_targets, tab_c2_exit_share, "
          "tab_c2_inter_groups, tab_c2_partitions_summary, tab_c2_diagnostics_b, tab_r23_seeds, tab_r24_qrogd_step, "
          "tab_review_predictors_b, tab_r16_geometry_short, tab_r13_layout, tab_review_feedback_b4, tab_c2_intersections_merged")


if __name__ == "__main__":
    main()
