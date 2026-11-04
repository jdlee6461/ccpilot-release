"""Chapter 6 figures (vector PDF) and their data files.

    python scripts/make_figures.py [name ...]      (run from paper/; `make figures`)

Writes generated/figures/<name>.pdf and generated/data/<name>.csv. Deterministic: the PDF carries no creation
date, so reruns give identical files.
"""
import os
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch6lib as L  # noqa: E402

ONE_COL, TWO_COL = 3.5, 7.16      # inches (IEEE)
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "lines.linewidth": 1.0, "lines.markersize": 4, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02, "axes.spines.top": False, "axes.spines.right": False,
})
GREY = "#9a9a9a"
REF = {0.95: {"color": "black", "linewidth": 0.7, "linestyle": "-", "zorder": 1},             # target
       0.94: {"color": "black", "linewidth": 0.7, "linestyle": (0, (3, 2)), "zorder": 1}}     # group bar


def refline(ax, y):
    """Reference line with one style per level, identical in every panel and figure."""
    return ax.axhline(y, **REF[y])


def check_reflines(fig):
    """All horizontal reference lines at the same y must have identical width, style and colour."""
    seen = {}
    for ax in fig.axes:
        for ln in ax.get_lines():
            y = ln.get_ydata()
            if len(y) == 2 and y[0] == y[1] and ln.get_xdata()[0] == 0 and ln.get_xdata()[1] == 1:
                key = round(float(y[0]), 6)
                prop = (ln.get_linewidth(), str(ln.get_linestyle()), str(ln.get_dashes() if hasattr(ln, "get_dashes") else ""),
                        ln.get_color(), ln.get_zorder())
                assert seen.setdefault(key, prop) == prop, (key, seen[key], prop)
    return seen


def save(fig, name):
    out = L.PAPER / "generated" / "figures" / f"{name}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, metadata={"CreationDate": None, "ModDate": None, "Creator": None, "Producer": None})
    if os.environ.get("CH6_PNG_DIR"):          # optional raster copy for visual checks (not part of the outputs)
        fig.savefig(Path(os.environ["CH6_PNG_DIR"]) / f"{name}.png", dpi=200)
    plt.close(fig)
    return out


def mstyle(key):
    c, m = L.STYLE[key]
    return {"color": c, "marker": m, "markeredgecolor": c, "markerfacecolor": "white" if key in ("static", "aci") else c}


