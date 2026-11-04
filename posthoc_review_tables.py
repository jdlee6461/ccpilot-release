"""POST HOC (added during revision (internal review), Sean instruction 02 §7, 04 §2): aggregate tables, macros and the
mechanical consequence check.

    python posthoc_review_tables.py

Inputs: review/{A,B_aci,B_refit,B_refit_b,C}_{estimates,differences,groups,intersections}.csv (posthoc_review_report.py
--collect). Outputs:
  review/aggregate/*.csv           copies of the collected csv with a header line (definition-file sha256)
  review/aggregate/consequence_check.csv   conditions A1-A4, B0-B6, C1-C3 of REVIEW_PLAN appendix R evaluated
                                   mechanically (condition, value, satisfied); no sentence is chosen
  review/tables/tab_review_{baselines,feedback,predictors}.tex   combined scope, target 0.95
  review/review_numbers.tex        macros appended (prefix \\ctwoRev..., POST HOC); instruction 04 §2 (A-22) adds pp
                                   macros (D x 100, one decimal), ranges and text lists from consequence_check;
                                   instruction 07 §1 adds F2 pp macros, F3 aggregate/A1_worst_group.csv, F4
                                   aggregate/A1_cost_vs_qr.csv, F5 the Mondrian row of tab_review_predictors
Tables (instruction 04 §2, A-23): D and re-acquisition d in pp (x 100, one decimal), cost / H2 two decimals.
No §10.8 judgement words. Intervals: 95%, taxi and day cluster bootstraps (B = 2,000), conservative bounds.
"""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import posthoc_review_common as C

# label of hopkind 2 in the tables: paper scripts/ch6lib.py POSTGAP_LABEL (verdict 14 A2); PAPER_REPO = a paper checkout
# that has it (default: paper/ of this repository)
sys.path.insert(0, str(Path(os.environ.get("PAPER_REPO", Path(__file__).resolve().parent / "paper")) / "scripts"))
from ch6lib import POSTGAP_HEAD  # noqa: E402

AGG = C.OUT / "aggregate"; TAB = C.OUT / "tables"
DEFS = ["configs/confirm2_analysis.yaml", str(C.OUT / "REVIEW_PLAN.md")]
T = 0.95
NAME = {"static": "static", "aci_g0005": "ACI", "mondrian_hour_hop_speed": "Mondrian (40 cells)",
        "A1_mondrian_small": "Mondrian (small)", "A2_aci_groups": "group-wise ACI", "A3_qr_groups_inter": "qr\\_groups + I1--I6",
        "qr_groups": "qr\\_groups", "qr_groups_refit": "qr\\_groups\\_refit", "mvp_log": "mvp\\_log", "qr_ogd": "qr\\_ogd"}
MAC = {"static": "Static", "aci_g0005": "Aci", "mondrian_hour_hop_speed": "Mondrian", "A1_mondrian_small": "MondrianSmall",
       "A2_aci_groups": "AciGroups", "A3_qr_groups_inter": "QrInter", "qr_groups": "Qrgroups", "qr_groups_refit": "Qrrefit",
       "mvp_log": "MvpLog", "qr_ogd": "QrOgd"}
LEVEL = {"grp_all": {0: "All hops"},                                   # group names of paper scripts/ch6lib.py LEVEL_NAME
         "hgroup": {0: "00-06 h", 1: "06-10 h", 2: "10-16 h", 3: "16-20 h", 4: "20-24 h"},
         "hopkind": {0: "Later", 1: "Initiated", 2: POSTGAP_HEAD},
         "speed_bin": {0: "Speed Q1 (slow)", 1: "Speed Q2", 2: "Speed Q3", 3: "Speed Q4 (fast)"},
         "zone": {0: "Exit east", 1: "Exit north", 2: "Exit west", 3: "Exit south"},
         "entropy_bin": {0: "Branching Q1 (low)", 1: "Branching Q2", 2: "Branching Q3", 3: "Branching Q4 (high)"},
         "nn_bin": {0: "Isolation Q1 (low)", 1: "Isolation Q2", 2: "Isolation Q3", 3: "Isolation Q4 (high)"}}
EST = {"D": "Dbar", "reacq_d": "Reacq", "cost_ratio_H2": "CostHtwo"}
SETS = {"full": {"ACI": "aci_g0005", "group-wise ACI": "A2_aci_groups", "mvp\\_log": "mvp_log", "qr\\_ogd": "qr_ogd",
                 "refit": "qr_groups_refit"},
        "(i)": {"ACI": "Bi_aci", "mvp\\_log": "mvp_log", "qr\\_ogd": "qr_ogd", "refit": "Bi_refit_a"},
        "(ii)": {"ACI": "Bii_aci", "mvp\\_log": "Bii_mvp_log", "qr\\_ogd": "Bii_qr_ogd", "refit": "Bii_refit_a"},
        "(iii)": {"ACI": "iii_aci", "group-wise ACI": "iii_aci_groups", "mvp\\_log": "iii_mvp_log", "qr\\_ogd": "iii_qr_ogd",
                  "refit": "Bi_refit_a"},
        "(iv)": {"ACI": "iv_aci", "group-wise ACI": "iv_aci_groups", "mvp\\_log": "iv_mvp_log", "qr\\_ogd": "iv_qr_ogd",
                 "refit": "Bii_refit_a"}}
