"""Appendix B (confirmation experiment, further results): the seven floats named in David's v3k frames.

    python scripts/make_confirm2_appendixB.py        (run from paper/; after make_confirm2_tables.py)

Outputs (bodies only; captions are in appendix.tex):
  generated/tables/tab_c2_targets.tex      targets 0.90, 0.93, 0.97, 0.98 in the layout of tab_c2_main
  generated/tables/tab_c2_classify.tex     classification of all pre-specified comparisons (3 estimates) + dominance counts
  generated/figures/fig_c2_blocks.pdf      per-block F1 (top) and F2 (bottom), block 1 left, block 2 right
  generated/tables/tab_c2_blocks.tex       between-block differences (autumn minus August): Dbar with 95% interval,
                                           re-acquisition shortfall (point only; no interval in the result files)
  generated/tables/tab_c2_partitions.tex   alternative partitions (paired difference) and intersections I1-I6
  generated/tables/tab_c2_diagnostics.tex  seed ranges (Dbar, re-acquisition), ACI variants, a_min share, reachable bounds
  generated/tables/tab_c2_tuning.tex       tuning history (research records, precheck A9) and trial run on exploratory 1
Sources: frozen results/porto_cctv_confirm2 (analysis/, runs/*/summary.csv, figures from the locked plotting code via
make_confirm2_tables.py), results/precheck_confirm2 (trial_expl1/analysis, precheck_report2.md A9), configs.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))   # work copy outside ccpilot: CCPILOT_REPO=/home/user/ccpilot
sys.path.insert(0, str(PAPER / "scripts"))
from make_confirm2_tables import COMPARATORS, ONLINE, OTHERS, SYM, ci, pp, srcline, tab_main  # noqa: E402
import make_confirm2_appendix as APX  # noqa: E402
from ch6lib import POSTGAP_HEAD, POSTGAP_LABEL  # noqa: E402

A = "results/porto_cctv_confirm2/analysis"
TABLES = PAPER / "generated" / "tables"
FIGS = PAPER / "generated" / "figures"
ALL_M = ONLINE + COMPARATORS + OTHERS
LAB = dict(ALL_M)


def body(path):
    """lines of a generated tabular file without its leading comments."""
    return [ln for ln in path.read_text().splitlines() if not ln.startswith("%")]


def tabular_rows(lines):
    """(header lines up to and incl. the first \\midrule, data rows, tail from \\bottomrule)."""
    i = lines.index(r"\midrule"); j = lines.index(r"\bottomrule")
    return lines[:i + 1], lines[i + 1:j], lines[j:]


def tab_targets():
    tmp = TABLES / "_tmp_target.tex"
    heads, parts, tail = None, [], None
    for t in (0.90, 0.93, 0.97, 0.98):        # S2 (a): every column; 0.95 is panel (b) (verdict 28 A2, instruction 24 §5)
        tab_main(t, "_tmp_target", full=True)
        h, rows, tl = tabular_rows(body(tmp))
        heads = heads or h; tail = tail or tl
        parts += ([r"\midrule"] if parts else []) + [rf"\multicolumn{{11}}{{@{{}}l}}{{\emph{{Target {t:.2f}}}}} \\"] + rows
    tmp.unlink()
    src = [f"{A}/{f}" for f in ("deficits.csv", "costs.csv", "cost_ratios.csv", "method_points.csv", "hindsight.csv")]
    L = [srcline(src), "% as tab_c2_main (make_confirm2_tables.tab_main, full=True: every column) at targets 0.90, 0.93, 0.97, 0.98, stacked."]
    (TABLES / "tab_c2_targets.tex").write_text("\n".join(L + heads + parts + tail) + "\n")


def tab_targets_b(t=0.95):
    """S2 (b) (verdict 28 A2, instruction 24 §5): target 0.95, the columns that Table 3 leaves out: overall recall, cost
    ratio to H1 and H4, isolation Q4 shortfall with its interval; H rows: recall (H2: range over the ten methods)."""
    D = pd.read_csv(REPO / A / "deficits.csv").query("scope == 'combined' and target == @t and cell == 'nn_bin=3'").set_index("method")
    C = pd.read_csv(REPO / A / "costs.csv").query("scope == 'combined' and target == @t").set_index("method")
    R = pd.read_csv(REPO / A / "cost_ratios.csv").query("scope == 'combined' and target == @t").set_index(["method", "reference"]).ratio
    H = pd.read_csv(REPO / A / "hindsight.csv").query("scope == 'combined' and target == @t")
    from make_confirm2_tables import REFD                       # H rows: post-hoc point estimates, as in Table 3
    RG = pd.read_csv(REPO / REFD, comment="#").query("scope == 'combined' and target == @t").set_index(["reference", "group"]).d
    src = [f"{A}/{f}" for f in ("deficits.csv", "costs.csv", "cost_ratios.csv", "hindsight.csv")] + [REFD]
    L = [srcline(src), f"% scope=combined (56 days), target={t}, seed means; recall = recall_all (costs.csv; H rows hindsight.csv, "
         "H2: min-max over the ten methods); ratios = cost_ratios.csv ratio; isolation Q4 d = deficits.csv cell nn_bin=3 in pp "
         "with the conservative 95% interval; H rows: point estimates of ref_group_d.csv (no interval), as in Table 3.",
         r"\setlength{\tabcolsep}{4.5pt}", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r"Method & Recall & Cost/H1 & Cost/H4 & Isolation Q4 $d$ \\", r"\midrule"]
    for k, (m, lab) in enumerate(ALL_M):
        if k == len(ONLINE):
            L.append(r"\addlinespace")
        b = D.loc[m]
        L.append(f"{lab} & {C.loc[m, 'recall_all']:.3f} & {R[(m, 'H1')]:.2f} & {R[(m, 'H4')]:.2f} & {ci(b.deficit, b.lo, b.hi)}" + r" \\")
    L.append(r"\addlinespace")
    for h in ("H1", "H2", "H3", "H4"):
        if h == "H2":
            hh = H[H.reference == "H2"].groupby("method").recall_all.mean().loc[[m for m, _ in ALL_M]]
            L.append(rf"H2$^{{a}}$ & {hh.min():.3f}--{hh.max():.3f} & & & --- \\")   # instruction 31 §2 (Y4)
        else:
            L.append(rf"{h} & {H[H.reference == h].iloc[0].recall_all:.3f} & & & {pp(RG[(h, 'nn_bin=3')])}$^\dagger$ \\")
    L += [r"\bottomrule", r"\end{tabular}", "",       # footnote a as in Table 3 (instruction 31 §2, Y4)
          r"\smallskip\parbox{\textwidth}{\footnotesize $^{a}$H2 is fitted to each method's overall recall (per seed), "
          r"so it has no shortfall of its own; its mean cost ranges from \ctwoHTwoCostMin{} to \ctwoHTwoCostMax{} over the "
          r"ten methods.}"]
    (TABLES / "tab_c2_targets_b.tex").write_text("\n".join(L) + "\n")


def tab_classify():
    APX.tab_classes(); APX.tab_dominance()
    a = body(TABLES / "tab_c2_app_classes.tex"); d = body(TABLES / "tab_c2_app_dominance.tex")
    L = [srcline([f"{A}/main_estimands.csv", f"{A}/dominance.csv"]),
         "% upper: class of every pre-specified comparison (99% simultaneous, conservative); lower: number of pairs of target "
         "points (any target of one method against any target of the other) in which one point dominates the other "
         "(interval dominance, 95%, plan 10.5), from dominance.csv."]
    L += a + ["", r"\medskip", r"\textit{Dominance: pairs of target points in which the online method dominates the comparator, "
              r"and in which the comparator dominates the online method.}", r"\smallskip", ""] + d
    (TABLES / "tab_c2_classify.tex").write_text("\n".join(L) + "\n")


def fig_blocks():
    """2 x 2 composition of the per-block F1 and F2 PDFs (vector) with pdflatex."""
    files = [FIGS / f for f in ("fig_c2_calibration_block1.pdf", "fig_c2_calibration_block2.pdf",
                                "fig_c2_cost_block1.pdf", "fig_c2_cost_block2.pdf")]
    assert all(f.exists() for f in files), "run make_confirm2_tables.py first"
    tex = r"""\documentclass{article}
