"""POST-HOC diagnosis of adaptation lag under camera outage (not pre-registered; report as post hoc).

    python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml
    python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml --analyze-only

Two hypotheses for the slow recovery of the online multi-group methods after an outage:
  saturation : mvp_log keeps choosing the top bucket (q >= 39/40), where tau is already
               capped at the a_min calibration quantile, so it cannot widen the search further
  inertia    : the warm-start statistics (V, N) accumulated over the calibration week
               dominate the per-bucket sums, so the sign of V flips only after many misses
Runs (same offline sites as posthoc_outage.py, seed 7):
  scenarios  : none (control), rand10, region
  starts     : 2014-06-21 (as in posthoc_outage.py) and 2014-06-12 (early in segment A)
  warm start : mvp_log / mvp_global with the warm-start V and N multiplied by 1.0, 0.1, 0.
               THIS IS A DIAGNOSTIC ABLATION, NOT A METHOD CHANGE: weight 1.0 is the
               registered method; 0.1 and 0 only test whether warm-start inertia causes the lag.
Saved per run: per-query q of every MVP variant (mvp_q.parquet), (V, N) snapshots at the
outage start, +6/12/18 h and then daily (mvp_state.parquet), per-hop hits (hits.parquet).
Group statistics use the pre-registered 25 groups. Output: <out_dir>_posthoc/outage_diag/.
"""
import argparse
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot import evaluate
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import load_config, offline_sites, outage_events, reduce_cfg, set_display

SCENARIOS = ["none", "rand10", "region"]
STARTS = ["2014-06-21", "2014-06-12"]
WEIGHTS = [1.0, 0.1, 0.0]
DIMS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]   # + 'all' = prereg 25
SHOW = ["static", "qr_ogd", "mvp_global", "mvp_log"]
BIN_H = 6
SAT_Q = 39 / 40


def vname(base, w):
    return base if w == 1.0 else f"{base}_w{int(round(w * 100)):03d}"


def run_dir(root, start, sc):
    return root / f"start_{start.replace('-', '')}" / sc


# ------------------------------------------------------------------ evaluation runs
def run_one(base, pred, start, sc, off, sight, root):
    tz = base["timezone"]
    t_start = date_to_unix(start, tz)
    trans, truth, n_bins, n_drop = outage_events(sight, base, off, t_start)
    cams = pd.read_csv(Path(base["work_dir"]) / "cameras.csv")
    cfg = reduce_cfg(copy.deepcopy(base), pred)
    ex = cfg["eval"]
    t0, end = ex["splits"]["test"][0]["range"][0], ex["splits"]["test"][-1]["range"][1]
    s48 = str((pd.Timestamp(start) + pd.Timedelta(days=2)).date())
    ex["splits"]["test"] = [{"name": "pre", "range": [t0, start]},
                            {"name": "post48", "range": [start, s48]},
                            {"name": "late", "range": [s48, end]}]
    ex["outage"] = {"cams": off, "t_start": t_start}
    ex["save_hits"] = True
    mg = ex["multigroup"]
    mg["mvp_variants"] = [dict(v, name=vname(v["name"], w), warm_weight=w)
                          for w in WEIGHTS for v in mg["mvp_variants"]]
    t_end = date_to_unix(end, tz)
    snaps = [t_start - 86400.0, t_start, t_start + 6 * 3600, t_start + 12 * 3600, t_start + 18 * 3600]
    snaps += list(np.arange(t_start + 86400.0, t_end, 86400.0))
    ex["mvp_diag"] = {"snapshot_times": snaps}
    print(f"\n########## start {start}, scenario {sc}: {len(off)} sites offline, {n_drop} sightings removed")
    evaluate.run(cfg, trans, truth, cams, n_bins, run_dir(root, start, sc))
    return n_drop


# ------------------------------------------------------------------ analysis
def load_run(d, pred, t_start):
    H = pd.read_parquet(d / "hits.parquet")
    Q = pd.read_parquet(d / "mvp_q.parquet")
    assert (H["tr_id"].to_numpy() == Q["tr_id"].to_numpy()).all()
    H = H.rename(columns={c: "cost:" + c.split("|")[2] for c in H.columns if c.startswith(f"cost|{pred}|")})
    H = H.rename(columns={c: c.split("|")[2] for c in H.columns if c.startswith(f"hit|{pred}|")})
    H = H.rename(columns={"hit|spatula_rule|fixed": "spatula"})
    for c in Q.columns:
        if c.startswith(f"q|{pred}|"):
            H["q|" + c.split("|")[2]] = Q[c].to_numpy()
    H["hours"] = (H["t_exit"] - t_start) / 3600.0
    H["bin"] = np.floor(H["hours"] / BIN_H).astype(int)
    return H


