"""confirm2 figures F1-F3 (plan §7) from the CSV files of confirm2_analysis.py.

    python confirm2_figures.py --analysis results/precheck_confirm2/trial_expl1/analysis --out <dir> [--label "..."]

F1  per method, recall against target (0.90-0.98); the 25 groups in light grey, re-acquired and isolation Q4 coloured
    with 95% bands (conservative over taxi / day clusters), all hops with a band; dotted line: reachable upper bound
    U_G of the two coloured groups (if reachable_bound.csv exists) when it lies inside the y range; otherwise the axis
    is not widened and the caption says "reachable upper bound of the highlighted groups: all >= [value]" (rev 72);
    diagonal y = x; same axes in every panel.
F2  cost curve: mean camera-seconds per hop (x) against worst-group recall t - D(t) (y), one line per method through
    its five targets, 95% cross bars (conservative). Panel A: static, ACI, CityTrac-style, H1, Spatula-style (point);
    panel B: Mondrian, qr_groups, qr_groups_refit, qr_groups_refit7, qr_ogd, mvp_log, H3, H4 (+ static faint).
    Same axis ranges in both panels. Logarithmic x axis (plan §7, rev 72).
F3  worst-group deficit D(t) with 95% intervals against target; proposed methods and the main comparators; zero line.
Per-block versions of F1 and F2 are written when the analysis has block scopes. No 0.94 / 1.20 reference lines.
"""
import argparse
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 6.5, "lines.linewidth": 1.0, "lines.markersize": 3.5, "axes.linewidth": 0.6,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "axes.spines.top": False, "axes.spines.right": False})
OK = {"black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442",
      "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "grey": "#7f7f7f", "brown": "#8c564b"}
STY = {"static": (OK["orange"], "o", "static"), "aci_g0005": (OK["sky"], "s", "ACI"),
       "mondrian_hour_hop_speed": (OK["purple"], "D", "Mondrian"), "qr_groups": (OK["purple"], "P", "qr_groups"),
       "qr_groups_refit": (OK["green"], "v", "qr_groups_refit"), "qr_groups_refit7": (OK["brown"], "<", "qr_groups_refit7"),
       "qr_ogd": (OK["vermillion"], ">", "qr_ogd"), "mvp_log": (OK["blue"], "*", "mvp_log"),
       "citytrac_nominal": (OK["green"], "^", "CityTrac-style"), "spatula_rule|fixed": (OK["yellow"], "x", "Spatula-style"),
       "H1": (OK["black"], "1", "H1"), "H3": (OK["black"], "2", "H3"), "H4": (OK["grey"], "3", "H4")}
F1_METHODS = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit", "qr_groups_refit7",
              "qr_ogd", "mvp_log", "citytrac_nominal"]
F2A = ["static", "aci_g0005", "citytrac_nominal", "H1", "spatula_rule|fixed"]
F2B = ["mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit", "qr_groups_refit7", "qr_ogd", "mvp_log", "H3", "H4"]
F3_METHODS = ["mvp_log", "qr_ogd", "static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit", "qr_groups_refit7"]
KEY = {"reacquired": ("hopkind=2", OK["vermillion"], "re-acquired"), "isoq4": ("nn_bin=3", OK["blue"], "isolation Q4"),
       "all": ("grp_all=0", OK["black"], "all hops")}


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, metadata={"CreationDate": None, "ModDate": None, "Creator": None, "Producer": None})
    fig.savefig(path.with_suffix(".png"), dpi=200)
    plt.close(fig)
    return path


def f1(an, scope, out, label):
    GR = pd.read_csv(an / "group_recall.csv"); DEF = pd.read_csv(an / "deficits.csv")
    GR = GR[GR.scope == scope]; DEF = DEF[DEF.scope == scope]
    U = pd.read_csv(an / "reachable_bound.csv") if (an / "reachable_bound.csv").exists() else None
    if U is not None:
        U = U[U.scope == scope].set_index("group").U_G
    note = ""
    gm = GR.groupby(["method", "target", "group"], as_index=False).recall.mean()
    targets = sorted(gm.target.unique())
    lo_ = min(gm.recall.min(), min(targets)) - 0.01; hi_ = max(gm.recall.max(), max(targets)) + 0.005
    # plan §7 (rev 72): if a highlighted group's reachable bound exceeds the y maximum, the axis is not widened; the
    # caption states "the reachable bounds of the highlighted groups are all >= [value]" instead of the dotted lines
    ub = None if U is None else {k: float(U[KEY[k][0]]) for k in ("reacquired", "isoq4")}
    draw_ub = ub is not None and all(v <= hi_ for v in ub.values())
    if ub is not None and not draw_ub:
        note = f"reachable upper bound of the highlighted groups: all >= {np.floor(min(ub.values()) * 1e4) / 1e4:.4f}"
    fig, axes = plt.subplots(3, 3, figsize=(7.16, 6.6), sharex=True, sharey=True)
    for ax, m in zip(axes.ravel(), F1_METHODS):
        g = gm[gm.method == m]
        for grp, x in g.groupby("group"):
            ax.plot(x.target, x.recall, color="#c8c8c8", lw=0.6, zorder=1)
        for k, (cell, col, lab) in KEY.items():
            d = DEF[(DEF.method == m) & (DEF.cell == cell)].sort_values("target")
            ax.fill_between(d.target, d.target - d.hi, d.target - d.lo, color=col, alpha=0.18, lw=0, zorder=2)
            ax.plot(d.target, d.recall, color=col, lw=1.1, marker="o", ms=2.5, zorder=3, label=lab)
            if draw_ub and k != "all":
                ax.axhline(U[cell], color=col, lw=0.8, ls=":", zorder=2)
        ax.plot([lo_, hi_], [lo_, hi_], color="black", lw=0.6, ls="--", zorder=0)
        ax.set_title(STY[m][2]); ax.set_xlim(min(targets) - 0.005, max(targets) + 0.005); ax.set_ylim(lo_, hi_)
        ax.set_xticks(targets)
    for ax in axes[-1]:
        ax.set_xlabel("target recall")
    for ax in axes[:, 0]:
        ax.set_ylabel("recall")
    axes[0, 0].legend(loc="lower right", frameon=False)
    cap = (f"F1 group calibration curves ({label}, {scope}); grey: 25 groups; band: 95% interval; "
           + ("dotted: reachable bound" if draw_ub else note))
    fig.suptitle(cap, fontsize=7)
    (out / f"F1_{scope}_caption.txt").parent.mkdir(parents=True, exist_ok=True)
    (out / f"F1_{scope}_caption.txt").write_text(cap + "\n")
    return save(fig, out / f"F1_{scope}.pdf")