\usepackage[paperwidth=17.6cm,paperheight=13.5cm,margin=0pt]{geometry}
\usepackage{graphicx}
\pagestyle{empty}
\begin{document}\noindent
\parbox[t]{8.7cm}{\centering\small Block 1 (August)\\\includegraphics[width=8.7cm]{%s}}\hfill
\parbox[t]{8.7cm}{\centering\small Block 2 (autumn)\\\includegraphics[width=8.7cm]{%s}}\\[2mm]
\noindent\includegraphics[width=8.7cm]{%s}\hfill\includegraphics[width=8.7cm]{%s}
\end{document}
""" % tuple(str(f) for f in files)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "blocks.tex").write_text(tex)
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "blocks.tex"], cwd=td, capture_output=True, text=True)
        assert (Path(td) / "blocks.pdf").exists(), r.stdout[-2000:]
        shutil.copyfile(Path(td) / "blocks.pdf", FIGS / "fig_c2_blocks.pdf")


BLOCKS_S10 = ["mvp_log", "qr_ogd", "qr_groups_refit", "mondrian_hour_hop_speed"]   # verdict 15 B, instruction 14 §2


def tab_blocks(methods=None, name="tab_c2_blocks"):
    """between-block differences; methods=None: all methods and the post-gap panel (R3 of the repository bundle)."""
    B = pd.read_csv(REPO / A / "block_comparison.csv")
    D = pd.read_csv(REPO / A / "deficits.csv").query("cell == 'hopkind=2' and scope in ['block1', 'block2']")
    T = sorted(B.target.unique())
    L = [srcline([f"{A}/block_comparison.csv", f"{A}/deficits.csv"]),
         "% Dbar: -(diff) of block_comparison.csv (= D_block2 - D_block1, autumn minus August) with [-hi, -lo] (conservative "
         "95%: taxi paired, day independent); re-acquisition: deficit(block2) - deficit(block1) of deficits.csv cell "
         "hopkind=2, point only (no interval for this difference in the result files).",
         r"\setlength{\tabcolsep}{3.4pt}",
         r"\begin{tabular}{@{}l" + "r" * len(T) + "@{}}", r"\toprule",
         "Method & " + " & ".join(f"{t:.2f}" for t in T) + r" \\", r"\midrule",
         rf"\multicolumn{{{1 + len(T)}}}{{@{{}}l}}{{\emph{{Worst-group shortfall \Dbar{{}}, autumn minus August (pp), 95\% interval}}}} \\"]
    rows_m = [(m, lab) for m, lab in ALL_M if methods is None or m in methods]
    if methods is not None:
        # S10 (verdict 17 A4): per-block Dbar (points) and their difference with the interval, one row per method and target
        rows_m = sorted(rows_m, key=lambda x: methods.index(x[0]))
        L = L[:1] + [L[1] + " Block 1, block 2: D_block1, D_block2 of block_comparison.csv (points). Rows: "
                     f"{', '.join(methods)} (shortened from the full table; Dbar only).", L[2],
                     r"\begin{tabular}{@{}llrrr@{}}", r"\toprule",
                     r"Method & Target & Block~1 \Dbar{} & Block~2 \Dbar{} & Difference [95\%] \\", r"\midrule"]
        for k, (m, lab) in enumerate(rows_m):
            if k:
                L.append(r"\addlinespace")
            for j, t in enumerate(T):
                r = B[(B.method == m) & (B.target == t)].iloc[0]
                L.append(f"{lab if j == 0 else ''} & {t:.2f} & {pp(r.D_block1)} & {pp(r.D_block2)} & "
                         f"{ci(-r['diff'], -r.hi, -r.lo)} " + r"\\")
        L += [r"\bottomrule", r"\end{tabular}"]
        (TABLES / f"{name}.tex").write_text("\n".join(L) + "\n")
        return
    for m, lab in rows_m:
        cells = []
        for t in T:
            r = B[(B.method == m) & (B.target == t)].iloc[0]
            cells.append(ci(-r["diff"], -r.hi, -r.lo))
        L.append(f"{lab} & " + " & ".join(cells) + r" \\")
    L += [r"\midrule", rf"\multicolumn{{{1 + len(T)}}}{{@{{}}l}}{{\emph{{{POSTGAP_HEAD} shortfall, autumn minus August (pp), point estimate}}}} \\"]
    for m, lab in ALL_M:
        cells = []
        for t in T:
            v = D[(D.method == m) & (D.target == t) & (D.scope == "block2")].deficit.item() - \
                D[(D.method == m) & (D.target == t) & (D.scope == "block1")].deficit.item()
            cells.append(pp(v))
        L.append(f"{lab} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    (TABLES / f"{name}.tex").write_text("\n".join(L) + "\n")


def tab_partitions():
    APX.tab_alt(); APX.tab_inter()
    ha, ra, ta = tabular_rows(body(TABLES / "tab_c2_app_alt.tex"))
    hi_, ri, _ = tabular_rows(body(TABLES / "tab_c2_app_inter.tex"))
    T = 5
    L = [srcline([f"{A}/alt_partitions.csv", f"{A}/intersections.csv"]),
         "% upper: alt_partitions.csv SUMMARY, diff_vs_D [diff_lo, diff_hi] (pp, conservative 95%); lower: intersections.csv "
         "deficit [lo, hi] (pp, conservative 95%); n = hops (pooled)."]
    hdr = [ln for ln in ha if not ln.startswith(r"Method &")]
    L += hdr[:-1] + [r"Method & Partition / intersection & " + " & ".join(["0.90", "0.93", "0.95", "0.97", "0.98"]) + r" \\",
                     r"\midrule", rf"\multicolumn{{{2 + T}}}{{@{{}}l}}{{\emph{{Alternative partitions: largest shortfall minus \Dbar{{}} on the 25 groups}}}} \\"]
    L += ra + [r"\midrule", rf"\multicolumn{{{2 + T}}}{{@{{}}l}}{{\emph{{Intersections I1--I6: shortfall (hops)}}}} \\"] + ri + ta
    (TABLES / "tab_c2_partitions.tex").write_text("\n".join(L) + "\n")


def tab_diagnostics():
    S = pd.read_csv(REPO / A / "seed_range.csv").query("scope == 'combined'")
    G = pd.read_csv(REPO / A / "group_recall.csv").query("scope == 'combined' and group == 'hopkind=2'")
    D = pd.read_csv(REPO / A / "deficits.csv").query("scope == 'combined' and cell == 'hopkind=2'")
    T = sorted(S.target.unique())
    L = [srcline([f"{A}/seed_range.csv", f"{A}/group_recall.csv", f"{A}/deficits.csv",
                  "results/porto_cctv_confirm2/runs/<block>/t<target>/s<seed>/summary.csv", f"{A}/a_min_reach.csv",
                  f"{A}/reachable_bound.csv"]),
         "% (a) Dbar: seed_range.csv D_seed_min-D_seed_max (seed_range_over_ci_width); re-acquisition: min-max over seeds "
         "of group_recall.csv deficit (hopkind=2), ratio = range / (hi - lo) of deficits.csv; (b) ACI variants: run summaries "
         "(coverage, as-run worst group, cost; seed means per block; no interval); (c) a_min_reach.csv target 0.98; "
         "(d) reachable_bound.csv U_G.",
         r"\setlength{\tabcolsep}{3.2pt}",
         r"\begin{tabular}{@{}ll" + "r" * len(T) + "@{}}", r"\toprule",
         "Method & Quantity & " + " & ".join(f"{t:.2f}" for t in T) + r" \\", r"\midrule",
         rf"\multicolumn{{{2 + len(T)}}}{{@{{}}l}}{{\emph{{(a) Range over the {S.groupby(['method', 'target']).size().shape[0] and 5} seeds, pp (ratio to the 95\% interval width)}}}} \\"]
    for m, lab in ALL_M:
        c1, c2 = [], []
        for t in T:
            r = S[(S.method == m) & (S.target == t)].iloc[0]
            c1.append(f"{pp(r.D_seed_min)}--{pp(r.D_seed_max)} ({r.seed_range_over_ci_width:.2f})")
            g = G[(G.method == m) & (G.target == t)].deficit
            dd = D[(D.method == m) & (D.target == t)].iloc[0]
            c2.append(f"{pp(g.min())}--{pp(g.max())} ({(g.max() - g.min()) / (dd.hi - dd.lo):.2f})")
        L.append(f"{lab} & \\Dbar{{}} & " + " & ".join(c1) + r" \\")
        L.append(f" & {POSTGAP_HEAD} $d$ & " + " & ".join(c2) + r" \\")   # post-gap label (verdict 25 A2)
    # (b) ACI variants
    recs = []
    for blk in ("block1", "block2"):
        for tdir in sorted((REPO / "results/porto_cctv_confirm2/runs" / blk).glob("t*")):
            for sd in sorted(p for p in tdir.glob("s*") if p.is_dir()):
                s = pd.read_csv(sd / "summary.csv")
                s = s[(s.predictor == "src_zone_hour_speed") & s.method.str.startswith("aci")]
                for _, r in s.iterrows():
                    recs.append(dict(block=blk, target=r.target, method=r.method, cov=r.coverage, worst=r.worst_group_cov,
                                     cost=r.cost_mean_cam_s))
    R = pd.DataFrame(recs).groupby(["method", "target"])[["cov", "worst", "cost"]].mean()   # mean over seeds and blocks
    names = {"aci_g0005": r"ACI $\gamma=0.0005$ (main)", "aci_g001": r"ACI $\gamma=0.001$",
             "aci_hophour_g001f": r"ACI per time of day $\times$ first hop"}   # caption wording (verdict 35 A27)
    L += [r"\midrule", rf"\multicolumn{{{2 + len(T)}}}{{@{{}}l}}{{\emph{{(b) ACI variants (mean over seeds and the two blocks; no interval): recall / worst group / cost}}}} \\"]
    for m, nm in names.items():
        L.append(f"{nm} & recall / worst / cost & " + " & ".join(
            f"{R.loc[(m, t), 'cov']:.3f} / {R.loc[(m, t), 'worst']:.3f} / {R.loc[(m, t), 'cost']:.0f}" for t in T) + r" \\")
    am = pd.read_csv(REPO / A / "a_min_reach.csv").query("target == 0.98").sort_values("seed")
    U = pd.read_csv(REPO / A / "reachable_bound.csv").query("scope == 'combined'").set_index("group")
    L += [r"\midrule", rf"\multicolumn{{{2 + len(T)}}}{{@{{}}l}}{{\emph{{(c) \texttt{{mvp\_log}} hops at $a_{{\min}}$, target 0.98, seeds 0--4 (\%): "
          + ", ".join(f"{100 * v:.4f}" for v in am.mvp_log_hops_at_a_min_share) + r"}} \\",
          rf"\multicolumn{{{2 + len(T)}}}{{@{{}}l}}{{\emph{{(d) Reachable upper bound of recall $U_G$: {POSTGAP_LABEL} {U.loc['hopkind=2', 'U_G']:.4f}, "
          rf"isolation Q4 {U.loc['nn_bin=3', 'U_G']:.4f}}}}} \\",
          r"\bottomrule", r"\end{tabular}"]
    (TABLES / "tab_c2_diagnostics.tex").write_text("\n".join(L) + "\n")


def tab_tuning():
    """Tuning history: research records (precheck_report2.md A9; before the pre-registration tag, not verifiable in git),
    translated cell by cell; trial run on exploratory period 1 (target 0.95, seeds 0-1): Dbar from group_recall.csv
    (seed-mean recall per group, worst of the 25 groups), cost ratio to H1 from cost_ratios.csv."""
    TA = "results/precheck_confirm2/trial_expl1/analysis"
    G = pd.read_csv(REPO / TA / "group_recall.csv")
    G = G[G.judged.astype(str) == "True"]
    CR = pd.read_csv(REPO / TA / "cost_ratios.csv").query("reference == 'H1'").set_index("method").point
    def trial(m):
        g = G[G.method == m].groupby("group").recall.mean()
        return f"{100 * (0.95 - g.min()):.1f}", f"{CR[m]:.2f}"
    HIST = [  # (method key in trial, label, parameters, chosen on, variants recorded)
        ("static", r"\texttt{static}", "none", "--", "--"),
        ("aci_g0005", "ACI", r"$\gamma \in \{0.005, 0.001, 0.0005\}$, floor $\alpha/5$, per hour $\times$ first hop; window 2{,}000 (initial value)",
         "expl.\\ 1 (virtual layout), then expl.\\ 2 (virtual)", "5, then 3 kept"),
        ("mondrian_hour_hop_speed", "Mondrian", "cells (hour, first hop, hour $\\times$ first hop; later speed and hour $\\times$ first hop $\\times$ speed, 40 cells); minimum 200",
         "expl.\\ 1, then expl.\\ 2 (virtual)", "5"),
        ("qr_groups", r"\texttt{qr\_groups}", "log scale (linear scale gave negative $\\tau$); at most 80{,}000 rows", "exploratory", "2 scales"),
        ("qr_groups_refit", r"\texttt{qr\_groups\_refit}", "as \\texttt{qr\\_groups}, refitted daily, cumulative", "defined before the trial run", "1"),
        ("qr_groups_refit7", r"\texttt{qr\_groups\_refit7}", "as \\texttt{qr\\_groups}, refitted daily, 7-day window", "defined before the trial run", "1"),
        ("qr_ogd", r"\texttt{qr\_ogd}", "$\\gamma = 0.005$, clip 3", "exploratory", "1"),
        ("mvp_log", r"\texttt{mvp\_log}", "log scale, $a_{\\min} = 0.002$, $m = 40$", "expl.\\ 1 and 2 (real layout)", "1"),
        ("spatula_rule|fixed", "Spatula-style", "share threshold 0.05, delay quantile 0.98", "from the reading of the paper", "--"),
        ("citytrac_rule|target095", "CityTrac-style", "delay window quantile 0.98, minimum 30 per key", "from the reading of the paper", "--"),
    ]
    L = [srcline(["results/precheck_confirm2/precheck_report2.md", f"{TA}/group_recall.csv", f"{TA}/cost_ratios.csv",
                  "configs/porto_cctv_confirm2.yaml"]),
         "% tuning history: precheck_report2.md section A9 (research records README v2-v7; before the pre-registration tag, not "
         "verifiable in git), translated; refit variants: plan section 3 and commit dcc7f9f; baseline parameters: run config. "
         "Trial: exploratory period 1, target 0.95, evaluation seeds 0-1; Dbar = 0.95 - min over the judged groups of the "
         "seed-mean recall (pp); cost ratio to H1 (cost_ratios.csv point). CityTrac-style at nominal 0.95.",
         r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular}{@{}lp{6.2cm}p{3.6cm}lrr@{}}", r"\toprule",
         r" & & & & \multicolumn{2}{c}{Trial run} \\", r"\cmidrule(l){5-6}",
         r"Method & Tuned parameters & Chosen on & Variants & \Dbar{} (pp) & Cost/H1 \\", r"\midrule"]
    for key, lab, par, per, var in HIST:
        d, c = trial(key)
        L.append(f"{lab} & {par} & {per} & {var} & {d} & {c}" + r" \\")
    L += [r"\midrule",
          r"Predictor & hierarchy src $\to$ zone $\to$ hour $\to$ speed; $\lambda = 20$, $\varepsilon = 10^{-4}$, $\sigma = 1$ bin & expl.\ 1 and 2 & 5 & & \\",
          r"Groups, criteria & 25 groups; bar 0.94 (first draft); cost bound 1.20 & research records & -- & & \\",
          r"\midrule",
          r"Trial run (pre-lock) & detection-time output compared in float64 like the score (the first trial run stopped on the consistency check); output code only, no method, comparator, or parameter changed (commit \texttt{b5e10e6}) & exploratory period 1 & -- & & \\",
          r"\bottomrule", r"\end{tabular}", "",
          r"\smallskip\parbox{\textwidth}{\footnotesize Tuning history before the pre-registration tag (\texttt{prereg-v3}): research records (README versions 2--7 and internal deviation notes), not verifiable in the version history. Trial run: exploratory period 1, target 0.95, evaluation seeds 0--1, made before the lock of the confirmation plan.}"]
    (TABLES / "tab_c2_tuning.tex").write_text("\n".join(L) + "\n")


def main():
    tab_targets(); tab_targets_b(); tab_classify(); fig_blocks(); tab_blocks(BLOCKS_S10); tab_blocks(None, "tab_c2_blocks_full"); tab_partitions(); tab_diagnostics(); tab_tuning()
    print("[make_confirm2_appendixB] tab_c2_targets, tab_c2_targets_b, tab_c2_classify, fig_c2_blocks, tab_c2_blocks (S10), tab_c2_blocks_full (R3), tab_c2_partitions, "
          "tab_c2_diagnostics, tab_c2_tuning")


if __name__ == "__main__":
    main()