SETMAC = {"full": "Full", "(i)": "One", "(ii)": "Two", "(iii)": "Three", "(iv)": "Four"}
METMAC = {"ACI": "Aci", "group-wise ACI": "AciGroups", "mvp\\_log": "MvpLog", "qr\\_ogd": "QrOgd", "refit": "Refit"}


IVHEAD = ("# Interval columns (level 0.95, B = 2,000 replicates per cluster type, bootstrap seed 20261013 after the "
          "10,000 main draws of confirm2_analysis): lo_taxi/hi_taxi = 2.5/97.5 percentiles over the taxi-cluster replicates "
          "(multinomial weights over taxis, joint over blocks); lo_day/hi_day = the same over the day-cluster replicates "
          "(days resampled within block); lo = min(lo_taxi, lo_day), hi = max(hi_taxi, hi_day) (conservative). Each "
          "replicate takes the seed mean (seeds 0-4) of the estimand; differences are taken per replicate before the "
          "percentiles; H2 is refitted in every replicate (cost ratios).\n")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(part, kind):
    f = C.OUT / f"{part}_{kind}.csv"
    return pd.read_csv(f) if f.exists() else pd.DataFrame()


def f3(x, nd=3):
    s = f"{x:.{nd}f}"
    return s.replace("-", "$-$") if s.startswith("-") else s


def cell(E, label, method, est, scope="combined", t=T, nd=3):
    r = E[(E.label == label) & (E.method == method) & (E.estimand == est) & (E.scope == scope) & (np.isclose(E.target, t))]
    if len(r) != 1:
        return None
    return r.iloc[0]


def fmt_cell(r, nd=3, k=1.0):
    return "--" if r is None else f"{f3(k * r.point, nd)} [{f3(k * r.lo, nd)}, {f3(k * r.hi, nd)}]"


def tcell(r, e):                         # table cell: D and re-acquisition d in pp (one decimal), cost / H2 two decimals
    return fmt_cell(r, 2) if e == "cost_ratio_H2" else fmt_cell(r, 1, 100.0)


def tlist(xs):
    xs = list(xs)
    return ", ".join(xs[:-1]) + ("," if len(xs) > 2 else "") + " and " + xs[-1] if len(xs) > 1 else "".join(xs)


def diff(Dd, label, comp, ref, est, scope="combined", t=T):
    r = Dd[(Dd.label == label) & (Dd.comparator == comp) & (Dd.reference == ref) & (Dd.estimand == f"{est}_diff")
           & (Dd.scope == scope) & (np.isclose(Dd.target, t))]
    return None if len(r) != 1 else r.iloc[0]