def f2(an, scope, out, label, log):
    PT = pd.read_csv(an / "method_points.csv"); PT = PT[PT.scope == scope]
    xs = pd.concat([PT.cost_lo, PT.cost_hi]); ys = pd.concat([PT.worst_lo, PT.worst_hi])
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.2), sharex=True, sharey=True)
    for ax, ms, ttl in [(axes[0], F2A, "A: average-target methods"), (axes[1], F2B, "B: group-aware methods")]:
        if ax is axes[1]:
            st = PT[PT.method == "static"].sort_values("target")
            ax.plot(st.cost_mean, st.worst_recall, color=STY["static"][0], alpha=0.3, lw=0.8)
        for m in ms:
            p = PT[PT.method == m].sort_values("target")
            if p.empty:
                continue
            c, mk, lab = STY[m]
            if m == "spatula_rule|fixed":
                p = p.iloc[[0]]
            # a point can lie outside its percentile interval (maximum over groups); bars are then drawn from the point
            ax.errorbar(p.cost_mean, p.worst_recall, xerr=np.clip([p.cost_mean - p.cost_lo, p.cost_hi - p.cost_mean], 0, None),
                        yerr=np.clip([p.worst_recall - p.worst_lo, p.worst_hi - p.worst_recall], 0, None), color=c, marker=mk, ms=3.5,
                        lw=0.9 if len(p) > 1 else 0, elinewidth=0.5, capsize=0, label=lab, ls="-" if len(p) > 1 else "none")
        ax.set_title(ttl); ax.set_xlabel("mean camera-seconds per hop" + (" (log)" if log else ""))
        if log:
            ax.set_xscale("log")
            ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator([50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]))
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
            ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.legend(loc="lower right", frameon=False)
    axes[0].set_ylabel("worst-group recall t - D(t)")
    pad = 0.02 * (xs.max() - xs.min())
    axes[0].set_xlim(xs.min() - pad if not log else xs.min() * 0.95, xs.max() + pad if not log else xs.max() * 1.05)
    axes[0].set_ylim(ys.min() - 0.005, ys.max() + 0.005)
    fig.suptitle(f"F2 cost curves ({label}, {scope}); lines join the targets; bars: 95% intervals", fontsize=7)
    return save(fig, out / f"F2_{scope}_{'log' if log else 'linear'}.pdf")


def f3(an, scope, out, label):
    D = pd.read_csv(an / "deficits.csv"); D = D[(D.scope == scope) & (D.cell == "WORST")]
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    ts = sorted(D.target.unique()); dx = np.linspace(-0.0025, 0.0025, len(F3_METHODS))
    for j, m in enumerate(F3_METHODS):
        p = D[D.method == m].sort_values("target")
        c, mk, lab = STY[m]
        ax.errorbar(p.target + dx[j], p.deficit, yerr=np.clip([p.deficit - p.lo, p.hi - p.deficit], 0, None), color=c, marker=mk, ms=3,
                    lw=0.8, elinewidth=0.5, capsize=0, label=lab)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xticks(ts); ax.set_xlabel("target recall"); ax.set_ylabel("worst-group deficit D(t)")
    ax.legend(fontsize=5.5, frameon=False, ncol=2)
    ax.set_title(f"F3 ({label}, {scope}); bars: 95% intervals", fontsize=7)
    return save(fig, out / f"F3_{scope}.pdf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True); ap.add_argument("--out", required=True); ap.add_argument("--label", default="")
    a = ap.parse_args()
    an, out = Path(a.analysis), Path(a.out)
    scopes = sorted(pd.read_csv(an / "deficits.csv").scope.unique(), key=lambda s: (s != "combined", s))
    made = []
    for sc in scopes:
        made += [f1(an, sc, out, a.label), f2(an, sc, out, a.label, True)]      # F2: logarithmic x axis (plan §7, rev 72)
    made.append(f3(an, "combined", out, a.label))
    for p in made:
        print(p)


if __name__ == "__main__":
    main()
