"""Confirm2 figures and tables for the manuscript (request list notes/2026-10-17_confirm2_macros.md, section 3).

    python scripts/make_confirm2_tables.py          (run from paper/; `make confirm2` does this)

Figures: the locked plotting code (ccpilot confirm2_figures.py, functions f1 and f2) on the frozen analysis directory,
with the figure-level title suppressed (the LaTeX caption replaces it); nothing else changed.
  generated/figures/fig_c2_calibration.pdf     F1, pooled 56 days (scope=combined)
  generated/figures/fig_c2_cost.pdf            F2, pooled, logarithmic x axis
  generated/figures/fig_c2_calibration_block{1,2}.pdf, fig_c2_cost_block{1,2}.pdf   (appendix C)
Tables (bodies only; float and caption are in the manuscript):
  generated/tables/tab_c2_main.tex       target 0.95; 10 methods and H1-H4; compact columns (instruction 23 §8: no
                                         recall column, cost ratios to H2 and H3 only, isolation Q4 point estimate);
                                         the full columns are in S1 (tab_c2_targets, scripts/make_confirm2_appendixB.py)
  generated/tables/tab_c2_verdicts.tex   re-acquisition difference, 99% simultaneous classification
Each table body starts with a comment naming its source files and the ccpilot commit that last changed them.
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
A = "results/porto_cctv_confirm2/analysis"
REFD = "exploratory/ref_group_d/ref_group_d.csv"   # POST HOC point estimates (instruction 13 §2(f), JD decision D14-1)
sys.path.insert(0, str(REPO))
import confirm2_figures as C2F  # noqa: E402  (locked code; imported, not modified)
sys.path.insert(0, str(PAPER / "scripts"))
from ch6lib import POSTGAP_HEAD, POSTGAP_LABEL  # noqa: E402
import matplotlib.figure  # noqa: E402

ONLINE = [("mvp_log", r"\texttt{mvp\_log}"), ("qr_ogd", r"\texttt{qr\_ogd}")]
COMPARATORS = [("static", r"\texttt{static}"), ("aci_g0005", "ACI"), ("mondrian_hour_hop_speed", "Mondrian"),
               ("qr_groups", r"\texttt{qr\_groups}"), ("qr_groups_refit", r"\texttt{qr\_groups\_refit}"),
               ("qr_groups_refit7", r"\texttt{qr\_groups\_refit7}")]
OTHERS = [("citytrac_nominal", "CityTrac-style"), ("spatula_rule|fixed", "Spatula-style")]
SYM = {"improvement": "$+$", "undetermined": "$=$", "worsening": "$-$"}


def commit_of(path):
    out = subprocess.run(["git", "log", "-1", "--format=%h", "--", path], cwd=REPO, capture_output=True, text=True)
    return out.stdout.strip() or "untracked"


def srcline(paths):
    return "% source: " + "; ".join(f"{p} @ {commit_of(p)}" for p in paths)


def pp(x):
    s = f"{100 * x:.1f}"
    return "$-$" + s[1:] if s.startswith("-") else s


def ci(d, lo, hi):
    """shortfall d with its interval [lo, hi], all in pp."""
    return f"{pp(d)} [{pp(lo)}, {pp(hi)}]"


def figures():
    an = REPO / A
    keep, keep_key = matplotlib.figure.Figure.suptitle, dict(C2F.KEY)
    matplotlib.figure.Figure.suptitle = lambda self, *a, **k: None    # caption is in LaTeX
    C2F.KEY["reacquired"] = C2F.KEY["reacquired"][:2] + (POSTGAP_LABEL,)   # legend label; locked module unchanged on disk
    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            for scope, suf in (("combined", ""), ("block1", "_block1"), ("block2", "_block2")):
                p1 = C2F.f1(an, scope, td, "confirm2")
                p2 = C2F.f2(an, scope, td, "confirm2", True)
                cap = (td / f"F1_{scope}_caption.txt").read_text().strip()
                for src, dst in ((p1, f"fig_c2_calibration{suf}.pdf"), (p2, f"fig_c2_cost{suf}.pdf")):
                    shutil.copyfile(src, PAPER / "generated" / "figures" / dst)
                print(f"[figures] {scope}: F1 caption note from the locked code: {cap.split('; ')[-1]}")
    finally:
        matplotlib.figure.Figure.suptitle = keep
        C2F.KEY.clear(); C2F.KEY.update(keep_key)


def tab_main(t=0.95, name="tab_c2_main", full=False):
    """full=False: Table 3 (instruction 23 §8, re-discussion 2026-11-03 #15): recall, H1 and H4 ratio columns and the
    isolation Q4 interval left out; full=True: every column (S1)."""
    D = pd.read_csv(REPO / A / "deficits.csv").query("scope == 'combined' and target == @t")
    C = pd.read_csv(REPO / A / "costs.csv").query("scope == 'combined' and target == @t").set_index("method")
    R = pd.read_csv(REPO / A / "cost_ratios.csv").query("scope == 'combined' and target == @t")
    P = pd.read_csv(REPO / A / "method_points.csv").query("scope == 'combined' and target == @t").set_index("method")
    H = pd.read_csv(REPO / A / "hindsight.csv").query("scope == 'combined' and target == @t")
    # JD decision D14-1 (instruction 13 §2(f)): per-group d of H1, H3, H4, point estimates of the post-hoc exploratory file
    RG = pd.read_csv(REPO / REFD, comment="#").query("scope == 'combined' and target == @t").set_index(["reference", "group"]).d
    # plan 9.3 (verdict 21 A (d)/(h), instruction 18 §2(e)): seed range of the worst-group shortfall D^s, seed_range.csv
    SR = pd.read_csv(REPO / A / "seed_range.csv").query("scope == 'combined' and target == @t").set_index("method")
    srcs = [f"{A}/{f}" for f in ("deficits.csv", "costs.csv", "cost_ratios.csv", "method_points.csv", "hindsight.csv",
                                 "seed_range.csv")] + [REFD]
    L = [srcline(srcs),
         f"% scope=combined (56 days), target={t}, seed means; d and Dbar in pp with conservative 95% intervals "
         "(deficits.csv cells hopkind=2, nn_bin=3, WORST: deficit [lo, hi]; H rows: Dbar = t - worst_recall of "
         "method_points.csv with [t - worst_hi, t - worst_lo]); recall = recall_all (costs.csv) or hindsight.csv; cost = "
         "cost_mean (camera-seconds per hop); ratios = cost_ratios.csv ratio (H3: threshold fixed); seeds = D_seed_min-"
         "D_seed_max of seed_range.csv (pp; one value for seed-independent methods)." + ("" if full else
         " Compact (Table 3): no recall, ratios to H2 and H3 only, isolation Q4 point estimate."),
         r"\setlength{\tabcolsep}{4.5pt}",            # 11 columns with the seed range (plan 9.3) in \textwidth
         r"\begin{tabular}{@{}l" + "r" * (10 if full else 7) + "@{}}", r"\toprule",
         # compact head without "95% interval" (the caption names the intervals; David 23 (c), verdict 28 A8)
         (r" & \multicolumn{3}{c}{Shortfall (pp), 95\% interval} & & & & " if full else r" & \multicolumn{3}{c}{Shortfall (pp)} & & & ")
         + (r"\multicolumn{4}{c}{Cost ratio to} \\" if full else r"\multicolumn{2}{c}{Cost ratio to} \\"),
         r"\cmidrule(lr){2-4}" + (r"\cmidrule(l){8-11}" if full else r"\cmidrule(l){7-8}"),
         rf"Method & {POSTGAP_HEAD} $d$ & Isolation Q4 $d$ & \Dbar{{}} & $D^s$, seeds & "
         + (r"Recall & Cost & H1 & H2 & H3 & H4 \\" if full else r"Cost & H2 & H3 \\"),
         r"\midrule"]
    HS = ("H1", "H2", "H3", "H4") if full else ("H2", "H3")
    blank = " & " * len(HS)                       # empty ratio cells of the H rows

    def seeds(m):
        lo, hi = pp(SR.loc[m, "D_seed_min"]), pp(SR.loc[m, "D_seed_max"])
        return lo if lo == hi else f"{lo}--{hi}"

    def row(m, lab):
        cell = lambda c: D[(D.method == m) & (D.cell == c)].iloc[0]
        a, b, w = cell("hopkind=2"), cell("nn_bin=3"), cell("WORST")
        rr = R[R.method == m].set_index("reference").ratio
        iso = ci(b.deficit, b.lo, b.hi) if full else pp(b.deficit)
        rec = f"{C.loc[m, 'recall_all']:.3f} & " if full else ""
        return (f"{lab} & {ci(a.deficit, a.lo, a.hi)} & {iso} & {ci(w.deficit, w.lo, w.hi)} & "
                f"{seeds(m)} & {rec}{C.loc[m, 'cost_mean']:.0f} & "
                + " & ".join(f"{rr[h]:.2f}" for h in HS) + r" \\")

    for m, lab in ONLINE:
        L.append(row(m, lab))
    L.append(r"\addlinespace")
    for m, lab in COMPARATORS + OTHERS:
        L.append(row(m, lab))
    L.append(r"\addlinespace")
    for h in ("H1", "H2", "H3", "H4"):
        if h == "H2":
            hh = H[H.reference == "H2"].groupby("method")[["cost_mean", "recall_all"]].mean()
            hh = hh.loc[[m for m, _ in ONLINE + COMPARATORS + OTHERS]]
            rec = f"{hh.recall_all.min():.3f}--{hh.recall_all.max():.3f} & " if full else ""
            L.append(rf"H2$^{{a}}$ & --- & --- & --- & & {rec}"         # no shortfall of its own (instruction 31 §2, Y4)
                     rf"{hh.cost_mean.min():.0f}--{hh.cost_mean.max():.0f}{blank}\\")
            continue
        p, hr = P.loc[h], H[H.reference == h].iloc[0]
        rec = f"{hr.recall_all:.3f} & " if full else ""
        L.append(rf"{h} & {pp(RG[(h, 'hopkind=2')])}$^\dagger$ & {pp(RG[(h, 'nn_bin=3')])}$^\dagger$ & "
                 rf"{pp(t - p.worst_recall)} [{pp(t - p.worst_hi)}, {pp(t - p.worst_lo)}] & & "
                 rf"{rec}{hr.cost_mean:.0f}{blank}\\")
    L += [r"\bottomrule", r"\end{tabular}", "",
          # Y4 (JD memo v12-1, instruction 31 §2): wording of Sean; the compact table (target 0.95) names the cost range
          # by macro; the full tables (targets 0.90-0.98, S4) keep the range sentence of David 23 (c)
          r"\smallskip\parbox{\textwidth}{\footnotesize $^{a}$H2 is fitted to each method's overall recall (per seed), "
          r"so it has no shortfall of its own; "
          + (r"the row gives the range over the ten methods of the seed-mean recall and cost. " if full else
             r"its mean cost ranges from \ctwoHTwoCostMin{} to \ctwoHTwoCostMax{} over the ten methods. ")
          + r"$^\dagger$Additional analysis; point estimate, no interval.}"]
    (PAPER / "generated" / "tables" / f"{name}.tex").write_text("\n".join(L) + "\n")


def tab_verdicts():
    M = pd.read_csv(REPO / A / "main_estimands.csv").query("scope == 'combined' and estimand == 'reacq_deficit_diff'")
    T = sorted(M.target.unique())
    L = [srcline([f"{A}/main_estimands.csv"]),
         "% scope=combined, estimand=reacq_deficit_diff (D_comparator - D_method), column class (99% simultaneous over "
         "the five targets, B=10000, conservative bound of the taxi and day clusters): + improvement, = undetermined, "
         "- worsening.",
         r"\setlength{\tabcolsep}{2.2pt}",
         r"\begin{tabular}{@{}l" + "c" * len(T) + "@{\hspace{6pt}}" + "c" * len(T) + "@{}}", r"\toprule",
         " & " + " & ".join(rf"\multicolumn{{{len(T)}}}{{c}}{{{lab}}}" for _, lab in ONLINE) + r" \\",
         rf"\cmidrule(r){{2-{1 + len(T)}}}\cmidrule(l){{{2 + len(T)}-{1 + 2 * len(T)}}}",
         "Comparator & " + " & ".join(f"{t:.2f}"[1:] for _ in ONLINE for t in T) + r" \\", r"\midrule"]
    for c, lab in COMPARATORS:
        cells = []
        for m, _ in ONLINE:
            for t in T:
                r = M[(M.proposed == m) & (M.comparator == c) & (M.target == t)]
                assert len(r) == 1
                cells.append(SYM[r["class"].item()])
        L.append(f"{lab} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "generated" / "tables" / "tab_c2_verdicts.tex").write_text("\n".join(L) + "\n")


def tab_custody(t=0.95):
    """POST HOC track custody (ccpilot results/porto_cctv_confirm2_posthoc/custody/custody.csv), layout of David's v3
    request (4.3): rows = 10 methods, all chains then chains starting with a re-acquisition; columns = k = 1..5 at
    target t (k = 5 with its conservative 95% interval), k = 5 at targets 0.90 and 0.98, mean cost per hop at t.
    Both blocks pooled, seed means. Caption is in appendix.tex."""
    CU = "results/porto_cctv_confirm2_posthoc/custody/custody.csv"
    C = pd.read_csv(REPO / CU, comment="#").query("scope == 'combined'")
    cost = pd.read_csv(REPO / A / "costs.csv").query("scope == 'combined' and target == @t").set_index("method").cost_mean
    T = sorted(C.target.unique()); lo_t, hi_t = T[0], T[-1]
    # POST HOC paired difference against static at k = 5 and target t (verdict 22 B, instruction 19 §3(d)): the seven
    # group-aware and calibration methods of tab_c2_custody_pairs; custody_diffs.csv, stored pair a-b turned into m - static
    CD = "results/porto_cctv_confirm2_posthoc/custody/custody_diffs.csv"
    DD = pd.read_csv(REPO / CD, comment="#").query("target == @t and scope == 'combined' and h == 5")
    PAIRED = ["mvp_log", "qr_ogd", "qr_groups", "qr_groups_refit", "qr_groups_refit7", "aci_g0005", "mondrian_hour_hop_speed"]

    def paired(m, st):
        if m not in PAIRED:
            return "--"
        r = DD[(DD.start == st) & (((DD.method_a == m) & (DD.method_b == "static")) |
                                   ((DD.method_a == "static") & (DD.method_b == m)))]
        assert len(r) == 1
        r = r.iloc[0]; sg = 1 if r.method_a == m else -1
        lo, hi = sorted((sg * r.lo, sg * r.hi))
        f = lambda v: f"{100 * v:.2f}".replace("-", "$-$")
        return f"{f(sg * r['diff'])} [{f(lo)}, {f(hi)}]"
    L = [srcline([CU, f"{A}/costs.csv", CD]),
         f"% POST HOC (decided after the confirm2 results); custody_table definition; scope=combined; seed means; k=5 at "
         f"t={t} with the conservative 95% interval (taxi and day cluster bootstraps, B=2000); cost = costs.csv cost_mean; "
         f"last column: custody(method) - custody(static) at k=5, t={t}, pp two decimals, conservative 95% paired interval "
         f"(custody_diffs.csv; seven methods, -- = not listed).",
         r"\setlength{\tabcolsep}{3.6pt}",
         r"\begin{tabular}{@{}lrrrrrrrrr@{}}", r"\toprule",
         rf" & \multicolumn{{5}}{{c}}{{Target {t:.2f}, $k$ hops}} & \multicolumn{{2}}{{c}}{{$k=5$}} & Cost & $k=5$, "
         r"$-$\,\texttt{static} \\",
         r"\cmidrule(lr){2-6}\cmidrule(lr){7-8}",
         rf"Method & 1 & 2 & 3 & 4 & 5 [95\% interval] & {lo_t:.2f} & {hi_t:.2f} & ({t:.2f}) & pp [95\% interval] \\"]
    for st, title in (("all", "All chains"), ("reacquired", f"Chains starting with a {POSTGAP_LABEL} hop")):
        n5 = int(C.query("start == @st and h == 5 and target == @t").n_chains.iloc[0])
        n1 = int(C.query("start == @st and h == 1 and target == @t").n_chains.iloc[0])
        f = lambda n: format(n, ",").replace(",", "{,}")
        L += [r"\midrule", rf"\multicolumn{{10}}{{@{{}}l}}{{\emph{{{title}}} ({f(n1)} chains at $k=1$, {f(n5)} at $k=5$)}} \\"]
        for m, lab in ONLINE + COMPARATORS + OTHERS:
            g = C.query("start == @st and method == @m")
            v = lambda tt, k: g.query("target == @tt and h == @k").iloc[0]
            r5 = v(t, 5)
            cells = [f"{v(t, k).custody:.3f}" for k in range(1, 5)] + [f"{r5.custody:.3f} [{r5.lo:.3f}, {r5.hi:.3f}]",
                     f"{v(lo_t, 5).custody:.3f}", f"{v(hi_t, 5).custody:.3f}", f"{cost[m]:.0f}", paired(m, st)]
            L.append(f"{lab} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "generated" / "tables" / "tab_c2_custody.tex").write_text("\n".join(L) + "\n")

def tab_heldout_reanalysis():
    """Handover item 14: plan 10.8 judgements of the confirmation period and of the held-out re-analysis (body only).
    Rows (plan statements S1-S4 shown as Claim 1-4): S1 core and S1 addition per method, S2 per method x refitted variant, S4 per method. Columns: judgement (status
    of claims_10_8.csv) and number of targets (from main_estimands.csv / deficits.csv) for each period."""
    P = [("Confirmation", A), ("Held-out", "results/porto_cctv_heldout_reanalysis/analysis")]
    data = {}
    for nm, a in P:
        E = pd.read_csv(REPO / a / "main_estimands.csv").query("scope == 'combined' and estimand == 'reacq_deficit_diff'")
        CL = pd.read_csv(REPO / a / "claims_10_8.csv").set_index(["method", "statement"]).status
        D = pd.read_csv(REPO / a / "deficits.csv").query("scope == 'combined' and cell == 'hopkind=2'")
        cnt = lambda p, c, cls, E=E: int(((E.proposed == p) & (E.comparator == c) & (E["class"] == cls)).sum())
        data[nm] = (CL, cnt, D)
    WORD = {"keep": "kept", "add": "added", "none": "not added", "반대였다": "opposite", "remains": "remains",
            "restrict": "qualified"}       # S4 wording of the supplementary caption (David v4, request A-9)
    srcs = [f"{a}/{f}" for _, a in P for f in ("claims_10_8.csv", "main_estimands.csv", "deficits.csv")]
    L = [srcline(srcs),
         "% status = claims_10_8.csv (locked judge; 'restrict (previous evaluation ...)' shown as 'qualified', '반대였다' as "
         "'opposite'; plan statements S1-S4 shown as Claim 1-4); targets = number of the five targets: S1 core improvement against static and against ACI; S1 addition "
         "improvement against Mondrian / qr_groups; S2 one verdict per method, worsening count per variant; S4 95% lower bound of the "
         "re-acquisition shortfall above zero.",
         r"\begin{tabular}{@{}lllrlr@{}}", r"\toprule",
         r" & & \multicolumn{2}{c}{Confirmation} & \multicolumn{2}{c}{Held-out} \\",
         r"\cmidrule(lr){3-4}\cmidrule(l){5-6}",
         r"Statement & Method & Judgment & Targets & Judgment & Targets \\", r"\midrule"]
    ML = dict(ONLINE)
    def st(nm, m, s_):
        return WORD[data[nm][0][(m, s_)].split(" (")[0]]
    for m, lab in ONLINE:
        cells = []
        for nm, _ in P:
            c = data[nm][1]
            cells += [st(nm, m, "S1 core"), f"{min(c(m, 'static', 'improvement'), c(m, 'aci_g0005', 'improvement'))}/5"]
        L.append(f"Claim 1 & {lab} & " + " & ".join(cells) + r" \\")
    for m, lab in ONLINE:       # Claim 1 addition: one verdict per method, then the targets improved per comparator
        # (Alex 25, Shannon19 X30: one row per comparator in the n/5 form of the Claim 2 rows)
        L.append(f"Claim 1 addition & {lab} & "
                 + " & ".join(f"{st(nm, m, 'S1 addition (offline group calibration)')} & " for nm, _ in P) + r" \\")
        for v, vl in (("mondrian_hour_hop_speed", "Mondrian"), ("qr_groups", r"\texttt{qr\_groups}")):
            L.append(rf"\quad improved against {vl} & & " + " & ".join(f" & {data[nm][1](m, v, 'improvement')}/5" for nm, _ in P) + r" \\")
    for m, lab in ONLINE:       # S2: one verdict per method, then the number of targets worse per refitted variant
        L.append(f"Claim 2 & {lab} & " + " & ".join(f"{st(nm, m, 'S2')} & " for nm, _ in P) + r" \\")
        for v, vl in (("qr_groups_refit", r"\texttt{qr\_groups\_refit}"), ("qr_groups_refit7", r"\texttt{qr\_groups\_refit7}")):
            L.append(rf"\quad worse than {vl} & & " + " & ".join(f" & {data[nm][1](m, v, 'worsening')}/5" for nm, _ in P) + r" \\")
    for m, lab in ONLINE:
        cells = []
        for nm, _ in P:
            D = data[nm][2]
            cells += [st(nm, m, "S4"), f"{int((D[D.method == m].lo > 0).sum())}/5"]
        L.append(f"Claim 4 & {lab} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]   # footnote a dropped: the comparator rows name the counts (Alex 25)
    (PAPER / "generated" / "tables" / "tab_heldout_reanalysis.tex").write_text("\n".join(L) + "\n")

def main():
    figures()
    tab_main()
    tab_verdicts()
    tab_custody()
    tab_heldout_reanalysis()
    print("[make_confirm2_tables] fig_c2_calibration(.pdf, _block1, _block2), fig_c2_cost(...), tab_c2_main, tab_c2_verdicts")


if __name__ == "__main__":
    main()
