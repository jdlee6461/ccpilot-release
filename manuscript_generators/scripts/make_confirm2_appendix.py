"""Appendix C (confirmation experiment, further results): tables and figures from the frozen confirm2 results.

    python scripts/make_confirm2_appendix.py        (run from paper/; after make_confirm2_tables.py)

Item list: the placeholder paragraph of sections/appendix.tex (app:confirm2). Writes the table bodies to
generated/tables/tab_c2_app_*.tex and one wrapper generated/app_confirm2.tex with the floats (captions are factual
drafts for David). The wrapper is NOT input by the manuscript; replacing the placeholder paragraph with
\\input{generated/app_confirm2.tex} is left to David/JD (manuscript text is not edited here).
Items not produced (see REPORT.md): the tuning history (precheck A9; source is a Korean prose table in
results/precheck_confirm2/precheck_report2.md, needs wording).
"""
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))   # work copy outside ccpilot: CCPILOT_REPO=/home/user/ccpilot
sys.path.insert(0, str(PAPER / "scripts"))
from make_confirm2_tables import COMPARATORS, ONLINE, OTHERS, SYM, ci, pp, srcline, tab_main  # noqa: E402

A = "results/porto_cctv_confirm2/analysis"
TRIAL = "results/precheck_confirm2/trial_expl1/analysis"
TABLES = PAPER / "generated" / "tables"
ALL_M = ONLINE + COMPARATORS + OTHERS
LAB = dict(ALL_M)
from ch6lib import DIM_NAME, LEVEL_NAME, POSTGAP_LABEL  # noqa: E402
# post-gap term in S2 and S3 (verdict 27 §6-6, instruction 23 §4): POSTGAP_LABEL instead of "re-acq."
EST = [("reacq_deficit_diff", POSTGAP_LABEL), ("isoq4_deficit_diff", "iso.\\ Q4"), ("worst_deficit_diff", r"\Dbar{}")]
FAMILY = {"hour24": "one-hour periods", "hour3": "three-hour periods", "zone8": "eight exit sectors",
          "speed5": "exit-speed quintiles", "entropy5": "branching quintiles", "isolation5": "isolation quintiles"}
INTER = {"I1": "PG $\\times$ isolation Q4", "I2": "PG $\\times$ branching Q4",
         "I3": "PG $\\times$ speed Q4", "I4": "initiated $\\times$ isolation Q4",
         "I5": "speed Q4 $\\times$ isolation Q4", "I6": "00--06 h $\\times$ PG"}
INTER = {k: v.replace("PG", POSTGAP_LABEL) for k, v in INTER.items()}


def rd(path):
    return pd.read_csv(REPO / path)


def write(name, lines):
    (TABLES / f"{name}.tex").write_text("\n".join(lines) + "\n")


def tgt_header(T, first="", span=None):
    return f"{first} & " + " & ".join(f"{t:.2f}" for t in T) + r" \\"


def seedsup(r):
    """class symbol; superscript = seeds agreeing with the class (plan 5.5) on classified cells, only when fewer than five
    (instruction 23 §9: superscripts 3 and 4 only)."""
    assert len(r) == 1
    r = r.iloc[0]
    sym, n = SYM[r["class"]], str(r.seed_agreement).split("/")[0]
    return sym if r["class"] == "undetermined" or n == "5" else sym[:-1] + "^{" + n + "}$"


