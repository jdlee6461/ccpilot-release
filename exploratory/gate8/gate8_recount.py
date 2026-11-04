"""EXPLORATORY, POST HOC (instruction 17 §1-3; verdict 20, Gate 8): fact checks and recounts from stored outputs.
No calibration method, bootstrap or fit is run; inputs are read only.

    python exploratory/gate8/gate8_recount.py

Items (instruction 17):
  (b) cal_score_floor.csv     calibration-week scores of the primary predictor at 0 and below the QR log floor 1e-8
  (a) dbar_definition.csv     D-bar as mean over seeds of max over groups (plan §5.1) against max over groups of the
                              seed-mean shortfall, from group_recall.csv (judged groups, per seed), checked against the
                              WORST row of deficits.csv
  (c) custody_pairs.csv       stored paired 5-hop custody differences (custody_diffs.csv) of every method against static
  (g) exit_by_group.csv       exit share per group of the 25 (exit hops have no threshold or cost in the result files);
                              group columns rebuilt with ccpilot.evaluate._add_strata/_add_spatial on the block's run
                              configuration and checked against hits.parquet for the non-exit evaluation hops
  (h) seed_range.csv          per-seed D^s and cost ranges (seed_range.csv), sign_agreement.csv (main_estimands.csv)
  (i) abs_cost_feedback.csv   absolute cost per hop (camera-s) under label sets (iii) and (iv) and full feedback
  (j) tab_c2_inter_groups.tex qr_groups and qr_groups + I1-I6 on I1-I6, five targets (exploratory/intersections_q)
  (k) qr_inter_design.csv     rank and correlations of the qr_groups + I1-I6 design on the calibration week, and the
                              number of I-hops in the 80,000-row subsample per seed (the fitted coefficients are not
                              stored, so the calibration-week miss rate is not computed here)
  (l) postgap_theta.csv       realised |theta_G| / (gamma T_G) for the post-gap group of qr_ogd (exploratory/qrogd_clip)
  (m) predictor_targets.csv   targets available per predictor and method in the review part C estimates
  (n) custody_rounding.csv    raw values behind ctwoCustodyReacqFive{Min,Max,DiffMax}
  (o) audit_counts.csv        label set (iv): audit hops and post-gap audit hops per block and evaluation seed
Output: exploratory/gate8/*.csv, tab_c2_inter_groups.tex, manifest.csv (file, sha256, script commit).
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask  # noqa: E402
from ccpilot.multigroup import _design  # noqa: E402
from confirm2_analysis import INTER  # noqa: E402

OUT = ROOT / "exploratory/gate8"
A = ROOT / "results/porto_cctv_confirm2/analysis"
RV = ROOT / "results/porto_cctv_confirm2_posthoc/review"
RUNS = ROOT / "results/porto_cctv_confirm2/runs"
WORK = ROOT / "work/porto_cctv_confirm2"
CACHE = ROOT / "work/review_cache"
HEADER = "# Post hoc analysis (after the confirm2 results were seen; exploratory, reads stored results only; instruction 17)\n"
DIMS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
BLOCKS = ["block1", "block2"]
SEEDS = [0, 1, 2, 3, 4]
WRITTEN = []


def write(df, name, **kw):
    with open(OUT / name, "w") as f:
        f.write(HEADER); df.to_csv(f, index=False, **kw)
    WRITTEN.append(name)


def item_a():
    G = pd.read_csv(A / "group_recall.csv").query("judged")
    W = pd.read_csv(A / "deficits.csv").query("cell == 'WORST'").set_index(["scope", "target", "method"]).deficit
    rows = []
    for (sc, t, m), g in G.groupby(["scope", "target", "method"]):
        per_seed = g.groupby("seed").deficit.max()
        mean_max = per_seed.mean()
        max_mean = g.groupby("group").deficit.mean().max()
        rows.append({"scope": sc, "target": t, "method": m, "n_seeds": len(per_seed), "D_mean_of_max": mean_max,
                     "D_max_of_mean": max_mean, "difference": mean_max - max_mean, "deficits_WORST": W[(sc, t, m)],
                     "WORST_equals_mean_of_max": abs(W[(sc, t, m)] - mean_max) < 1e-12})
    R = pd.DataFrame(rows)
    assert R.WORST_equals_mean_of_max.all()
    write(R, "dbar_definition.csv")


def item_b():
    rows = []
    for b in BLOCKS:
        c = pd.read_parquet(CACHE / b / "cal.parquet")
        s = c["score|src_zone_hour_speed"].to_numpy()
        for hk in [None, 0, 1, 2]:
            m = np.ones(len(s), bool) if hk is None else c.hopkind.to_numpy() == hk
            rows.append({"block": b, "hopkind": "all" if hk is None else hk, "n_cal": int(m.sum()),
                         "n_score_0": int((s[m] == 0).sum()), "n_score_below_1e-8": int((s[m] < 1e-8).sum()),
                         "min_positive_score": float(s[m][s[m] > 0].min())})
    write(pd.DataFrame(rows), "cal_score_floor.csv")


def item_c():
    D = pd.read_csv(ROOT / "results/porto_cctv_confirm2_posthoc/custody/custody_diffs.csv", comment="#")
    D = D.query("target == 0.95 and scope == 'combined' and h == 5 and (method_a == 'static' or method_b == 'static')")
    rows = []
    for r in D.itertuples():
        sgn = 1 if r.method_b == "static" else -1           # difference method - static
        lo, hi = sorted((sgn * r.lo, sgn * r.hi))
        rows.append({"method": r.method_a if sgn == 1 else r.method_b, "start": r.start, "diff_vs_static": sgn * r.diff,
                     "lo": lo, "hi": hi, "stored_pair": f"{r.method_a}-{r.method_b}"})
    write(pd.DataFrame(rows).sort_values(["start", "method"]), "custody_pairs.csv")


def item_g():
    trans_all = pd.read_parquet(WORK / "transitions.parquet")
    cams = pd.read_csv(WORK / "cameras.csv")
    rows, checks = [], []
    per_block = {}
    for b in BLOCKS:
        cfg = yaml.safe_load(open(RUNS / b / "t0950" / "s0" / "run_config.yaml"))
        tz, ex = cfg["timezone"], cfg["eval"]
        sp = ex["splits"]
        t = trans_all["t_exit"].to_numpy()
        m_train = _period_mask(t, sp["train"], tz)
        m_eval = np.zeros(len(t), bool)
        for s in sp["test"]:
            m_eval |= _period_mask(t, s["range"], tz)
        tr = _add_strata(trans_all, trans_all[m_train], ex.get("n_speed_bins", 4))
        tr = _add_spatial(tr, m_train, cams, ex.get("n_spatial_bins", 4))
        ev = tr[m_eval]
        H = pd.read_parquet(RUNS / b / "t0950" / "s0" / "hits.parquet", columns=["tr_id"] + DIMS)
        j = H.merge(ev[["tr_id"] + DIMS], on="tr_id", suffixes=("_h", "_r"))
        ok = all((j[f"{d}_h"] == j[f"{d}_r"]).all() for d in DIMS)
        checks.append({"block": b, "hits_rows": len(H), "matched": len(j), "nonexit_eval": int((~ev.is_exit).sum()),
                       "group_columns_equal": ok})
        assert ok and len(j) == len(H) == int((~ev.is_exit).sum())
        per_block[b] = ev
    for sc, ev in [("block1", per_block["block1"]), ("block2", per_block["block2"]),
                   ("combined", pd.concat(per_block.values()))]:
        rows.append({"scope": sc, "group": "grp_all=0", "n_transitions": len(ev), "n_exit": int(ev.is_exit.sum()),
                     "exit_share": ev.is_exit.mean()})
        for d in DIMS:
            for v, g in ev.groupby(d):
                rows.append({"scope": sc, "group": f"{d}={v}", "n_transitions": len(g), "n_exit": int(g.is_exit.sum()),
                             "exit_share": g.is_exit.mean()})
    write(pd.DataFrame(rows), "exit_by_group.csv")
    write(pd.DataFrame(checks), "exit_by_group_check.csv")


def item_h():
    S = pd.read_csv(A / "seed_range.csv")
    write(S, "seed_range.csv")
    E = pd.read_csv(A / "main_estimands.csv").query("scope == 'combined'")
    write(E[["target", "estimand", "proposed", "comparator", "point", "lo", "hi", "class", "seeds_improving",
             "seeds_worsening", "seed_agreement"]], "sign_agreement.csv")


def item_i():
    keep = ["mvp_log", "qr_ogd", "A2_aci_groups", "aci_g0005", "iii_mvp_log", "iv_mvp_log", "iii_qr_ogd", "iv_qr_ogd",
            "iii_aci", "iv_aci", "iii_aci_groups", "iv_aci_groups", "qr_groups_refit", "Bi_refit_a", "Bii_refit_a"]
    F = []
    for f in ("B_aci_estimates.csv", "B_refit_estimates.csv"):
        x = pd.read_csv(RV / f, comment="#").query("scope == 'combined' and estimand in ['cost_mean', 'D']")
        F.append(x[x.method.isin(keep)].assign(source=f"review/{f}"))
    X = pd.concat(F).drop_duplicates(["target", "method", "estimand"])
    write(X[["source", "target", "method", "estimand", "point", "seed_min", "seed_max", "lo", "hi"]]
          .sort_values(["estimand", "target", "method"]), "abs_cost_feedback.csv")


def item_j():
    Q = pd.read_csv(ROOT / "exploratory/intersections_q/intersections_q.csv", comment="#")
    Q = Q[Q.method.isin(["qr_groups", "A3_qr_groups_inter"])]
    T = sorted(Q.target.unique())

    def ci(d, lo, hi):
        f = lambda v: f"{100 * v:.1f}".replace("-", "$-$")
        return f"{f(d)} [{f(lo)}, {f(hi)}]"
    L = ["% source: exploratory/intersections_q/intersections_q.csv (POST HOC exploratory; frozen intersections.csv for "
         "qr_groups, review A_intersections.csv for A3_qr_groups_inter); shortfall d (pp) with conservative 95% bounds "
         "(taxi and day, B = 2000), scope combined, seed mean. qr_groups + I1-I6 is evaluated on the groups it was "
         "calibrated for (self-evaluation).",
         r"\setlength{\tabcolsep}{3.4pt}", r"\begin{tabular}{@{}ll" + "r" * len(T) + "@{}}", r"\toprule",
         "Intersection & Method & " + " & ".join(f"{t:.2f}" for t in T) + r" \\", r"\midrule"]
    lab = {"qr_groups": r"\texttt{qr\_groups}", "A3_qr_groups_inter": r"\texttt{qr\_groups} + I1--I6"}
    for k, c in enumerate(sorted(Q.cell.unique())):
        if k:
            L.append(r"\addlinespace")
        for j, m in enumerate(["qr_groups", "A3_qr_groups_inter"]):
            g = Q[(Q.cell == c) & (Q.method == m)].set_index("target")
            L.append(f"{c if j == 0 else ''} & {lab[m]} & " + " & ".join(ci(g.deficit[t], g.lo[t], g.hi[t]) for t in T)
                     + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    (OUT / "tab_c2_inter_groups.tex").write_text("\n".join(L) + "\n")
    WRITTEN.append("tab_c2_inter_groups.tex")


def inter_cols(df):
    return np.column_stack([np.all([df[d].to_numpy() == v for d, v in cond], axis=0).astype(float)
                            for cond in INTER.values()])


def item_k():
    rows = []
    for b in BLOCKS:
        cal = pd.read_parquet(CACHE / b / "cal.parquet")
        cfg = yaml.safe_load(open(RUNS / b / "t0950" / "s0" / "run_config.yaml"))
        mg = cfg["eval"]["multigroup"]; max_n = mg.get("qr_max_n", 80000)
        X0 = _design([cal], mg["dims"])[0]
        I = inter_cols(cal)
        X = np.column_stack([X0, I])
        sv = np.linalg.svd(X - 0, compute_uv=False)
        r = {"block": b, "n_cal": len(cal), "qr_max_n": max_n, "p_qr_groups": X0.shape[1], "p_with_inter": X.shape[1],
             "rank_qr_groups": int(np.linalg.matrix_rank(X0)), "rank_with_inter": int(np.linalg.matrix_rank(X)),
             "cond_with_inter": float(sv[0] / sv[-1]), "cond_qr_groups": float(np.linalg.cond(X0))}
        C = np.corrcoef(X[:, 1:].T)                       # without the intercept
        for k, nm in enumerate(INTER):
            ci_ = X0.shape[1] - 1 + k
            cc = np.abs(np.delete(C[ci_], ci_)); r[f"{nm}_n_cal"] = int(I[:, k].sum())
            r[f"{nm}_max_abs_corr"] = float(np.nanmax(cc))
        for s in SEEDS:                                    # the subsample of qr_group_taus / qr_inter_taus (seed = eval seed)
            if len(cal) > max_n:
                idx = np.random.default_rng(s).choice(len(cal), max_n, replace=False)
                Is = I[idx]
            else:
                Is = I
            for k, nm in enumerate(INTER):
                r[f"{nm}_n_sub_s{s}"] = int(Is[:, k].sum())
        rows.append(r)
    write(pd.DataFrame(rows), "qr_inter_design.csv")


def item_l():
    Q = pd.read_csv(ROOT / "exploratory/qrogd_clip/qrogd_clip.csv", comment="#").query("group == 'hopkind=2'").copy()
    gamma = 0.005
    Q["dev_final"] = Q.theta_final.abs() / (gamma * Q.T_G)              # |(1/T_G) sum (err - alpha)| by (7), no clipping
    Q["dev_bound_maxabs"] = np.maximum(Q.theta_min.abs(), Q.theta_max.abs()) / (gamma * Q.T_G)
    write(Q[["block", "target", "seed", "T_G", "n_upd_clipped", "theta_final", "theta_min", "theta_max", "dev_final",
             "dev_bound_maxabs"]], "postgap_theta.csv")


def item_m():
    C = pd.read_csv(RV / "C_estimates.csv", comment="#").query("scope == 'combined' and estimand == 'D'")
    M = C.groupby(["label", "predictor", "method"]).target.apply(lambda x: " ".join(f"{v:g}" for v in sorted(set(x))))
    write(M.reset_index().rename(columns={"target": "targets"}), "predictor_targets.csv")


def item_n():
    C = pd.read_csv(ROOT / "results/porto_cctv_confirm2_posthoc/custody/custody.csv", comment="#")
    C = C.query("scope == 'combined' and start == 'reacquired' and h == 5 and target == 0.95")
    C = C[~C.method.isin(["citytrac_nominal", "spatula_rule|fixed"])]
    vmin, vmax = C.custody.min(), C.custody.max()
    write(pd.DataFrame([{"min": vmin, "argmin": C.loc[C.custody.idxmin(), "method"], "max": vmax,
                         "argmax": C.loc[C.custody.idxmax(), "method"], "diff_raw": vmax - vmin,
                         "min_1d": f"{100 * vmin:.1f}", "max_1d": f"{100 * vmax:.1f}", "diff_1d": f"{100 * (vmax - vmin):.1f}",
                         "diff_of_rounded": round(float(f"{100 * vmax:.1f}") - float(f"{100 * vmin:.1f}"), 1)}]),
          "custody_rounding.csv")


def item_o():
    rows = []
    for b in BLOCKS:
        ref = None
        for t in ("t0900", "t0950", "t0980"):              # the feedback mask does not depend on the target
            fbs = [pd.read_parquet(RUNS / b / t / f"s{s}" / "hits.parquet", columns=["feedback"]).feedback.to_numpy()
                   for s in SEEDS]
            ref = fbs if ref is None else ref
            assert all(np.array_equal(x, y) for x, y in zip(ref, fbs)), (b, t)
        H = pd.read_parquet(RUNS / b / "t0950" / "s0" / "hits.parquet", columns=["hopkind"])
        pg = H.hopkind.to_numpy() == 2
        for s in SEEDS:
            fb = ref[s].astype(bool); n = len(fb)
            rng = np.random.default_rng(s)                 # posthoc_review_methods.audit_mask: first draw = feedback mask
            assert np.array_equal(rng.random(n) < 0.3, fb)
            au = rng.random(n) < 0.05
            rows.append({"block": b, "seed": s, "n_eval_hops": n, "n_feedback": int(fb.sum()), "n_audit": int(au.sum()),
                         "expected_audit": 0.05 * n, "n_postgap": int(pg.sum()), "n_postgap_audit": int((au & pg).sum()),
                         "expected_postgap_audit": 0.05 * pg.sum(), "n_postgap_feedback": int((fb & pg).sum()),
                         "n_audit_and_feedback": int((au & fb).sum())})
    write(pd.DataFrame(rows), "audit_counts.csv")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (item_a, item_b, item_c, item_g, item_h, item_i, item_j, item_k, item_l, item_m, item_n, item_o):
        f(); print("[gate8]", f.__name__, "done", flush=True)
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "exploratory/gate8/gate8_recount.py"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
    pd.DataFrame({"file": [f"exploratory/gate8/{x}" for x in WRITTEN],
                  "sha256": [hashlib.sha256((OUT / x).read_bytes()).hexdigest() for x in WRITTEN],
                  "script_commit": commit}).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
