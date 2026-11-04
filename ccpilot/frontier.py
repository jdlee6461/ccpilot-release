"""Post-hoc cost-matched comparison: worst-group coverage as a function of search cost.

Any method can raise its worst group by searching more (raising its target). A fair
comparison therefore asks: at the SAME cost, which method has the better worst group,
and what does each method need to spend before no group is significantly below the bar?

Curves (per test segment), cost normalised by the marginal oracle at target 0.95:
  static   : split-conformal threshold at targets t
  citytrac : CityTrac-style model-probability constraint at targets t (no calibration)
  mvp_log  : proposed multi-group online calibration at targets t
Single points at t = 0.95: qr_groups, qr_ogd, spatula_rule.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import conformal_tau
from .evaluate import _period_mask, _add_strata, _add_spatial, _wilson_ub
from .multigroup import group_matrix, mvp_taus, qr_group_taus, qr_ogd_taus
from .predictors import VisibilityModel, SpatulaRule, CityTracRule, candidate_sets, _truth_by_tr


def _group_stats(hit, m, strata, min_n, bar):
    worst, wname, nsig = np.inf, "", 0
    for d, v in strata.items():
        for g in np.unique(v[m]):
            mm = m & (v == g)
            n = int(mm.sum())
            if n < min_n:
                continue
            k = int(hit[mm].sum())
            if _wilson_ub(k, n) < bar:
                nsig += 1
            if k / n < worst:
                worst, wname = k / n, f"{d}={g}"
    return worst, wname, nsig


def run(cfg, trans, truth, cams, n_bins, out_dir, predictor, targets):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    tz = cfg["timezone"]; ev = cfg["events"]; ex = cfg["eval"]
    delta = ev["bin_s"]; t_max = ev["t_max_s"]
    rng = np.random.default_rng(ex.get("seed", 0))
    t = trans["t_exit"].to_numpy(); sp = ex["splits"]
    m_train = _period_mask(t, sp["train"], tz); m_cal = _period_mask(t, sp["cal"], tz)
    segs = {s["name"]: _period_mask(t, s["range"], tz) for s in sp["test"]}
    m_test = np.zeros(len(t), bool)
    for m in segs.values():
        m_test |= m
    trans = _add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    trans = _add_spatial(trans, m_train, cams, ex.get("n_spatial_bins", 4))
    ok = ~trans["is_exit"].to_numpy()
    tr_train = trans[m_train]
    tr_cal = trans[m_cal & ok].sort_values("t_exit").reset_index(drop=True)
    tr_test = trans[m_test & ok].sort_values("t_exit").reset_index(drop=True)
    seg_of = np.full(len(tr_test), "", dtype=object)
    for name, m in segs.items():
        seg_of[tr_test["tr_id"].isin(set(trans.loc[m, "tr_id"])).to_numpy()] = name
    truth_map = _truth_by_tr(truth)
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    strata = {d: tr_test[d].to_numpy() for d in ex["strata"]}
    min_n = ex.get("min_group_n", 200); bar = ex.get("group_bar", 0.94)

    vm = VisibilityModel(ex["predictors"][predictor], cand, n_bins, **ex["model"]).fit(tr_train, truth_map)
    s_cal, _, _ = vm.score(tr_cal, truth_map)
    s_test, kid, _ = vm.score(tr_test, truth_map)
    fb = rng.random(len(tr_test)) < ex["aci"]["feedback_fraction"]
    t_exit = tr_test["t_exit"].to_numpy(); t_hit = tr_test["t_arrive"].to_numpy(); t_miss = t_exit + t_max
    mg = ex["multigroup"]
    (G_cal, G_test), _ = group_matrix([tr_cal, tr_test], mg["dims"])
    mv = next(v for v in mg["mvp_variants"] if v["name"] == "mvp_log")

    rows = []

    def add(method, tgt, hit, cost):
        for seg in segs:
            m = seg_of == seg
            w, wn, ns = _group_stats(hit, m, strata, min_n, bar)
            rows.append({"method": method, "target": tgt, "segment": seg, "coverage": hit[m].mean(),
                         "worst_group_cov": w, "worst_group": wn, "n_groups_sig_below_bar": ns,
                         "cost_mean_cam_s": cost[m].mean()})

    # oracle reference (marginal, target 0.95) per segment
    oracle = {}
    for seg in segs:
        m = seg_of == seg
        oracle[seg] = vm.cost(kid[m], conformal_tau(s_test[m], 0.05), delta).mean()

    for tg in targets["static"]:
        tau = conformal_tau(s_cal, 1 - tg)
        add("static", tg, s_test >= tau, vm.cost(kid, np.full(len(s_test), tau), delta))
        print(f"[frontier] static {tg}")
    for tg in targets["citytrac"]:
        cr = CityTracRule(cand, n_bins, delta, tg, ex.get("citytrac", {}).get("window_q", 0.98),
                          ex.get("citytrac", {}).get("min_n", 30)).fit(tr_train)
        h, c = cr.evaluate(tr_test, truth_map)
        add("citytrac", tg, h, c)
        print(f"[frontier] citytrac {tg}")
    for tg in targets["mvp_log"]:
        tau, _, _ = mvp_taus(s_test, t_exit, t_hit, t_miss, G_test, s_cal, tr_cal["t_exit"].to_numpy(), G_cal,
                             1 - tg, fb, m=mv.get("m", 40), r=mv.get("r", 1000), eta=mv.get("eta", "theory"),
                             eps=mv.get("eps", 1.0), seed=ex.get("seed", 0), scale="log",
                             a_min=mv.get("a_min", 0.002))
        add("mvp_log", tg, s_test >= tau, vm.cost(kid, tau, delta))
        print(f"[frontier] mvp_log {tg}")
    # single points at 0.95
    tq, _ = qr_group_taus(tr_cal, s_cal, tr_test, mg["dims"], 0.05, mg.get("qr_max_n", 80000), ex.get("seed", 0))
    add("qr_groups", 0.95, s_test >= tq, vm.cost(kid, tq, delta))
    o = mg.get("qr_ogd", {})
    to = qr_ogd_taus(tq, s_test, t_exit, t_hit, t_miss, G_test, 0.05, fb, o.get("gamma", 0.005), o.get("clip", 3.0))
    add("qr_ogd", 0.95, s_test >= to, vm.cost(kid, to, delta))
    sr = SpatulaRule(cand, n_bins, delta, ex["spatula"]["s_thresh"], ex["spatula"]["t_quantile"]).fit(tr_train)
    h, c = sr.evaluate(tr_test, truth_map)
    add("spatula", np.nan, h, c)

    df = pd.DataFrame(rows)
    df["cost_over_oracle"] = df["cost_mean_cam_s"] / df["segment"].map(oracle)
    df.to_csv(out_dir / "frontier.csv", index=False)

    # cost-matched worst group (at mvp_log target-0.95 cost) and cost to reach group validity
    summ = []
    for seg in segs:
        d = df[df["segment"] == seg]
        ref = d[(d["method"] == "mvp_log") & (d["target"] == 0.95)]["cost_over_oracle"].iloc[0]
        for meth in ["static", "citytrac", "mvp_log"]:
            c = d[d["method"] == meth].sort_values("cost_over_oracle")
            x, y = c["cost_over_oracle"].to_numpy(), c["worst_group_cov"].to_numpy()
            at_ref = np.interp(ref, x, y) if x.min() <= ref <= x.max() else np.nan
            valid = c[c["n_groups_sig_below_bar"] == 0]
            summ.append({"segment": seg, "method": meth, "ref_cost_ratio(mvp_log@0.95)": ref,
                         "worst_group_at_ref_cost": at_ref,
                         "min_cost_ratio_no_sig_group": valid["cost_over_oracle"].min() if len(valid) else np.nan,
                         "target_at_that_cost": valid.sort_values("cost_over_oracle")["target"].iloc[0]
                         if len(valid) else np.nan})
    summ = pd.DataFrame(summ)
    summ.to_csv(out_dir / "cost_matched.csv", index=False)
    _plot(df, out_dir, bar)
    return df, summ


def _plot(df, out_dir, bar):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style = {"static": ("tab:blue", "o"), "citytrac": ("tab:orange", "s"), "mvp_log": ("tab:red", "^"),
             "qr_groups": ("tab:green", "D"), "qr_ogd": ("tab:purple", "v"), "spatula": ("k", "x")}
    for seg in df["segment"].unique():
        d = df[df["segment"] == seg]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
        for meth, g in d.groupby("method"):
            col, mk = style.get(meth, ("gray", "."))
            g = g.sort_values("cost_over_oracle")
            ls = "-" if len(g) > 1 else "none"
            axes[0].plot(g["cost_over_oracle"], g["worst_group_cov"], ls, color=col, marker=mk, ms=5, label=meth)
            axes[1].plot(g["cost_over_oracle"], g["coverage"], ls, color=col, marker=mk, ms=5, label=meth)
            for _, r in g.iterrows():
                if meth in ("static", "citytrac", "mvp_log") and not np.isnan(r["target"]):
                    axes[0].annotate(f"{r['target']:.2f}", (r["cost_over_oracle"], r["worst_group_cov"]),
                                     fontsize=6, xytext=(3, 3), textcoords="offset points", color=col)
        axes[0].axhline(bar, color="gray", ls="--", lw=1)
        axes[1].axhline(0.95, color="gray", ls="--", lw=1)
        for ax, yl in zip(axes, ["worst-group hop recall", "overall hop recall"]):
            ax.set_xscale("log"); ax.set_xlabel("search cost / marginal oracle (log scale)"); ax.set_ylabel(yl)
            ax.grid(alpha=0.3)
        axes[0].set_ylim(0.8, 1.0); axes[1].set_ylim(0.85, 1.0)
        axes[0].legend(fontsize=8); axes[0].set_title(f"worst group vs cost [{seg}] (labels = target)", fontsize=9)
        axes[1].set_title(f"overall recall vs cost [{seg}]", fontsize=9)
        fig.tight_layout(); fig.savefig(out_dir / f"frontier_{seg}.png", dpi=140); plt.close(fig)