def tab_classes():
    M = rd(f"{A}/main_estimands.csv").query("scope == 'combined'")
    T = sorted(M.target.unique())
    L = [srcline([f"{A}/main_estimands.csv"]),
         "% scope=combined, all three estimands, column class (99% simultaneous, conservative): + improvement, "
         "= undetermined, - worsening; sign D_comparator - D_method; superscript = seeds whose paired difference has "
         "the sign of the class (seed_agreement, plan 5.5), shown only when fewer than five (instruction 23 §9).",
         r"\setlength{\tabcolsep}{2.2pt}",
         r"\begin{tabular}{@{}ll" + "c" * len(T) + r"@{\hspace{6pt}}" + "c" * len(T) + "@{}}", r"\toprule",
         " & & " + " & ".join(rf"\multicolumn{{{len(T)}}}{{c}}{{{lab}}}" for _, lab in ONLINE) + r" \\",
         rf"\cmidrule(r){{3-{2 + len(T)}}}\cmidrule(l){{{3 + len(T)}-{2 + 2 * len(T)}}}",
         "Comparator & Estimate & " + " & ".join(f"{t:.2f}"[1:] for _ in ONLINE for t in T) + r" \\", r"\midrule"]
    for k, (c, lab) in enumerate(COMPARATORS):
        for j, (e, el) in enumerate(EST):
            cells = [seedsup(M[(M.proposed == m) & (M.comparator == c) & (M.target == t) & (M.estimand == e)])
                     for m, _ in ONLINE for t in T]
            L.append(f"{lab if j == 0 else ''} & {el} & " + " & ".join(cells) + r" \\")
        if k < len(COMPARATORS) - 1:
            L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_app_classes", L)