def held_groups():
    """Group table of the held-out period, seed 0 (same source and rules as tab_main)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import make_tables as T
    return T.held_rows()[1]


GR_METH = ["static", "qr_ogd", "mvp_log"]      # common method order (ch6lib.METHODS)
GR_DX = [-0.24, 0.0, 0.24]
GR_SIZE = (TWO_COL, 3.0)


def group_recall(seg, sn):
    G = held_groups()
    G = G[(G.segment == seg) & G.method.isin(GR_METH)].copy()
    name = f"fig_group_recall_{sn}"
    L.write_csv(G[["method", "segment", "dim", "group", "key", "name", "n", "hits", "recall", "lo95", "ub95", "judged"]],
                name, [L.HELD_HITS], "main", f"held-out period, segment {sn}, evaluation seed 0, 25-group definition; "
                "methods static, qr_ogd, mvp_log; 95% Wilson; groups with n < 200 drawn grey and not judged")
    fig, ax = plt.subplots(figsize=GR_SIZE)
    order = G[G.method == "static"][["dim", "group", "name"]].reset_index(drop=True)
    xs, x, ticks, bounds = {}, 0.0, [], []
    prev = None
    for _, r in order.iterrows():
        if prev is not None and r.dim != prev:
            bounds.append(x + 0.25); x += 0.5
        xs[(r.dim, r.group)] = x; ticks.append((x, r["name"])); prev = r.dim; x += 1
    for key, dx in zip(GR_METH, GR_DX):
        g = G[G.method == key]
        st = mstyle(key)
        for judged in (True, False):
            gg = g[g.judged == judged]
            if gg.empty:
                continue
            px = np.array([xs[(d, k)] for d, k in zip(gg.dim, gg.group)]) + dx
            col = st["color"] if judged else GREY
            ax.errorbar(px, gg.recall, yerr=[gg.recall - gg.lo95, gg.ub95 - gg.recall], fmt="none", ecolor=col, elinewidth=0.8, capsize=0)
            ax.plot(px, gg.recall, linestyle="none", marker=st["marker"], color=col, markeredgecolor=col,
                    markerfacecolor=st["markerfacecolor"] if judged else GREY, markersize=3.6,
                    label=L.plain_label(key) if judged else None)
    refline(ax, 0.95)
    refline(ax, 0.94)
    for b in bounds:
        ax.axvline(b, color="#d9d9d9", linewidth=0.6, zorder=0)
    lo = min(0.85, np.floor(G.lo95.min() * 100) / 100)
    ax.set_ylim(lo, 1.0)
    ax.set_xlim(-0.7, x - 0.3)
    ax.set_xticks([t for t, _ in ticks]); ax.set_xticklabels([n for _, n in ticks], rotation=90)
    ax.tick_params(axis="x", length=0)
    starts = [0.0] + [b + 0.25 for b in bounds]; ends = [b - 0.25 for b in bounds] + [x - 1]
    for (d, s0, e0) in zip(order.dim.unique(), starts, ends):
        ax.text((s0 + e0) / 2, 1.0, L.DIM_NAME[d], ha="center", va="bottom", fontsize=7, transform=ax.get_xaxis_transform())
    ax.set_ylabel("Recall (fraction of hops)")
    ax.legend(loc="lower left", frameon=False, ncol=3, handletextpad=0.3, columnspacing=1.0)
    return save(fig, name)


FRONTIER = L.PH + "/frontier_prereg25/frontier.csv"


def fig_frontier():
    F = pd.read_csv(L.REPO / FRONTIER)
    curve = {"static": "static", "citytrac": "citytrac095"}          # target swept: 0.93-0.99 / 0.70-0.99
    point = {"mvp_log": "mvp_log", "qr_ogd": "qr_ogd"}               # target 0.95 only
    keep = F[F.method.isin(curve) | (F.method.isin(point) & (F.target == 0.95))].copy()
    keep["key"] = keep.method.map({**curve, **point})
    keep["kind"] = np.where(keep.method.isin(curve), "curve", "point")
    # 95% Wilson interval of the worst group, single points only (same run as Table 1: tab_main.csv)
    import make_tables as T
    R = T.held_rows()[0].set_index(["method", "segment"])
    for c in ["worst_lo", "worst_ub", "worst_n"]:
        keep[c] = np.nan
    for idx, r in keep[keep.kind == "point"].iterrows():
        t = R.loc[(r.key, r.segment)]
        assert abs(t.worst - r.worst_group_cov) < 1e-12 and t.worst_key == r.worst_group, (r.key, r.segment)
        keep.loc[idx, ["worst_lo", "worst_ub", "worst_n"]] = [t.worst_lo, t.worst_ub, t.worst_n]
    L.write_csv(keep, "fig_frontier", [FRONTIER, L.HELD_HITS], "main",
                "held-out period, single evaluation seed (seed 0); 25-group definition; cost ratio = mean cost / "
                "hindsight-oracle mean cost (primary predictor, same segment); static and CityTrac-style: target swept "
                "(curve, no interval); mvp_log and qr_ogd: target 0.95 (point) with the 95% Wilson interval of the worst "
                "group (worst_lo, worst_ub, worst_n; from the hop-level results, = tab_main); x axis log scale")
    fig, axes = plt.subplots(2, 2, figsize=(TWO_COL, 4.4), sharex=True)
    for j, (seg, sn) in enumerate(L.SEGS):
        for i, (col, bar, ylab) in enumerate([("worst_group_cov", 0.94, "Worst-group recall"),
                                               ("coverage", 0.95, "Mean recall")]):
            ax = axes[i, j]
            for m, key in curve.items():
                d = keep[(keep.method == m) & (keep.segment == seg)].sort_values("cost_over_oracle")
                st = mstyle(key)
                lab = "CityTrac-style\u2020" if m == "citytrac" else L.plain_label(key)
                ax.plot(d.cost_over_oracle, d[col], linestyle="-", label=lab, markersize=3.5, zorder=2, **st)
            for m, key in point.items():
                d = keep[(keep.method == m) & (keep.segment == seg)]
                st = mstyle(key)
                if i == 0:
                    ax.errorbar(d.cost_over_oracle, d[col], yerr=[d[col] - d.worst_lo, d.worst_ub - d[col]], fmt="none",
                                ecolor=st["color"], elinewidth=0.9, capsize=2, capthick=0.9, zorder=3)
                ax.plot(d.cost_over_oracle, d[col], linestyle="none", label=L.plain_label(key),
                        markersize=7 if key == "mvp_log" else 5, zorder=4, **st)
            refline(ax, bar)
            ax.set_xscale("log")
            ax.set_xticks([0.6, 1, 2, 3, 5, 8]); ax.set_xticklabels(["0.6", "1", "2", "3", "5", "8"])
            ax.minorticks_off()
            if i == 0:
                ax.set_title(f"Segment {sn}")
            if i == 1:
                ax.set_xlabel("Cost ratio (mean cost / hindsight-oracle cost)")
            if j == 0:
                ax.set_ylabel(f"{ylab} (fraction)")
    axes[0, 0].legend(loc="lower right", frameon=False)
    fig.tight_layout()
    check_reflines(fig)
    return save(fig, "fig_frontier")


TS_SEEDS = [1, 2, 3, 4, 7]
TS_METH = [("static", "static"), ("aci_g0005", "aci"), ("qr_ogd", "qr_ogd"), ("mvp_log", "mvp_log")]
TS_PRED = [("src_zone_hour_speed", "Base predictor"), ("src_zone_hour_speed_oa", "Outage-aware predictor")]
OUTAGE_START = "2014-06-21"          # run_meta.csv start (local date; = start of B_early, 2014-06-20 23:00 UTC)
PRE_H = 48
ROWS = {"recall": (6, None), "worst": (24, 200), "cost": (24, None)}    # bin width (h), min hops per group
TS_SIZE = (TWO_COL, 6.0)
NONE_SUMMARY = L.PH + "/outage_suite/none_s7/summary.csv"


def none_oracle_cost():
    """Mean cost of the hindsight oracle (base predictor) in the no-outage run, per segment. Bins never straddle
    a segment boundary (edges at multiples of 6 h from the outage start; B_early ends at +48 h)."""
    S = pd.read_csv(L.REPO / NONE_SUMMARY)
    S = S[(S.predictor == L.PRED) & (S.method == "oracle(post-hoc)")]
    return S.set_index("segment")["cost_mean_cam_s"].to_dict()


def ts_bins(H, t0, cols, width, min_n, oracle):
    """Per bin: mean recall, worst-group recall (25 groups with >= min_n hops in the bin), cost / no-outage oracle."""
    h = (H.t_exit.to_numpy() - t0) / 3600.0
    keep = h >= -PRE_H
    H = H.loc[keep].copy()
    H["bin"] = np.floor(h[keep] / width).astype(int) * width
    seg = H.groupby("bin").segment.agg(lambda x: x.iloc[0] if x.nunique() == 1 else "MIXED")
    assert (seg != "MIXED").all()
    out = []
    for hitc, costc, tag in cols:
        g = H.groupby("bin")
        r = pd.DataFrame({"tag": tag, "bin_start_h": g.size().index, "n": g.size().values,
                          "recall": g[hitc].mean().values, "segment": seg.values})
        r["cost_ratio_none"] = g[costc].mean().values / r.segment.map(oracle).values
        if min_n:
            parts = []
            for d in L.DIMS25:
                gg = H.groupby(["bin", d])[hitc].agg(["mean", "size"])
                parts.append(gg[gg["size"] >= min_n]["mean"].groupby(level=0).min())
            r["worst"] = pd.concat(parts, axis=1).min(axis=1).reindex(r.bin_start_h).values
        out.append(r)
    return pd.concat(out, ignore_index=True)


def fig_outage_timeseries():
    t0 = (pd.Timestamp(OUTAGE_START, tz="Europe/Lisbon").tz_convert("UTC")).timestamp()
    orc = none_oracle_cost()
    frames, srcs = {k: [] for k in ROWS}, [NONE_SUMMARY]
    for sd in TS_SEEDS + ["none"]:
        f = f"{L.PH}/outage_suite/{'none_s7' if sd == 'none' else f'rand10_s{sd}'}/hits.parquet"
        srcs.append(f)
        H = pd.read_parquet(L.REPO / f)
        preds = TS_PRED if sd != "none" else TS_PRED[:1]
        cols = [(f"hit|{p}|{m}", f"cost|{p}|{m}", f"{p}|{k}") for p, _ in preds for m, k in TS_METH]
        for row, (w, mn) in ROWS.items():
            if row == "cost" and w == ROWS["worst"][0]:
                continue                                    # same 24-h bins as the worst-group row
            B = ts_bins(H, t0, cols, w, mn, orc)
            B["site_seed"] = sd
            frames[row].append(B)
    aggs = []
    for row, (w, mn) in ROWS.items():
        if row == "cost":
            continue
        D = pd.concat(frames[row], ignore_index=True)
        D[["predictor", "method"]] = D.tag.str.split("|", expand=True)
        out = D[D.site_seed != "none"]
        metrics = ["recall"] if row == "recall" else ["worst", "cost_ratio_none"]
        spec = {f"{m}_{s}": (m, s) for m in metrics for s in ["mean", "min", "max"]}
        A = out.groupby(["predictor", "method", "bin_start_h", "segment"]).agg(**spec, n_mean=("n", "mean"), seeds=("n", "size")).reset_index()
        ref = D[D.site_seed == "none"][["method", "bin_start_h"] + metrics].rename(columns={m: f"{m}_no_outage" for m in metrics})
        A = A.merge(ref, on=["method", "bin_start_h"], how="left")
        A.insert(0, "bin_h", w)
        aggs.append(A)
    agg = pd.concat(aggs, ignore_index=True)
    L.write_csv(agg, "fig_outage_timeseries", srcs, "additional",
                f"held-out period, random 10% outage, site seeds {TS_SEEDS}, evaluation seed 0; outage start {OUTAGE_START} "
                "00:00 local (start of B_early); from -48 h to the end of B. Rows with bin_h = 6: mean recall; bin_h = 24 "
                "(local calendar days): worst group = lowest recall among the 25 groups with >= 200 hops in the bin, and cost ratio. *_mean/min/max over "
                "site seeds. cost_ratio_none = bin mean cost / mean cost of the hindsight oracle (base predictor) of the "
                f"no-outage run in the same segment (test_jun_a {orc['test_jun_a']:.1f}, B_early {orc['B_early']:.1f}, "
                f"B_late {orc['B_late']:.1f} camera-s per hop; the oracle's per-hop cost is not stored, so a per-bin oracle is "
                "not available). *_no_outage = no-outage run (none_s7, base predictor), for the pre-outage check")
    fig, axes = plt.subplots(3, 2, figsize=TS_SIZE, sharex=True, sharey="row")
    rows = [("recall", 6, "Mean recall (fraction)", False), ("worst", 24, "Worst-group recall (fraction)", False),
            ("cost_ratio_none", 24, "Cost ratio (vs. no-outage oracle)", True)]
    for j, (pred, ptitle) in enumerate(TS_PRED):
        for i, (col, w, ylab, logy) in enumerate(rows):
            ax = axes[i, j]
            for _, key in TS_METH:
                d = agg[(agg.bin_h == w) & (agg.predictor == pred) & (agg.method == key)].sort_values("bin_start_h")
                x = d.bin_start_h + w / 2
                st = mstyle(key)
                ax.fill_between(x, d[f"{col}_min"], d[f"{col}_max"], color=st["color"], alpha=0.18, linewidth=0)
                ax.plot(x, d[f"{col}_mean"], linestyle="-", markersize=2.5, markevery=4 if w == 6 else 1,
                        label=L.plain_label(key), **st)
            ax.axvline(0, color="#555555", linewidth=0.8, linestyle=(0, (1, 1.5)))
            if logy:
                ax.set_yscale("log")
                ax.axhline(1.0, color="#9a9a9a", linewidth=0.6, linestyle="-", zorder=1)
                ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([0.5, 1, 2, 5, 10, 20, 50, 100]))
                ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
                ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            else:
                refline(ax, 0.95)
            if i == 0:
                ax.set_title(ptitle)
            if i == len(rows) - 1:
                ax.set_xlabel("Time since outage start (h)")
            if j == 0:
                ax.set_ylabel(ylab)
            ax.set_xticks(range(-48, 241, 48))
    axes[0, 0].legend(loc="lower left", frameon=False, ncol=2)
    fig.tight_layout()
    check_reflines(fig)
    return save(fig, "fig_outage_timeseries")


FIGURES = {"fig_group_recall_B": lambda: group_recall("test_jun_b", "B"),
           "fig_group_recall_A": lambda: group_recall("test_jun_a", "A"),
           "fig_frontier": fig_frontier, "fig_outage_timeseries": fig_outage_timeseries}


def main():
    only = sys.argv[1:] or list(FIGURES)
    for name in only:
        FIGURES[name]()
        print("figure:", name)


if __name__ == "__main__":
    main()