def group_frames(H, cols, by):
    """Long table (by..., group, n, mean of each col) over the 25 pre-registered groups."""
    out = []
    g = H.groupby(by)[cols]
    out.append(g.mean().join(g.size().rename("n")).reset_index().assign(group="all"))
    for d in DIMS:
        g = H.groupby(by + [d])[cols]
        t = g.mean().join(g.size().rename("n")).reset_index()
        t["group"] = d + "=" + t.pop(d).astype(int).astype(str)
        out.append(t)
    return pd.concat(out, ignore_index=True)


def worst(gt, col, min_n):
    gt = gt[gt["n"] >= min_n]
    i = gt[col].idxmin()
    return gt.loc[i, col], gt.loc[i, "group"], int(gt.loc[i, "n"]), len(gt)


def analyze(root, starts, scenarios, pred, tz, min_n_bin, min_n_48, bar):
    ts_rows, rec_rows, sat_all, state_all = [], [], [], []
    for start in starts:
        t_start = date_to_unix(start, tz)
        for sc in scenarios:
            d = run_dir(root, start, sc)
            H = load_run(d, pred, t_start)
            meths = [c for c in H.columns if c in SHOW or c.startswith("mvp_")]
            G = group_frames(H, meths, ["bin"])
            for m in meths:
                for b, gb in G.groupby("bin"):
                    tot = gb[gb["group"] == "all"].iloc[0]
                    w = worst(gb, m, min_n_bin)
                    ts_rows.append({"start": start, "scenario": sc, "method": m, "bin": b, "hours": b * BIN_H,
                                    "n": int(tot["n"]), "coverage": tot[m], "worst_group_cov": w[0],
                                    "worst_group": w[1], "worst_n": w[2], "n_groups": w[3]})
                for win, lo, hi in [("pre48", -48, 0), ("post48", 0, 48)]:
                    Hm = H[(H["hours"] >= lo) & (H["hours"] < hi)]
                    gt = group_frames(Hm.assign(k=0), [m], ["k"])
                    w = worst(gt, m, min_n_48)
                    ub = [evaluate._wilson_ub(r[m] * r["n"], r["n"]) for _, r in gt[gt["n"] >= min_n_48].iterrows()]
                    rec_rows.append({"start": start, "scenario": sc, "method": m, "window": win, "n": len(Hm),
                                     "coverage": Hm[m].mean(), "cost_mean_cam_s": Hm["cost:" + m].mean(),
                                     "worst_group_cov": w[0], "worst_group": w[1],
                                     "n_sig_below_bar": int(np.sum(np.array(ub) < bar))})
            qc = [c for c in H.columns if c.startswith("q|")]
            S = H[["bin"] + DIMS].copy()
            for c in qc:
                S[c[2:]] = (H[c] >= SAT_Q).astype(float)
            sat = group_frames(S, [c[2:] for c in qc], ["bin"]).melt(
                id_vars=["bin", "group", "n"], var_name="method", value_name="sat_share")
            sat_all.append(sat.assign(start=start, scenario=sc, hours=sat["bin"] * BIN_H))
            st = pd.read_parquet(d / "mvp_state.parquet")
            st = st[st["predictor"] == pred].drop(columns="predictor")
            state_all.append(st.assign(start=start, scenario=sc, hours=(st["t_snap"] - t_start) / 3600.0))
    TS = pd.DataFrame(ts_rows); REC = pd.DataFrame(rec_rows)
    SAT = pd.concat(sat_all, ignore_index=True); ST = pd.concat(state_all, ignore_index=True)

    # recovery summary: 48 h after the outage start vs the no-outage control (same start, same method)
    post = REC[REC["window"] == "post48"].drop(columns="window")
    ctl = post[post["scenario"] == "none"].set_index(["start", "method"])
    post["d_cov_vs_none"] = post["coverage"].to_numpy() - ctl["coverage"].reindex(
        pd.MultiIndex.from_frame(post[["start", "method"]])).to_numpy()
    post["d_worst_vs_none"] = post["worst_group_cov"].to_numpy() - ctl["worst_group_cov"].reindex(
        pd.MultiIndex.from_frame(post[["start", "method"]])).to_numpy()
    rh = []
    for (start, sc, m), g in TS[(TS["bin"] >= 0) & (TS["bin"] < 48 // BIN_H)].groupby(["start", "scenario", "method"]):
        cov = g.sort_values("bin")["coverage"].to_numpy()
        ok = [b for b in range(len(cov)) if (cov[b:] >= bar).all()]
        rh.append({"start": start, "scenario": sc, "method": m, "min_6h_cov_48h": cov.min(),
                   "recover_h": ok[0] * BIN_H if ok else np.nan})
    post = post.merge(pd.DataFrame(rh), on=["start", "scenario", "method"])
    pre = REC[REC["window"] == "pre48"][["start", "scenario", "method", "coverage", "worst_group_cov", "cost_mean_cam_s"]]
    post = post.merge(pre.rename(columns={"coverage": "pre48_cov", "worst_group_cov": "pre48_worst",
                                          "cost_mean_cam_s": "pre48_cost"}),
                      on=["start", "scenario", "method"])

    # sign changes of V after the outage start (buckets that have been used at least once)
    at0 = ST[ST["hours"] == 0][["start", "scenario", "method", "group", "bucket", "V", "N"]]
    flips = []
    for key, g in ST[ST["hours"] >= 0].groupby(["start", "scenario", "method", "group", "bucket"]):
        g = g.sort_values("hours")
        if g["N"].max() == 0:
            continue
        s0 = np.sign(g["V"].iloc[0])
        ch = g[np.sign(g["V"]) != s0]
        flips.append(dict(zip(["start", "scenario", "method", "group", "bucket"], key),
                          V_start=g["V"].iloc[0], N_start=g["N"].iloc[0], V_end=g["V"].iloc[-1],
                          N_end=g["N"].iloc[-1], first_flip_h=ch["hours"].iloc[0] if len(ch) else np.nan))
    FL = pd.DataFrame(flips)
    return TS, post, SAT, ST, FL, at0


# ------------------------------------------------------------------ figures
# categorical slots 1-4 of the reference palette, fixed order; markers as secondary encoding
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MK = ["o", "s", "^", "D"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3de"


def _style(ax):
    ax.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)


def _refs(ax, bar):
    ax.axhline(0.95, color=MUTED, lw=0.8, ls="--"); ax.axhline(bar, color=MUTED, lw=0.8, ls=":")
    ax.axvline(0, color=INK, lw=0.8)


def lines_grid(TS, rows, cols, series, title, path, bar, xlim=(-48, 96)):
    """rows/cols/series: lists of (label, filter-dict); y = coverage or worst_group_cov (in col filter '_y')."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(rows), len(cols), figsize=(4.2 * len(cols), 2.8 * len(rows)),
                             sharex=True, squeeze=False)
    for i, (rl, rf) in enumerate(rows):
        for j, (cl, cf) in enumerate(cols):
            ax = axes[i, j]; _style(ax); _refs(ax, bar)
            ycol = cf.get("_y", "coverage")
            for k, (sl, sf) in enumerate(series):
                f = {**rf, **{a: b for a, b in cf.items() if a != "_y"}, **sf}
                g = TS
                for a, b in f.items():
                    g = g[g[a] == b]
                g = g[(g["hours"] >= xlim[0]) & (g["hours"] < xlim[1])].sort_values("hours")
                ax.plot(g["hours"] + BIN_H / 2, g[ycol], color=C[k], lw=2, marker=MK[k], ms=4, label=sl)
            ax.set_xlim(*xlim)
            if i == 0:
                ax.set_title(cl, fontsize=9, color=INK)
            if j == 0:
                ax.set_ylabel(rl, fontsize=9, color=INK)
            if i == len(rows) - 1:
                ax.set_xlabel("hours since outage start (6 h bins)", fontsize=8, color=MUTED)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=len(series), frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(title, fontsize=10, color=INK, y=1.04)
    fig.text(0.5, -0.01, f"dashed: target 0.95, dotted: bar {bar}. Post hoc, not pre-registered.",
             ha="center", fontsize=7, color=MUTED)
    fig.tight_layout(); fig.savefig(path, dpi=160, bbox_inches="tight"); plt.close(fig)


def sat_plot(SAT, starts, scenarios, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = ["all", "hopkind=2", "hopkind=1", "speed_bin=0"]
    fig, axes = plt.subplots(len(starts), len(groups), figsize=(3.6 * len(groups), 2.6 * len(starts)),
                             sharex=True, sharey=True, squeeze=False)
    for i, st in enumerate(starts):
        for j, gname in enumerate(groups):
            ax = axes[i, j]; _style(ax); ax.axvline(0, color=INK, lw=0.8)
            for k, sc in enumerate(scenarios):
                g = SAT[(SAT["start"] == st) & (SAT["scenario"] == sc) & (SAT["method"] == "mvp_log") &
                        (SAT["group"] == gname) & (SAT["hours"] >= -48) & (SAT["hours"] < 96)].sort_values("hours")
                ax.plot(g["hours"] + BIN_H / 2, g["sat_share"], color=C[k], lw=2, marker=MK[k], ms=4, label=sc)
            if i == 0:
                ax.set_title(gname, fontsize=9, color=INK)
            if j == 0:
                ax.set_ylabel(f"start {st}\nshare q >= 39/40", fontsize=8, color=INK)
            if i == len(starts) - 1:
                ax.set_xlabel("hours since outage start", fontsize=8, color=MUTED)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=len(scenarios), frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("mvp_log top-bucket saturation (post hoc)", fontsize=10, color=INK, y=1.05)
    fig.tight_layout(); fig.savefig(path, dpi=160, bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--scenarios", nargs="*", default=SCENARIOS)
    ap.add_argument("--starts", nargs="*", default=STARTS)
    ap.add_argument("--radius", type=float, default=800.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-n-bin", type=int, default=100, help="min group size for worst group in a 6 h bin")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--run-only", action="store_true")
    a = ap.parse_args()
    base = load_config(a.config)
    tz = base["timezone"]; bar = base["eval"].get("group_bar", 0.94)
    min_n = base["eval"].get("min_group_n", 200)
    root = Path(base["out_dir"] + "_posthoc") / "outage_diag"
    if not a.analyze_only:
        work = Path(base["work_dir"])
        sight = pd.read_parquet(work / "sightings.parquet")
        cams = pd.read_csv(work / "cameras.csv")
        # sites drawn in posthoc_outage.py's default order so rand10/region are the same sites
        sites = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams,
                              pd.read_parquet(work / "transitions.parquet"), base, a.radius, a.seed)
        meta = []
        for start in a.starts:
            for sc in a.scenarios:
                n_drop = run_one(base, a.predictor, start, sc, sites[sc], sight, root)
                meta.append({"start": start, "scenario": sc, "n_offline": len(sites[sc]), "sightings_removed": n_drop,
                             "offline_sites": ",".join(map(str, sites[sc]))})
        root.mkdir(parents=True, exist_ok=True)
        tag = "_".join(s.replace("-", "") for s in a.starts) + "_" + "_".join(a.scenarios)
        pd.DataFrame(meta).to_csv(root / f"runs_{tag}.csv", index=False)
    if a.run_only:
        return
    starts = a.starts
    TS, REC, SAT, ST, FL, _ = analyze(root, starts, a.scenarios, a.predictor, tz, a.min_n_bin, min_n, bar)
    TS.to_csv(root / "timeseries_6h.csv", index=False)
    REC.to_csv(root / "recovery_48h.csv", index=False)
    SAT.to_csv(root / "saturation_6h.csv", index=False)
    ST.to_parquet(root / "mvp_state_all.parquet")
    FL.to_csv(root / "v_sign_flips.csv", index=False)
    (root / "README.txt").write_text(
        "POST-HOC diagnosis (not pre-registered). Warm-start weights 0.1 and 0 (variants *_w010, *_w000)\n"
        "are a diagnostic ablation of the registered mvp_log / mvp_global, NOT a method change.\n"
        f"6 h worst group: groups with n >= {a.min_n_bin}; 48 h worst group: n >= {min_n}.\n"
        "recover_h: first 6 h bin (hours after start) from which every 6 h coverage up to 48 h is >= bar.\n")

    scen = [(s, {"scenario": s}) for s in a.scenarios]
    meth = [(m, {"method": m}) for m in SHOW]
    for st in starts:
        lines_grid(TS, scen, [("mean coverage", {"start": st}), ("worst group (6 h, n >= %d)" % a.min_n_bin,
                   {"start": st, "_y": "worst_group_cov"})], meth,
                   f"Coverage after outage start {st} (post hoc)", root / f"fig_recovery_{st.replace('-', '')}.png", bar)
        for bm in ["mvp_log", "mvp_global"]:
            ser = [(f"warm x{w:g}", {"method": vname(bm, w)}) for w in WEIGHTS]
            lines_grid(TS, scen, [("mean coverage", {"start": st}),
                                  ("worst group", {"start": st, "_y": "worst_group_cov"})], ser,
                       f"{bm}: warm-start ablation, start {st} (diagnostic, not a method change)",
                       root / f"fig_warm_{bm}_{st.replace('-', '')}.png", bar)
    if len(starts) > 1:
        ser = [(f"start {s}", {"start": s}) for s in starts]
        lines_grid(TS, scen, [(m, {"method": m}) for m in ["mvp_log", "mvp_global", "qr_ogd"]], ser,
                   "Mean coverage by outage start date (post hoc)", root / "fig_start_compare.png", bar, xlim=(-24, 72))
    sat_plot(SAT, starts, a.scenarios, root / "fig_saturation_mvp_log.png")

    set_display()
    print("\n================ POST-HOC OUTAGE DIAGNOSIS (not pre-registered) ================")
    print(REC[REC["method"].isin(SHOW + [vname(b, w) for b in ["mvp_log", "mvp_global"] for w in WEIGHTS[1:]])][
        ["start", "scenario", "method", "pre48_cov", "coverage", "d_cov_vs_none", "worst_group_cov", "worst_group",
         "d_worst_vs_none", "n_sig_below_bar", "min_6h_cov_48h", "recover_h", "pre48_cost", "cost_mean_cam_s"]].round(4).to_string(index=False))
    print(f"\n-> {root}")


if __name__ == "__main__":
    main()