def main():
    AGG.mkdir(parents=True, exist_ok=True); TAB.mkdir(parents=True, exist_ok=True)
    head = "# POST HOC (external review). Definition files: " + "; ".join(f"{d} sha256 {sha(d)}" for d in DEFS) + "\n"
    for f in sorted(C.OUT.glob("*_estimates.csv")) + sorted(C.OUT.glob("*_differences.csv")) + \
            sorted(C.OUT.glob("*_groups.csv")) + sorted(C.OUT.glob("*_intersections.csv")):
        if f.name.startswith(("A_", "B_", "C_")):
            (AGG / f.name).write_text(head + IVHEAD + f.read_text())
    EA, DA, IA = load("A", "estimates"), load("A", "differences"), load("A", "intersections")
    EB, DB = load("B_aci", "estimates"), load("B_aci", "differences")
    ER, DR = load("B_refit", "estimates"), load("B_refit", "differences")
    EC, DC = load("C", "estimates"), load("C", "differences")
    EV, DV = load("B_v", "estimates"), load("B_v", "differences")
    mac = []

    def addm(name, val, src):            # source file cited with the ccpilot commit that last changed it
        f = src.split(":", 1)[0]
        h = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(C.OUT.parent / f)], capture_output=True,
                           text=True).stdout.strip() or "uncommitted"
        src = src.replace(f"{f}:", f"{f} @ {h}:", 1)
        mac.append(f"% {src}"); mac.append(f"\\newcommand{{\\{name}}}{{{val}\\xspace}}")

    # ---- A table (target 0.95, combined)
    # v6 Table 5 (instruction 14 §2): last column = Dbar under label set (iv), same cells as tab_review_feedback (iv)
    IV = {"aci_g0005": "ACI", "A2_aci_groups": "group-wise ACI", "qr_groups_refit": "refit", "mvp_log": "mvp\\_log",
          "qr_ogd": "qr\\_ogd"}
    rows = ["\\begin{tabular}{@{}lcccc@{}}", "\\toprule",
            "Method & $\\bar{D}$ & " + POSTGAP_HEAD + " $d$ & Cost / H2 & $\\bar{D}$ under (iv) \\\\", "\\midrule"]
    for m in ["static", "aci_g0005", "mondrian_hour_hop_speed", "A1_mondrian_small", "A2_aci_groups", "A3_qr_groups_inter",
              "qr_groups", "qr_groups_refit", "mvp_log", "qr_ogd"]:
        cs = [cell(EA, "A", m, e) for e in ("D", "reacq_d", "cost_ratio_H2")]
        iv = None
        if m in IV:
            mi = SETS["(iv)"][IV[m]]
            iv = cell(EB, "B_aci", mi, "D") if mi not in ("qr_groups_refit", "Bi_refit_a", "Bii_refit_a") else \
                cell(ER, "B_refit", mi, "D")
            assert iv is not None, m
        rows.append(f"\\texttt{{{NAME[m]}}} & " + " & ".join(tcell(c, e)
                                                         for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2")))
                    + " & " + tcell(iv, "D") + " \\\\")
        for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2")):
            if c is not None:
                nd = 2 if e == "cost_ratio_H2" else 3
                for suf, v in (("", c.point), ("Lo", c.lo), ("Hi", c.hi)):
                    addm(f"ctwoRevBase{MAC[m]}{EST[e]}{suf}", f3(v, nd),
                         f"review/A_estimates.csv: label A, method {m}, estimand {e}, scope combined, target 0.95, "
                         f"seed mean, 95% conservative | raw {v!r}")
    rows += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_review_baselines.tex").write_text(
        "% POST HOC (added during revision (internal review)), generated by posthoc_review_tables.py; confirmation period, "
        "both blocks, target 0.95, "
        "seeds 0-4 (mean), primary predictor; D and re-acquisition d in pp; [95% interval, taxi and day cluster "
        "bootstraps, B = 2,000, conservative]; last column: D under label set (iv) (B_aci / B_refit estimates, methods "
        "iv_aci, iv_aci_groups, Bii_refit_a ((iv) refit = (ii) refit by construction), iv_mvp_log, iv_qr_ogd; -- = not run)\n"
        + "\n".join(rows) + "\n")
    # ---- A table, five targets (instruction 10 §2, verdict 10 4-3; supplementary Table S-n): same methods and cells
    rows = ["\\begin{tabular}{@{}llccc@{}}", "\\toprule",
            "Method & Target & $\\bar{D}$ & " + POSTGAP_HEAD + " $d$ & Cost / H2 \\\\", "\\midrule"]
    ms = ["static", "aci_g0005", "mondrian_hour_hop_speed", "A1_mondrian_small", "A2_aci_groups", "A3_qr_groups_inter",
          "qr_groups", "qr_groups_refit", "mvp_log", "qr_ogd"]
    for i, m in enumerate(ms):
        for k, t in enumerate(C.TARGETS):
            cs = [cell(EA, "A", m, e, t=t) for e in ("D", "reacq_d", "cost_ratio_H2")]
            first = f"\\texttt{{{NAME[m]}}}" if k == 0 else ""
            rows.append(f"{first} & {t:.2f} & " + " & ".join(
                tcell(c, e) for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2"))) + " \\\\")
        if i < len(ms) - 1:
            rows.append("\\addlinespace")
    rows += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_review_baselines_targets.tex").write_text(
        "% POST HOC (added during revision (internal review)), generated by posthoc_review_tables.py; confirmation period, "
        "both blocks, targets 0.90-0.98, seeds 0-4 (mean), primary predictor; review/A_estimates.csv label A; "
        "D and re-acquisition d in pp; [95% interval, taxi and day cluster bootstraps, B = 2,000, conservative]\n"
        + "\n".join(rows) + "\n")
    cells = pd.read_csv(C.OUT / "A1_mondrian_cells.csv")
    for b, nm in (("block1", "One"), ("block2", "Two")):
        k = cells[cells.block == b].cell.nunique()
        addm(f"ctwoRevMondrianSmallCellsBlock{nm}", str(k), f"review/A1_mondrian_cells.csv: block {b}, distinct final cells")
    # ---- B table
    rows = ["\\begin{tabular}{@{}llccc@{}}", "\\toprule",
            "Label set & Method & $\\bar{D}$ & " + POSTGAP_HEAD + " $d$ & Cost / H2 \\\\", "\\midrule"]
    for st, ms in SETS.items():
        for k, (disp, m) in enumerate(ms.items()):
            src = (EB if m not in ("qr_groups_refit", "Bi_refit_a", "Bii_refit_a") else ER)
            lab = "B_aci" if src is EB else "B_refit"
            cs = [cell(src, lab, m, e) for e in ("D", "reacq_d", "cost_ratio_H2")]
            note = "$^a$" if (disp == "refit" and st in ("(iii)", "(iv)")) else ""
            rows.append(f"{st if k == 0 else ''} & {disp}{note} & " + " & ".join(
                tcell(c, e) for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2"))) + " \\\\")
            for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2")):
                if c is not None:
                    nd = 2 if e == "cost_ratio_H2" else 3
                    for suf, v in (("", c.point), ("Lo", c.lo), ("Hi", c.hi)):
                        addm(f"ctwoRevFeed{SETMAC[st]}{METMAC[disp]}{EST[e]}{suf}", f3(v, nd),
                             f"review/{lab}_estimates.csv: method {m} (label set {st}), estimand {e}, scope combined, "
                             f"target 0.95, seed mean, 95% conservative | raw {v!r}")
        if st == "(iv)" and len(EV):         # REVIEW_PLAN rev 5 (instruction 19 §3(c)): 7-day refit under (iv), 0.95 and 0.93
            for t in (T, 0.93):
                cs = [cell(EV, "B_v", "Biv_refit7_a", e, t=t) for e in ("D", "reacq_d", "cost_ratio_H2")]
                rows.append(f" & seven-day refit$^c$, target {t:.2f} & " + " & ".join(
                    tcell(c, e) for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2"))) + " \\\\")
        rows.append("\\addlinespace")
    if len(EV):                              # label set (v): audit hops only (REVIEW_PLAN rev 5)
        for k, (disp, m) in enumerate({"group-wise ACI": "v_aci_groups", "mvp\\_log": "v_mvp_log",
                                       "qr\\_ogd": "v_qr_ogd"}.items()):
            cs = [cell(EV, "B_v", m, e) for e in ("D", "reacq_d", "cost_ratio_H2")]
            rows.append(f"{'(v)$^b$' if k == 0 else ''} & {disp} & " + " & ".join(
                tcell(c, e) for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2"))) + " \\\\")
        rows.append("\\addlinespace")
    rows += ["\\bottomrule", "\\end{tabular}", "",
             "\\smallskip\\parbox{\\linewidth}{\\footnotesize $^a$(iii)/(iv) refit = (i)/(ii) refit by construction "
             "(the refit reads only labeled scores)."
             + (" $^b$(v): audit hops only, plan revision 5. $^c$\\texttt{qr\\_groups\\_refit7} under (iv), plan revision 5; "
                "the 0.93 row by the additional-target rule (plan revision 3)." if len(EV) else "") + "}"]
    (TAB / "tab_review_feedback.tex").write_text(
        "% POST HOC (added during revision (internal review)), generated by posthoc_review_tables.py; confirmation period, "
        "both blocks, target 0.95, "
        "seeds 0-4 (mean), primary predictor; D and re-acquisition d in pp; [95% interval, taxi and day cluster "
        "bootstraps, B = 2,000, conservative]"
        + ("; rows (v) and 7-day refit under (iv): review/B_v_estimates.csv (methods v_aci_groups, v_mvp_log, v_qr_ogd, "
           "Biv_refit7_a; the 7-day refit row at target 0.93 is at 0.93)" if len(EV) else "") + "\n"
        + "\n".join(rows) + "\n")
    # ---- C table
    # names as the v6 text (VI predictor sensitivity: "the source site alone, with the exit zone, ...") (instruction 14 §2)
    PRED = {"src": "source site", "src_zone": "+ exit zone", "src_zone_hour": "+ exit zone, time of day",
            "src_zone_speed": "+ exit zone, exit speed", "src_zone_hour_speed": "+ exit zone, time, speed (main)"}
    PM = {"src": "Src", "src_zone": "SrcZone", "src_zone_hour": "SrcZoneHour", "src_zone_speed": "SrcZoneSpeed",
          "src_zone_hour_speed": "Primary"}
    rows = ["\\begin{tabular}{@{}llccc@{}}", "\\toprule",
            "Predictor & Method & $\\bar{D}$ & " + POSTGAP_HEAD + " $d$ & Cost / H2 \\\\", "\\midrule"]
    for p in PRED:
        ms = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "mvp_log", "qr_ogd"] + (["qr_groups_refit"] if p in ("src_zone_speed", "src_zone_hour_speed") else [])
        for k, m in enumerate(ms):
            lab = "C_refit" if (p == "src_zone_speed" and m == "qr_groups_refit") else f"C_{p}"
            cs = [cell(EC, lab, m, e) for e in ("D", "reacq_d", "cost_ratio_H2")]
            rows.append(f"{PRED[p] if k == 0 else ''} & \\texttt{{{NAME[m]}}} & " + " & ".join(
                tcell(c, e) for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2"))) + " \\\\")
            for c, e in zip(cs, ("D", "reacq_d", "cost_ratio_H2")):
                if c is not None:
                    nd = 2 if e == "cost_ratio_H2" else 3
                    for suf, v in (("", c.point), ("Lo", c.lo), ("Hi", c.hi)):
                        addm(f"ctwoRevPred{PM[p]}{MAC[m]}{EST[e]}{suf}", f3(v, nd),
                             f"review/C_estimates.csv: label {lab}, predictor {p}, method {m}, estimand {e}, scope combined, "
                             f"target 0.95, seed mean, 95% conservative | raw {v!r}")
        rows.append("\\addlinespace")
    rows += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_review_predictors.tex").write_text(
        "% POST HOC (added during revision (internal review)), generated by posthoc_review_tables.py; confirmation period, "
        "both blocks, target 0.95, "
        "seeds 0-4 (mean); D and re-acquisition d in pp; [95% interval, taxi and day cluster bootstraps, B = 2,000, "
        "conservative]\n" + "\n".join(rows) + "\n")

    # ---- consequence check (appendix R, mechanical)
    cc = []

    def rec(rule, cond, where, value, sat):
        cc.append({"rule": rule, "condition": cond, "where": where, "value": value, "satisfied": sat})
    for t in C.TARGETS:
        for b in ("A1_mondrian_small", "A2_aci_groups"):
            for q in ("qr_groups", "qr_groups_refit"):
                dd, dc = diff(DA, "A", b, q, "D", t=t), diff(DA, "A", b, q, "cost_ratio_H2", t=t)
                if dd is None or dc is None:
                    continue
                v = f"D diff {dd.point:.4f} [{dd.lo:.4f}, {dd.hi:.4f}]; cost/H2 diff {dc.point:.4f} [{dc.lo:.4f}, {dc.hi:.4f}]"
                w = f"combined, t={t}, {b} - {q}"
                rec("A1", "D diff interval contains 0 and cost/H2 diff interval contains 0", w, v,
                    bool(dd.lo <= 0 <= dd.hi and dc.lo <= 0 <= dc.hi))
                rec("A2", "D diff interval excludes 0 with the QR method smaller (lo > 0)", w, v, bool(dd.lo > 0))
                rec("A2-cost", "and baseline cheaper (cost/H2 diff hi < 0)", w, v, bool(dd.lo > 0 and dc.hi < 0))
                rec("A3", "D diff interval excludes 0 with the baseline smaller (hi < 0)", w, v, bool(dd.hi < 0))
        I = IA[(IA.label == "A") & (IA.method == "A3_qr_groups_inter") & (IA.scope == "combined") & np.isclose(IA.target, t)]
        for _, r in I.iterrows():
            rec("A4", "intersection deficit upper bound <= 0.01 (self-evaluation: the intersections are groups of A3)",
                f"combined, t={t}, A3_qr_groups_inter, {r.cell}", f"{r.deficit:.4f} [{r.lo:.4f}, {r.hi:.4f}]", bool(r.hi <= 0.01))
    rec("B0", "(i): mvp_log and qr_ogd equal full feedback", "all runs", "stored values reused (miss indicator only)", True)
    for st, on, rf in (("(i)", ("mvp_log", "qr_ogd"), "Bi_refit_a"), ("(ii)", ("Bii_mvp_log", "Bii_qr_ogd"), "Bii_refit_a"),
                       ("(iii)", ("iii_mvp_log", "iii_qr_ogd"), "Bi_refit_a"), ("(iv)", ("iv_mvp_log", "iv_qr_ogd"), "Bii_refit_a")):
        for t, o, e in ((t, o, e) for t in (0.95, 0.93) for o in on for e in ("reacq_d", "D")):   # 0.93: conditional refit
                d = diff(DR, "B_refit", o, rf, e, t=t)
                if d is None:
                    continue
                v = f"{e} diff ({o} - {rf}) {d.point:.4f} [{d.lo:.4f}, {d.hi:.4f}]"
                rec("B1", f"order as confirm2 (online not smaller with interval excluding 0), {e}", f"combined, t={t}, {st}", v, bool(not d.hi < 0))
                rec("B2", f"online smaller with interval excluding 0 (hi < 0), {e}", f"combined, t={t}, {st}", v, bool(d.hi < 0))
                if t == 0.95 and e == "reacq_d" and o.endswith("mvp_log") and st in ("(i)", "(ii)"):
                    rec("6.3-0.93", "run refit at 0.93 for this label set (mvp_log reacq d smaller, interval excludes 0)",
                        f"combined, t=0.95, {st}", v, bool(d.hi < 0))
    for m, full, src, Dd, lab in (("Bi_refit_a", "qr_groups_refit", "refit", DR, "B_refit"), ("Bi_aci", "aci_g0005", "ACI", DB, "B_aci")):
        d = diff(Dd, lab, m, full, "D")
        if d is not None:
            rec("B3", "(i): D increase vs full feedback >= 0.02 for every group method (mvp_log, qr_ogd: 0 by construction); "
                "note: only the refit row is evaluated (the consequence text names every group method)",
                f"combined, t=0.95, {m} - {full}", f"{d.point:.4f} [{d.lo:.4f}, {d.hi:.4f}]", bool(d.point >= 0.02))
    rec("B4", "left-censored QR trial reported in the supplement only", "block1, t=0.95, seed 0", "no condition", None)
    for t in C.TARGETS:
        for o in ("iii_mvp_log", "iii_qr_ogd"):
            r = cell(EB, "B_aci", o, "D", t=t)
            if r is not None:
                rec("B5", "(iii): worst-group recall below target by >= 0.05 at the upper bound (D lo >= 0.05)",
                    f"combined, t={t}, {o}", f"D {r.point:.4f} [{r.lo:.4f}, {r.hi:.4f}]", bool(r.lo >= 0.05))
        for o, full in (("iv_mvp_log", "mvp_log"), ("iv_qr_ogd", "qr_ogd")):
            d = diff(DB, "B_aci", o, full, "D", t=t)
            if d is not None:
                rec("B6", "(iv): D within 0.02 of full feedback including the interval (-0.02 <= lo, hi <= 0.02)",
                    f"combined, t={t}, {o} - {full}", f"{d.point:.4f} [{d.lo:.4f}, {d.hi:.4f}]", bool(d.lo >= -0.02 and d.hi <= 0.02))
    for p in ("src", "src_zone", "src_zone_hour", "src_zone_speed", "src_zone_hour_speed"):
        for t in C.TARGETS:
            sat_all = True; vals = []
            for g in ("qr_groups", "mvp_log", "qr_ogd"):
                for mg in ("static", "aci_g0005"):
                    d = diff(DC, f"C_{p}", mg, g, "D", t=t)
                    if d is None:
                        sat_all = None; continue
                    vals.append(f"{mg}-{g} {d.point:.4f} [{d.lo:.4f}, {d.hi:.4f}]")
                    if sat_all is not None:
                        sat_all = sat_all and bool(d.lo > 0)
            rec("C1", "group methods' D smaller than static and ACI, every pair interval excludes 0 (lo > 0)",
                f"combined, t={t}, predictor {p}", "; ".join(vals), sat_all)
            rec("C2", "complement of C1 (direction changes or not distinguished in some pair)",
                f"combined, t={t}, predictor {p}", "see C1", None if sat_all is None else not sat_all)
    rec("C3", "refit with one alternative predictor not used in the S2 sentence", "src_zone_speed, t=0.95", "no condition", None)
    CC = pd.DataFrame(cc)
    with open(AGG / "consequence_check.csv", "w") as f:
        f.write(head + IVHEAD); CC.to_csv(f, index=False)
    # ---- derived macros (instruction 04 §2, A-22): pp (D x 100, one decimal), ranges, text lists from consequence_check
    def pp(E, lab, m, name, what):
        r = cell(E, lab, m, "D")
        addm(name, f3(100 * r.point, 1), f"review/{lab}_estimates.csv: method {m} ({what}), estimand D, scope combined, "
             f"target 0.95, seed mean, x 100 (pp) | raw {r.point!r}")
    for m, nm in (("mondrian_hour_hop_speed", "Mondrian"), ("A1_mondrian_small", "MondrianSmall"), ("A2_aci_groups", "AciGroups")):
        pp(EA, "A", m, f"ctwoRevBase{nm}DbarPp", "label A")
    # instruction 07 §1 F2: small Mondrian re-acquisition d in pp with its conservative bounds
    r = cell(EA, "A", "A1_mondrian_small", "reacq_d")
    for suf, v in (("", r.point), ("Lo", r.lo), ("Hi", r.hi)):      # names as David's v4-9 placeholder (ReacqHiPp)
        addm(f"ctwoRevBaseMondrianSmallReacq{suf}Pp", f3(100 * v, 1),
             f"review/A_estimates.csv: label A, method A1_mondrian_small, estimand reacq_d, scope combined, target 0.95, "
             f"seed mean, 95% conservative, x 100 (pp) | raw {v!r}")
    # instruction 07 §1 F3: group that sets D of the small Mondrian per target (argmax of the judged g25 deficits; the
    # deficit equals D in A_estimates), and whether it is one of the attributes that define the 12 original cells
    # (track state, branching Q4, isolation Q4; REVIEW_PLAN A(1)). Group names as paper scripts/ch6lib.py LEVEL_NAME.
    GA = load("A", "groups")
    rows_w = []
    for t in C.TARGETS:
        g = GA[(GA.label == "A") & (GA.method == "A1_mondrian_small") & (GA.scope == "combined") & np.isclose(GA.target, t)
               & GA.judged]
        w = g.loc[g.deficit.idxmax()]
        dim, lev = w.cell.split("=")
        rows_w.append({"target": t, "worst_group": w.cell, "name": LEVEL[dim][int(lev)], "n": int(w.n), "deficit": w.deficit,
                       "lo": w.lo, "hi": w.hi, "D_estimates": cell(EA, "A", "A1_mondrian_small", "D", t=t).point,
                       "partition_attribute": dim == "grp_all" or dim == "hopkind" or (dim in ("entropy_bin", "nn_bin")
                                                                                        and int(lev) == 3)})
    W = pd.DataFrame(rows_w)
    assert (W.deficit == W.D_estimates).all()
    with open(AGG / "A1_worst_group.csv", "w") as f:
        f.write("# POST HOC (instruction 07 §1 F3): small Mondrian (A1_mondrian_small), label A, scope combined, seed mean; "
                "worst_group = judged g25 group with the largest deficit (= D of A_estimates); partition_attribute = the "
                "group is all hops, a track state, branching Q4 or isolation Q4 (attributes of the 12 original cells)\n")
        W.to_csv(f, index=False)
    w = W[np.isclose(W.target, T)].iloc[0]
    # v11 (verdict 35 A6, instruction 28 §1): lower-case attribute word as in the running text ("branching Q3")
    addm("ctwoRevBaseMondrianSmallWorstGroup", w["name"][0].lower() + w["name"][1:],
         f"review/A_groups.csv: label A, method A1_mondrian_small, scope combined, target 0.95, judged g25 groups, seed "
         f"mean; group with the largest deficit ({w.worst_group}, deficit {w.deficit!r} = D); name as ch6lib LEVEL_NAME, "
         f"first letter lower case")
    # instruction 07 §1 F4: cost / H2 difference small Mondrian - QR methods, conservative upper bound < 0 at every target
    rows_c = []
    for q in ("qr_groups", "qr_groups_refit"):
        for t in C.TARGETS:
            d = diff(DA, "A", "A1_mondrian_small", q, "cost_ratio_H2", t=t)
            rows_c.append({"comparator": "A1_mondrian_small", "reference": q, "target": t, "point": d.point, "lo": d.lo,
                           "hi": d.hi, "hi_lt_0": bool(d.hi < 0)})
    with open(AGG / "A1_cost_vs_qr.csv", "w") as f:
        f.write("# POST HOC (instruction 07 §1 F4): A_differences.csv rows cost_ratio_H2_diff, label A, scope combined; "
                "Delta = comparator - reference; hi = conservative 95% upper bound\n")
        pd.DataFrame(rows_c).to_csv(f, index=False)
    print(W.to_string(index=False)); print(pd.DataFrame(rows_c).to_string(index=False))
    for m, nm, what in (("qr_groups_refit", "Full", "full feedback"), ("Bi_refit_a", "One", "label set (i)"),
                        ("Bii_refit_a", "Two", "label set (ii)"),
                        ("Bii_refit_a", "Four", "label set (iv) = (ii) refit by construction")):
        pp(ER, "B_refit", m, f"ctwoRevFeed{nm}RefitDbarPp", what)
    for m, nm in (("iv_mvp_log", "MvpLog"), ("iv_qr_ogd", "QrOgd"), ("iv_aci_groups", "AciGroups")):
        pp(EB, "B_aci", m, f"ctwoRevFeedFour{nm}DbarPp", "label set (iv)")

    def rng(E, lab, ms, est, name, nd, k, what, ts=(T,)):
        rs = [(m, t, cell(E, lab, m, est, t=t)) for m in ms for t in ts]
        lo, hi = min(rs, key=lambda x: x[2].point), max(rs, key=lambda x: x[2].point)
        for suf, (m, t, r) in (("Min", lo), ("Max", hi)):
            addm(f"{name}{suf}", f3(k * r.point, nd), f"review/{lab}_estimates.csv: {suf.lower()} over methods "
                 f"{', '.join(ms)} and targets {', '.join(map(str, ts))} ({what}), estimand {est}, scope combined, seed mean"
                 f"{', x 100 (pp)' if k != 1 else ''}; attained by {m} at target {t} | raw {r.point!r}")
    rng(EB, "B_aci", ("iv_mvp_log", "iv_qr_ogd"), "D", "ctwoRevFeedFourOnlineDbarPp", 1, 100, "label set (iv)")
    rng(EB, "B_aci", ("iii_mvp_log", "iii_qr_ogd"), "D", "ctwoRevFeedThreeOnlineDbarPp", 1, 100, "label set (iii)")
    rng(EB, "B_aci", ("iii_mvp_log", "iii_qr_ogd"), "cost_ratio_H2", "ctwoRevFeedThreeOnlineCostHtwo", 1, 1,
        "label set (iii), after the R3 fix c7de4f7")
    rng(EA, "A", ("A2_aci_groups",), "cost_ratio_H2", "ctwoRevAciGroupsCostHtwo", 2, 1, "label A", ts=tuple(C.TARGETS))
    # instruction 20 §1 (verdict 23 B, David 20 abstract): Dbar of group-wise ACI over the five targets
    rng(EA, "A", ("A2_aci_groups",), "D", "ctwoRevAciGroupsDbarPp", 1, 100, "label A", ts=tuple(C.TARGETS))
    w = lambda t: f"combined, t={t}, A2_aci_groups - qr_groups_refit"            # noqa: E731
    sat = lambda rule, t: bool(CC[(CC.rule == rule) & (CC["where"] == w(t))].satisfied.iloc[0])   # noqa: E731
    small = [t for t in C.TARGETS if sat("A3", t)]
    equal = [t for t in C.TARGETS if not sat("A3", t) and not sat("A2", t)]
    for name, ts_, how in (("ctwoRevAciGroupsRefitSmallerTargets", small, "A3 satisfied (D diff hi < 0)"),
                           ("ctwoRevAciGroupsRefitEqualTargets", equal, "A2 and A3 not satisfied (D diff interval contains 0)")):
        addm(name, tlist(f"{t:.2f}" for t in ts_), f"review/aggregate/consequence_check.csv: rows A2, A3, where "
             f"'combined, t=<target>, A2_aci_groups - qr_groups_refit'; targets with {how}")
    I4 = CC[(CC.rule == "A4") & CC["where"].str.startswith(f"combined, t={T}, ")]
    cl = I4["where"].str.split(", ").str[-1]
    for name, sel, how in (("ctwoRevInterClosed", I4.satisfied == True, "satisfied"),            # noqa: E712
                           ("ctwoRevInterOpen", I4.satisfied != True, "not satisfied")):        # noqa: E712
        addm(name, tlist(cl[sel]), f"review/aggregate/consequence_check.csv: rows A4, combined, t={T}, A3_qr_groups_inter; "
             f"intersections with A4 {how} (deficit upper bound <= 0.01)")

    # ---- REVIEW_PLAN rev 5 (instruction 18 §4): label set (v) and refit7 under (iv), target 0.95, combined; written only
    # when the B_v aggregate exists, so the macros above are unchanged without it
    if len(EV):
        VM = {"v_mvp_log": ("MvpLog", "mvp_log", "iv_mvp_log"), "v_qr_ogd": ("QrOgd", "qr_ogd", "iv_qr_ogd"),
              "v_aci_groups": ("AciGroups", "A2_aci_groups", "iv_aci_groups")}
        for m, (mm, full, iv) in VM.items():
            for est, en, k, nd in (("D", "DbarPp", 100, 1), ("reacq_d", "PostgapPp", 100, 1),
                                   ("cost_mean", "CostAbs", 1, 0), ("cost_ratio_H2", "CostHtwo", 1, 2)):
                r = cell(EV, "B_v", m, est)
                for suf, v in (("", r.point), ("Lo", r.lo), ("Hi", r.hi)):
                    addm(f"ctwoRevV{mm}{en}{suf}", f3(k * v, nd), f"review/B_v_estimates.csv: method {m} (label set (v)), "
                         f"estimand {est}, scope combined, target 0.95, seed mean, 95% conservative | raw {v!r}")
            for ref, rn in ((full, "Full"), (iv, "Four")):
                r = diff(DV, "B_v", m, ref, "D")
                for suf, v in (("", r.point), ("Lo", r.lo), ("Hi", r.hi)):
                    addm(f"ctwoRevV{mm}DiffDbar{rn}Pp{suf}", f3(100 * v, 2), f"review/B_v_differences.csv: D({m}) - "
                         f"D({ref}), scope combined, target 0.95, paired, seed mean, 95% conservative, x 100 (pp) | raw {v!r}")
                if rn == "Full" and mm == "MvpLog":   # one decimal of the upper bound, abstract (verdict 23 B (a), instruction 20 §1)
                    addm(f"ctwoRevV{mm}DiffDbar{rn}PpHiOne", f3(100 * r.hi, 1), f"review/B_v_differences.csv: D({m}) - "
                         f"D({ref}), scope combined, target 0.95, paired, seed mean, 95% conservative upper bound, x 100 "
                         f"(pp), one decimal | raw {r.hi!r}")
        for est, en, k, nd in (("D", "DbarPp", 100, 1), ("reacq_d", "PostgapPp", 100, 1), ("cost_mean", "CostAbs", 1, 0),
                               ("cost_ratio_H2", "CostHtwo", 1, 2)):
            r = cell(EV, "B_v", "Biv_refit7_a", est)
            for suf, v in (("", r.point), ("Lo", r.lo), ("Hi", r.hi)):
                addm(f"ctwoRevRefitSevenFour{en}{suf}", f3(k * v, nd), f"review/B_v_estimates.csv: method Biv_refit7_a "
                     f"(qr_groups_refit7 under label set (iv)), estimand {est}, scope combined, target 0.95, seed mean, "
                     f"95% conservative | raw {v!r}")
        for est, en, k, nd in (("D", "DbarPp", 100, 1), ("reacq_d", "PostgapPp", 100, 1), ("cost_mean", "CostAbs", 1, 0),
                               ("cost_ratio_H2", "CostHtwo", 1, 2)):      # instruction 19 §2: the 0.93 runs (rev 3 rule)
            r = cell(EV, "B_v", "Biv_refit7_a", est, t=0.93)
            for suf, v in (("", r.point), ("Lo", r.lo), ("Hi", r.hi)):
                addm(f"ctwoRevRefitSevenFourNinetyThree{en}{suf}", f3(k * v, nd), f"review/B_v_estimates.csv: method "
                     f"Biv_refit7_a (qr_groups_refit7 under label set (iv)), estimand {est}, scope combined, target 0.93, "
                     f"seed mean, 95% conservative | raw {v!r}")
        UP = pd.read_csv(C.OUT / "B_v_updates_postgap.csv").query("target == 0.95")
        for nm, v in (("Median", np.median(UP.mvp_log)), ("Min", UP.mvp_log.min()), ("Max", UP.mvp_log.max())):
            addm(f"ctwoRevVPostgapUpdates{nm}", f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}", f"review/B_v_updates_postgap.csv: label updates "
                 f"applied to the post-gap group (hopkind=2) per run under (v), target 0.95, 10 runs (2 blocks x 5 seeds); "
                 f"{nm.lower()} (the same counts for the three methods) | raw {v!r}")

    old = (C.OUT / "review_numbers.tex").read_text()
    old = old.split("% ---- REVIEW aggregate macros")[0].rstrip("\n")
    # wording of the look-up block header (instruction 04 §2, A-26); posthoc_review_lookups.py writes the same wording now
    old = old.replace("(POST HOC, external review;", "(POST HOC, added during revision (internal review);", 1)
    (C.OUT / "review_numbers.tex").write_text(old + "\n% ---- REVIEW aggregate macros (posthoc_review_tables.py, POST HOC)\n"
                                              + "\n".join(mac) + "\n")
    print(CC.groupby(["rule", "satisfied"], dropna=False).size().to_string())
    print(len(mac) // 2, "aggregate macros")


if __name__ == "__main__":
    main()