def tab_dominance():
    D = rd(f"{A}/dominance.csv")
    lab = {**LAB, "H1": "H1", "H3": "H3", "H4": "H4"}
    L = [srcline([f"{A}/dominance.csv"]),
         "% columns method_dominates_pairs, comparator_dominates_pairs (interval dominance, 95%, plan 10.5; pairs of "
         "target points), same_cost_sentence_allowed.",
         r"\setlength{\tabcolsep}{3pt}", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r" & \multicolumn{2}{c}{\texttt{mvp\_log}} & \multicolumn{2}{c}{\texttt{qr\_ogd}} \\",
         r"\cmidrule(lr){2-3}\cmidrule(l){4-5}",
         r"Comparator & dominates & dominated & dominates & dominated \\", r"\midrule"]
    for c in D.comparator.unique():
        r = {m: D[(D.method == m) & (D.comparator == c)].iloc[0] for m, _ in ONLINE}
        L.append(f"{lab[c]} & " + " & ".join(f"{int(r[m].method_dominates_pairs)} & {int(r[m].comparator_dominates_pairs)}"
                                             for m, _ in ONLINE) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_app_dominance", L)


def by_target_table(name, rows, T, src, note, first="", width="l"):
    L = [srcline(src), note, r"\setlength{\tabcolsep}{3.4pt}", r"\begin{tabular}{@{}" + width + "r" * len(T) + "@{}}", r"\toprule",
         tgt_header(T, first), r"\midrule"] + rows + [r"\bottomrule", r"\end{tabular}"]
    write(name, L)


def tab_alt():
    S = rd(f"{A}/alt_partitions.csv").query("scope == 'combined' and cell == 'SUMMARY'")
    T = sorted(S.target.unique())
    rows = []
    for m, ml in ONLINE:
        for f, fl in FAMILY.items():
            cells = []
            for t in T:
                r = S[(S.method == m) & (S.family == f) & (S.target == t)].iloc[0]
                cells.append(ci(r.diff_vs_D, r.diff_lo, r.diff_hi))
            rows.append(f"{ml if f == 'hour24' else ''} & {fl} & " + " & ".join(cells) + r" \\")
        rows.append(r"\addlinespace[2pt]")
    rows = rows[:-1]
    by_target_table("tab_c2_app_alt", rows, T, [f"{A}/alt_partitions.csv"],
                    "% scope=combined, cell=SUMMARY; diff_vs_D [diff_lo, diff_hi] (largest shortfall over the partition "
                    "minus D of the 25 groups, same method; 95% conservative), pp.", first="Method & Partition", width="ll")


def tab_inter():
    I = rd(f"{A}/intersections.csv").query("scope == 'combined'")
    T = sorted(I.target.unique())
    rows = []
    for m, ml in ONLINE:
        for c, cl in INTER.items():
            cells = []
            for t in T:
                r = I[(I.method == m) & (I.cell == c) & (I.target == t)].iloc[0]
                cells.append(ci(r.deficit, r.lo, r.hi))
            n = int(I[(I.method == m) & (I.cell == c)].n.iloc[0])
            rows.append(f"{ml if c == 'I1' else ''} & {c} {cl} ({n:,}) & ".replace(",", "{,}") + " & ".join(cells) + r" \\")
        rows.append(r"\addlinespace[2pt]")
    rows = rows[:-1]
    by_target_table("tab_c2_app_inter", rows, T, [f"{A}/intersections.csv"],
                    "% scope=combined; deficit [lo, hi] (95% conservative), pp; n = hops (pooled, per seed).",
                    first="Method & Intersection ($n$)", width="ll")


def tab_blocks():
    B = rd(f"{A}/block_comparison.csv")
    T = sorted(B.target.unique())
    rows = []
    for m, ml in ALL_M:
        cells = [ci(*B[(B.method == m) & (B.target == t)][["diff", "lo", "hi"]].iloc[0]) for t in T]
        rows.append(f"{ml} & " + " & ".join(cells) + r" \\")
    by_target_table("tab_c2_app_blocks", rows, T, [f"{A}/block_comparison.csv"],
                    "% diff = D_block1 - D_block2 [lo, hi] (taxi: paired, day: independent; conservative), pp.",
                    first="Method")


def tab_seeds():
    S = rd(f"{A}/seed_range.csv").query("scope == 'combined'")
    T = sorted(S.target.unique())
    rows = []
    for m, ml in ALL_M:
        cells = []
        for t in T:
            r = S[(S.method == m) & (S.target == t)].iloc[0]
            cells.append(f"{pp(r.D_seed_min)}--{pp(r.D_seed_max)} ({r.seed_range_over_ci_width:.2f})")
        rows.append(f"{ml} & " + " & ".join(cells) + r" \\")
    by_target_table("tab_c2_app_seeds", rows, T, [f"{A}/seed_range.csv"],
                    "% scope=combined; D_seed_min--D_seed_max in pp (seed_range_over_ci_width).", first="Method")


def tab_aci():
    """ACI variants: per-run summaries (no bootstrap; seed means of the per-block values)."""
    rows, src = [], "results/porto_cctv_confirm2/runs/<block>/t<target>/s<seed>/summary.csv"
    recs = []
    for blk in ("block1", "block2"):
        for tdir in sorted((REPO / "results/porto_cctv_confirm2/runs" / blk).glob("t*")):
            for sd in sorted(tdir.glob("s*")):
                f = sd / "summary.csv"
                if not f.exists():
                    continue
                s = pd.read_csv(f)
                s = s[(s.predictor == "src_zone_hour_speed") & s.method.str.startswith("aci")]
                for _, r in s.iterrows():
                    recs.append(dict(block=blk, target=r.target, seed=sd.name, method=r.method, cov=r.coverage,
                                     worst=r.worst_group_cov, cost=r.cost_mean_cam_s))
    R = pd.DataFrame(recs)
    assert R.groupby(["block", "target", "method"]).seed.nunique().eq(5).all()
    G = R.groupby(["method", "target", "block"])[["cov", "worst", "cost"]].mean()
    names = {"aci_g0005": r"ACI $\gamma=0.0005$ (main)", "aci_g001": r"ACI $\gamma=0.001$",
             "aci_hophour_g001f": r"ACI per hour $\times$ first hop"}
    L = [f"% source: {src} @ {subprocess.run(['git', 'log', '-1', '--format=%h', '--', 'results/porto_cctv_confirm2/runs'], cwd=REPO, capture_output=True, text=True).stdout.strip()}",
         "% predictor=src_zone_hour_speed; columns coverage, worst_group_cov (as-run strata), cost_mean_cam_s; mean over "
         "seeds 0-4 per block; no interval.",
         r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
         r" & & \multicolumn{3}{c}{Block 1} & \multicolumn{3}{c}{Block 2} \\",
         r"\cmidrule(lr){3-5}\cmidrule(l){6-8}",
         r"Variant & $t$ & Recall & Worst & Cost & Recall & Worst & Cost \\", r"\midrule"]
    for m in names:
        for i, t in enumerate(sorted(R.target.unique())):
            a, b = G.loc[(m, t, "block1")], G.loc[(m, t, "block2")]
            L.append(f"{names[m] if i == 0 else ''} & {t:.2f} & {a['cov']:.3f} & {a.worst:.3f} & {a.cost:.0f} & "
                     f"{b['cov']:.3f} & {b.worst:.3f} & {b.cost:.0f}" + r" \\")
        L.append(r"\addlinespace[2pt]")
    L = L[:-1] + [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_app_aci", L)


def tab_reach():
    U = rd(f"{A}/reachable_bound.csv").query("scope == 'combined'")
    am = rd(f"{A}/a_min_reach.csv").query("target == 0.98")
    L = [srcline([f"{A}/reachable_bound.csv", f"{A}/a_min_reach.csv"]),
         "% scope=combined; U_G (reachable upper bound of the recall) and below_mvp_log_min_tau_share; footnote: "
         "a_min_reach.csv target=0.98, mvp_log_hops_at_a_min_share per seed.",
         r"\begin{tabular}{@{}lrrr@{}}", r"\toprule", r"Group & $n$ & $U_G$ & Below $\tau_{\min}$ (\%) \\", r"\midrule"]
    for _, r in U.iterrows():
        dim, lev = r.group.split("=")
        L.append(f"{LEVEL_NAME[dim][int(lev)]} & {int(r.n):,} & {r.U_G:.4f} & {100 * r.below_mvp_log_min_tau_share:.2f}"
                 .replace(",", "{,}") + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", "",
          r"\smallskip\parbox{\columnwidth}{\footnotesize Share of hops whose \texttt{mvp\_log} cost equals the cost at "
          r"$a_{\min}$, target 0.98, seeds 0--4: "
          + ", ".join(f"{100 * v:.4f}" for v in am.sort_values("seed").mvp_log_hops_at_a_min_share) + r"\,\%.}"]
    write("tab_c2_app_reach", L)


def tab_trial():
    M = rd(f"{TRIAL}/main_estimands.csv")
    assert set(M.target) == {0.95}
    L = [srcline([f"{TRIAL}/main_estimands.csv"]),
         "% exploratory period 1, target 0.95, evaluation seeds 0-1; the trial implementation reports method - "
         "comparator (negative = improvement): sign flipped here to D_comparator - D_method (plan 13.8); "
         "point [lo, hi] (99% conservative), pp; class symbol.",
         r"\begin{tabular}{@{}llrcrc@{}}", r"\toprule",
         r" & & \multicolumn{2}{c}{\texttt{mvp\_log}} & \multicolumn{2}{c}{\texttt{qr\_ogd}} \\",
         r"\cmidrule(lr){3-4}\cmidrule(l){5-6}",
         r"Comparator & Estimate & Difference & & Difference & \\", r"\midrule"]
    for k, (c, lab) in enumerate(COMPARATORS):
        for j, (e, el) in enumerate(EST):
            cells = []
            for m, _ in ONLINE:
                r = M[(M.proposed == m) & (M.comparator == c) & (M.estimand == e)]
                if r.empty:
                    cells.append("-- & ")
                    continue
                r = r.iloc[0]
                cells.append(f"{ci(-r.point, -r.hi, -r.lo)} & {SYM[r['class']]}")
            L.append(f"{lab if j == 0 else ''} & {el} & " + " & ".join(cells) + r" \\")
        if k < len(COMPARATORS) - 1:
            L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_c2_app_trial", L)


def wrapper():
    F = [("fig_c2_calibration_block1", "Recall per group against the target, block~1 (August); as Fig.~\\ref{fig:c2_calibration}."),
         ("fig_c2_calibration_block2", "Recall per group against the target, block~2 (autumn); as Fig.~\\ref{fig:c2_calibration}."),
         ("fig_c2_cost_block1", "Worst-group recall against mean cost per hop, block~1; as Fig.~\\ref{fig:c2_cost}."),
         ("fig_c2_cost_block2", "Worst-group recall against mean cost per hop, block~2; as Fig.~\\ref{fig:c2_cost}.")]
    W = ["% AUTO-GENERATED by scripts/make_confirm2_appendix.py -- floats of Appendix C (captions: drafts for David).",
         "% Not input by main.tex; intended to replace the placeholder paragraph of app:confirm2.", ""]
    for f, cap in F:
        W += [r"\begin{figure*}[!t]", r"\centering", rf"\includegraphics[width=\textwidth]{{generated/figures/{f}.pdf}}",
              rf"\caption{{{cap}}}", rf"\label{{fig:{f.replace('fig_', '')}}}", r"\end{figure*}", ""]
    T = [("tab_c2_app_t0900", True, "Confirmation period, target 0.90; columns as in Table~\\ref{tab:c2_main}."),
         ("tab_c2_app_t0930", True, "Confirmation period, target 0.93; columns as in Table~\\ref{tab:c2_main}."),
         ("tab_c2_app_t0970", True, "Confirmation period, target 0.97; columns as in Table~\\ref{tab:c2_main}."),
         ("tab_c2_app_t0980", True, "Confirmation period, target 0.98; columns as in Table~\\ref{tab:c2_main}."),
         ("tab_c2_app_classes", True, f"Classification of all pre-specified comparisons for the three estimates ({POSTGAP_LABEL} "
          "shortfall, isolation Q4 shortfall, worst-group shortfall \\Dbar{}; 99\\% simultaneous, conservative): $+$ "
          "improved, $=$ not distinguished, $-$ worse."),
         ("tab_c2_app_dominance", False, "Number of dominating target-point pairs (interval dominance, 95\\%) between each "
          "online method and each comparator, in both directions."),
         ("tab_c2_app_alt", True, "Alternative partitions not used for calibration: largest shortfall over the partition "
          "minus \\Dbar{} on the 25 groups (same method), pp, conservative 95\\% interval."),
         ("tab_c2_app_inter", True, "Shortfall on the intersections I1--I6 (pp, conservative 95\\% interval)."),
         ("tab_c2_app_blocks", True, "Difference in worst-group shortfall between block~1 and block~2 (pp, conservative 95\\% "
          "interval)."),
         ("tab_c2_app_seeds", True, "Range of the worst-group shortfall over the five evaluation seeds (pp) and, in "
          "parentheses, its ratio to the width of the 95\\% interval."),
         ("tab_c2_app_aci", True, "The three ACI variants (per block, mean over seeds; no interval). Only $\\gamma=0.0005$ "
          "enters the comparisons."),
         ("tab_c2_app_reach", False, "Reachable upper bound $U_G$ of each group and share of hops below the lowest threshold "
          "of \\texttt{mvp\\_log} (pooled)."),
         ("tab_c2_app_trial", True, "Trial run on exploratory period~1 before the lock (target 0.95, evaluation seeds 0--1; "
          "not used for any judgement): differences in shortfall, comparator minus method, pp, 99\\% conservative interval.")]
    for name, wide, cap in T:
        env = "table*" if wide else "table"
        W += [rf"\begin{{{env}}}[!t]", r"\centering", rf"\caption{{{cap}}}", rf"\label{{tab:{name.replace('tab_', '')}}}",
              r"\footnotesize", rf"\input{{generated/tables/{name}.tex}}", rf"\end{{{env}}}", ""]
    (PAPER / "generated" / "app_confirm2.tex").write_text("\n".join(W) + "\n")


def main():
    for t in (0.90, 0.93, 0.97, 0.98):
        tab_main(t, f"tab_c2_app_t{int(round(t * 1000)):04d}", full=True)
    tab_classes(); tab_dominance(); tab_alt(); tab_inter(); tab_blocks(); tab_seeds(); tab_aci(); tab_reach(); tab_trial()
    wrapper()
    print("[make_confirm2_appendix] generated/app_confirm2.tex and generated/tables/tab_c2_app_*.tex")


if __name__ == "__main__":
    main()
