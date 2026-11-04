"""results/porto_cctv_confirm2/REPORT.md: numbers and judgements only (no interpretation), from the result files.

    python confirm2_report.py

Sources: results/porto_cctv_confirm2/run_log.txt, analysis/*.csv, h3_sensitivity/h3_sensitivity.csv. Every table names
its file; values are copied with fixed rounding (4 decimals for recalls / deficits / differences, 3 for ratios,
1 for costs).
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
R = ROOT / "results/porto_cctv_confirm2"
AN = R / "analysis"
MN = {"mvp_log": "mvp_log", "qr_ogd": "qr_ogd", "static": "static", "aci_g0005": "ACI", "mondrian_hour_hop_speed": "Mondrian",
      "qr_groups": "qr_groups", "qr_groups_refit": "qr_groups_refit", "qr_groups_refit7": "qr_groups_refit7",
      "citytrac_nominal": "CityTrac-style", "spatula_rule|fixed": "Spatula-style", "H1": "H1", "H3": "H3", "H4": "H4"}
EST = {"reacq_deficit_diff": "(a) re-acquired", "isoq4_deficit_diff": "(b) isolation Q4", "worst_deficit_diff": "(c) ΔD"}


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(out)


def ci(p, lo, hi, d=4):
    return f"{p:.{d}f} [{lo:.{d}f}, {hi:.{d}f}]"


def runlog():
    txt = (R / "run_log.txt").read_text().splitlines()
    i = max(k for k, l in enumerate(txt) if l.startswith("# confirm2-exec"))
    part = txt[i:]
    st = {m.group(2): m.group(1) for l in part if (m := re.match(r"START (\S+) (block\d_t\d+_s\d)", l))}
    en = {m.group(2): (m.group(1), m.group(3)) for l in part if (m := re.match(r"END +(\S+) (block\d_t\d+_s\d) \| exit (\d+)", l))}
    rows = []
    for k in sorted(st):
        t0 = pd.Timestamp(st[k]); t1 = pd.Timestamp(en[k][0]) if k in en else None
        rows.append({"run": k, "start": st[k], "end": en[k][0] if k in en else "", "exit": en[k][1] if k in en else "",
                     "hours": round((t1 - t0).total_seconds() / 3600, 2) if t1 is not None else None})
    return pd.DataFrame(rows), txt


def main():
    L = ["# Confirmation experiment 2: summary of results (results/porto_cctv_confirm2)", "",
         "Numbers and verdicts only (no interpretation). Plan: `notes/instructions/PLAN_confirm2.md` (rev 72, tag `confirm2-plan`, commit 6758bce). "
         "Start of execution: tag `confirm2-exec` (commit ca586a6). Deviations: `DEVIATIONS.md` D4, D5.", ""]
    RL, txt = runlog()
    L += ["## 1. Runs", "",
          f"- Runs: {len(RL)} (5 targets × 2 blocks × evaluation seeds 0–4), normal exit (exit 0): {(RL.exit == '0').sum()}",
          f"- First start: {RL.start.min()}, last end: {RL.end.max()}",
          f"- Duration per run (hours, at most 6 at a time): min {RL.hours.min()}, median {RL.hours.median()}, max {RL.hours.max()}",
          "- Data check before the runs (run_log.txt CHECK lines): trip table and transition hashes = lock; cameras = file bytes, column values and addendum hash agree",
          "- Stops and restarts: stopped at the pre-run check on 2026-10-15 17:48:29 (camera hash, D4; before the 50 runs started). Restarted with the same command at 17:55:36. "
          "No stop or restart during the 50 runs."]
    import json
    al = json.load(open(AN / "analysis_log.json")); hl = json.load(open(R / "h3_sensitivity/h3_sensitivity_log.json"))
    L += [f"- Main analysis (`confirm2_analysis.py`, two blocks + combined, B = {al['B_main']:,} / {al['B_other']:,}, threads {al.get('threads')}): "
          f"total {al['timing']['total_s']:.0f} s (hindsight-reference step {al['timing']['hindsight_s']:.0f} s); clusters: taxi {al['clusters']['taxi']}, day {al['clusters']['day']}",
          f"- H3 sensitivity analysis (target {hl['target']}, combined {hl['hops']:,} hops, taxi {hl['taxi_clusters']}, B = {hl['B']}, workers {hl['workers']}): "
          f"full-sample fit {hl['full_fit_seconds']:.0f} s, refits in the replicates {hl['bootstrap_seconds']:.0f} s (run alongside the main analysis)", ""]
    L += [md(RL.rename(columns={"run": "Run", "start": "Start", "end": "End", "exit": "Exit code", "hours": "Hours"})), ""]
    # 10.8
    C = pd.read_csv(AN / "claims_10_8.csv")
    L += ["## 2. §10.8 verdict table (combined 56 days, verdict estimand (a), 99% simultaneous intervals, conservative at each bound, majority = at least 3 of the 5 targets)", "",
          "Source: `analysis/claims_10_8.csv`", "", md(C.rename(columns={"method": "Method", "statement": "Statement", "status": "Verdict", "detail": "Basis"})), "",
          "- Note: the H3 intervals in the basis column of S3 are the fixed-threshold intervals printed by the locked verdict code (`confirm2_analysis.judge`). Under plan rev 72 (§10.5), "
          "the H3 intervals for the paper are the sensitivity intervals at target 0.95, in the cost table of section 5. S3 has no verdict condition.", ""]
    # main comparisons
    E = pd.read_csv(AN / "main_estimands.csv")
    L += ["## 3. Main comparison table (sign: Δ = D_comparator − D_method, positive = improvement; 99% intervals, conservative over taxi and day clusters at each bound, B = 10,000)", "",
          "Source: `analysis/main_estimands.csv`. Cell: point estimate [lower, upper] class (seed sign agreement)", ""]
    for sc in ["combined", "block1", "block2"]:
        L += [f"### {sc}", ""]
        for pm in ["mvp_log", "qr_ogd"]:
            rows = []
            for cm in ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit", "qr_groups_refit7"]:
                for est in EST:
                    g = E[(E.scope == sc) & (E.proposed == pm) & (E.comparator == cm) & (E.estimand == est)].set_index("target")
                    r = {"Comparator": MN[cm], "Estimand": EST[est]}
                    for t, x in g.iterrows():
                        agree = f" ({x.seed_agreement})" if isinstance(x.seed_agreement, str) and x.seed_agreement else ""
                        r[f"t={t:g}"] = f"{ci(x.point, x.lo, x.hi)} {x['class']}{agree}"
                    rows.append(r)
            L += [f"**{pm}**", "", md(pd.DataFrame(rows)), ""]
    # deficits
    D = pd.read_csv(AN / "deficits.csv")
    L += ["## 4. Shortfalls (d = t − R, 95% intervals, conservative; combined)", "", "Source: `analysis/deficits.csv`", ""]
    for cell, nm in [("WORST", "Worst-group shortfall D̄"), ("hopkind=2", "Re-acquisition d̄"), ("nn_bin=3", "Isolation Q4 d̄"), ("grp_all=0", "All hops d̄")]:
        g = D[(D.scope == "combined") & (D.cell == cell)]
        T = g.pivot_table(index="method", columns="target", values="deficit", aggfunc="first")
        rows = []
        for m in T.index:
            r = {"Method": MN.get(m, m)}
            for t in T.columns:
                x = g[(g.method == m) & (g.target == t)].iloc[0]
                r[f"t={t:g}"] = ci(x.deficit, x.lo, x.hi)
            rows.append(r)
        L += [f"**{nm}**", "", md(pd.DataFrame(rows)), ""]
    # costs
    CO = pd.read_csv(AN / "costs.csv"); RA = pd.read_csv(AN / "cost_ratios.csv"); HS = pd.read_csv(R / "h3_sensitivity/h3_sensitivity.csv")
    HI = pd.read_csv(AN / "hindsight.csv")
    L += ["## 5. Cost table (combined; camera·s/hop, an upper bound on the operational cost; 95% intervals, conservative)", "",
          "Sources: `analysis/costs.csv`, `analysis/cost_ratios.csv`, `analysis/hindsight.csv`, `h3_sensitivity/h3_sensitivity.csv`. "
          "H3 ratio: point estimate and the sensitivity interval at target 0.95 (combined, taxi clusters, B = 100, refitted in every replicate). H3 fixed-threshold intervals only in the appendix tables (section 6).", ""]
    rows = []
    for t in sorted(CO.target.unique()):
        for m in ["mvp_log", "qr_ogd", "static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit",
                  "qr_groups_refit7", "citytrac_nominal", "spatula_rule|fixed"]:
            c = CO[(CO.scope == "combined") & (CO.target == t) & (CO.method == m)].iloc[0]
            r = {"t": f"{t:g}", "Method": MN[m], "Mean cost": ci(c.cost_mean, c.cost_lo, c.cost_hi, 1), "Overall recall": f"{c.recall_all:.4f}",
                 "D̄": f"{c.D:.4f}"}
            for ref in ["H1", "H2", "H3", "H4"]:
                x = RA[(RA.scope == "combined") & (RA.target == t) & (RA.method == m) & (RA.reference == ref)].iloc[0]
                if ref == "H3":
                    s = HS[(HS.method == m) & (abs(HS.target - t) < 1e-9)]
                    r["÷H3"] = f"{x.ratio:.3f}" + (f" [{s.iloc[0].lo_refit:.3f}, {s.iloc[0].hi_refit:.3f}]" if len(s) else "")
                else:
                    r[f"÷{ref}"] = ci(x.ratio, x.lo, x.hi, 3)
            rows.append(r)
    L += [md(pd.DataFrame(rows)), ""]
    hr = HI[(HI.scope == "combined") & (HI.reference != "H2")][["target", "reference", "recall_all", "worst_deficit", "worst_group", "cost_mean"]]
    hr = hr.assign(recall_all=hr.recall_all.round(4), worst_deficit=hr.worst_deficit.round(4), cost_mean=hr.cost_mean.round(1))
    L += ["**Realized overall recall and worst-group shortfall of the hindsight references (combined)**", "", md(hr), ""]
    h2 = HI[(HI.scope == "combined") & (HI.reference == "H2")].groupby(["target", "method"], as_index=False)[["recall_all", "worst_deficit", "cost_mean"]].mean().round(4)
    L += ["**H2 (per method and seed; seed mean)**", "", md(h2), ""]
    # appendix
    fx = RA[(RA.scope == "combined") & (RA.reference == "H3")][["target", "method", "ratio", "lo", "hi", "note"]].round(4)
    L += ["## 6. Appendix tables", "", "**Ratio to H3, fixed-threshold intervals (not used in the paper)**", "", md(fx), ""]
    DO = pd.read_csv(AN / "dominance.csv")
    L += ["**Two-way dominance table (§10.5, combined)** Source: `analysis/dominance.csv`, pair list `analysis/dominance_pairs.csv`", "", md(DO), ""]
    BC = pd.read_csv(AN / "block_comparison.csv")
    BC = BC[["target", "method", "D_block1", "D_block2", "diff", "lo", "hi", "reading"]].round(4)
    L += ["**Comparison between blocks (§10.4, D̄ block 1 − block 2, 95%)** Source: `analysis/block_comparison.csv`", "", md(BC), ""]
    SR = pd.read_csv(AN / "seed_range.csv")
    SR = SR[SR.scope == "combined"][["target", "method", "D_seed_min", "D_seed_max", "cost_seed_min", "cost_seed_max", "seed_range_over_ci_width"]].round(4)
    L += ["**Seed range (§9.3, combined)** Source: `analysis/seed_range.csv`", "", md(SR), ""]
    AP = pd.read_csv(AN / "alt_partitions.csv")
    AP = AP[(AP.scope == "combined") & (AP.cell == "SUMMARY") & AP.method.isin(["mvp_log", "qr_ogd"])][
        ["target", "method", "family", "deficit", "diff_vs_D", "diff_lo", "diff_hi", "reading", "smallest_cell_n"]].round(4)
    L += ["**Alternative partitions, summary (§8, §10.7, combined, 95%)** Source: `analysis/alt_partitions.csv`", "", md(AP), ""]
    IN = pd.read_csv(AN / "intersections.csv")
    IN = IN[(IN.scope == "combined") & IN.method.isin(["mvp_log", "qr_ogd"])][["target", "method", "cell", "n", "deficit", "lo", "hi"]].round(4)
    L += ["**Intersections I1–I6 (combined, 95%)** Source: `analysis/intersections.csv`", "", md(IN), ""]
    if (AN / "reachable_bound.csv").exists():
        RB = pd.read_csv(AN / "reachable_bound.csv")
        RB = RB[RB.group.isin(["hopkind=2", "nn_bin=3", "grp_all=0"])].round(5)
        L += ["**Reachable upper bound U_G (§5.4)** Source: `analysis/reachable_bound.csv`", "", md(RB), ""]
        AM = pd.read_csv(AN / "a_min_reach.csv").groupby("target", as_index=False).mvp_log_hops_at_a_min_share.agg(["min", "max"]).round(6)
        L += ["**Share reaching a_min (§4, mvp_log, seed min–max, approximate)** Source: `analysis/a_min_reach.csv`", "", md(AM.reset_index() if "target" not in AM.columns else AM), ""]
    (R / "REPORT.md").write_text("\n".join(L) + "\n")
    print(f"-> {R / 'REPORT.md'} ({len(L)} lines)")


if __name__ == "__main__":
    main()
