import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_BASE = {"fixed": ("k", ":"), "static": ("tab:blue", "-"), "mondrian_hour": ("tab:green", "-")}
_CYCLE = ["tab:red", "tab:purple", "tab:orange", "tab:brown", "tab:pink", "tab:olive", "tab:cyan", "tab:gray"]


def _style(m, _cache={}):
    if m in _BASE:
        return _BASE[m]
    if m not in _cache:
        _cache[m] = (_CYCLE[len(_cache) % len(_CYCLE)], "-")
    return _cache[m]


def _keep(m, methods):
    return methods is None or m in methods or m == "fixed"


def rolling(tr_test, hit_store, seg_of, alpha, window, out_dir, methods=None):
    t = pd.to_datetime(tr_test["t_exit"], unit="s")
    preds = sorted({p for p, _ in hit_store if p != "spatula_rule"})
    fig, axes = plt.subplots(len(preds), 1, figsize=(11, 3.2 * len(preds)), sharex=True, squeeze=False)
    seg_change = [t[seg_of == s].min() for s in pd.unique(seg_of)][1:]
    for ax, p in zip(axes[:, 0], preds):
        for (pp, m), (hit, _) in hit_store.items():
            if pp not in (p, "spatula_rule") or not _keep(m, methods):
                continue
            col, ls = _style(m)
            r = pd.Series(hit.astype(float)).rolling(window, min_periods=window // 2).mean()
            ax.plot(t, r, color=col, ls=ls, lw=1.0, label=("spatula_rule" if pp == "spatula_rule" else m))
        ax.axhline(1 - alpha, color="gray", lw=1, ls="--")
        for x in seg_change:
            ax.axvline(x, color="orange", lw=1.5)
        ax.set_ylabel("rolling hop recall"); ax.set_title(f"predictor = {p}")
        ax.set_ylim(max(0.0, 1 - 6 * alpha), 1.0)
        ax.legend(loc="lower left", fontsize=7, ncol=6)
    fig.tight_layout(); fig.savefig(out_dir / "rolling_coverage.png", dpi=130); plt.close(fig)


def custody(cust, alpha, out_dir, methods=None):
    if cust.empty:
        return
    for seg in cust["segment"].unique():
        d = cust[cust["segment"] == seg]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for (p, m), g in d.groupby(["predictor", "method"]):
            if not _keep(m, methods):
                continue
            col, ls = _style(m)
            mk = {"src": "o", "src_zone": "s"}.get(p, "^")
            ax.plot(g["hops"], g["custody"], color=col, ls=ls, marker=mk, ms=3, lw=1, label=f"{p}/{m}")
        h = np.arange(1, d["hops"].max() + 1)
        ax.plot(h, (1 - alpha) ** h, color="gray", ls="--", lw=1, label="(1-alpha)^h")
        ax.set_xlabel("hops"); ax.set_ylabel("P(no miss in first h hops)")
        ax.set_title(f"custody vs chain length [{seg}]"); ax.legend(fontsize=6, ncol=2)
        fig.tight_layout(); fig.savefig(out_dir / f"custody_{seg}.png", dpi=130); plt.close(fig)


def alpha_trace(tr_test, traces, alpha, out_dir):
    t = pd.to_datetime(tr_test["t_exit"], unit="s")
    preds = sorted({p for p, _ in traces})
    fig, axes = plt.subplots(len(preds), 1, figsize=(11, 2.6 * len(preds)), sharex=True, squeeze=False)
    for ax, p in zip(axes[:, 0], preds):
        for (pp, v), a in traces.items():
            if pp == p:
                ax.plot(t, a, lw=0.6, label=v, color=_style(v)[0])
        ax.axhline(alpha, color="gray", ls="--"); ax.axhline(0, color="k", lw=0.5)
        ax.set_ylabel("alpha_t"); ax.set_title(f"ACI alpha_t [{p}]", fontsize=9); ax.legend(fontsize=7, ncol=4)
    fig.tight_layout(); fig.savefig(out_dir / "aci_alpha_trace.png", dpi=130); plt.close(fig)


def conditional(cond, alpha, out_dir, methods=None):
    for pred in cond["predictor"].unique():
        d = cond[(cond["predictor"] == pred) & cond["method"].map(lambda m: _keep(m, methods))]
        if d.empty:
            continue
        dims = list(d["dim"].unique()); segs = list(d["segment"].unique())
        fig, axes = plt.subplots(len(segs), len(dims), figsize=(3.4 * len(dims), 3.0 * len(segs)),
                                 squeeze=False, sharey=True)
        for i, seg in enumerate(segs):
            for j, dim in enumerate(dims):
                ax = axes[i, j]
                dd = d[(d["segment"] == seg) & (d["dim"] == dim)]
                meths = list(dd["method"].unique()); groups = sorted(dd["group"].unique())
                w = 0.8 / max(1, len(meths))
                for k, m in enumerate(meths):
                    y = [dd[(dd["method"] == m) & (dd["group"] == g)]["coverage"].mean() for g in groups]
                    ax.bar(np.arange(len(groups)) + k * w, y, w, color=_style(m)[0], label=m)
                ax.axhline(1 - alpha, color="gray", ls="--", lw=1)
                ax.set_xticks(np.arange(len(groups)) + 0.4 - w / 2); ax.set_xticklabels(groups, fontsize=7)
                ax.set_ylim(1 - 4 * alpha, 1.0); ax.set_title(f"{seg} / {dim}", fontsize=8)
        axes[0, 0].legend(fontsize=6)
        fig.tight_layout(); fig.savefig(out_dir / f"conditional_{pred}.png", dpi=130); plt.close(fig)


def frontier(vm, s_test, kid, seg_of, delta, alpha, pname, hit_store, path):
    qs = np.unique(np.quantile(s_test[s_test > 0], np.linspace(0, 0.5, 60))) if (s_test > 0).any() else [1e-6]
    uk, inv = np.unique(kid, return_inverse=True)
    tab = vm.cost_table(uk, qs, delta)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for seg, col in zip(pd.unique(seg_of), ["tab:blue", "tab:orange", "tab:green", "tab:red"]):
        m = seg_of == seg
        cov = [(s_test[m] >= q).mean() for q in qs]
        ax.plot(tab[inv[m]].mean(axis=0), cov, color=col, lw=1.5, label=f"{pname} frontier [{seg}]")
        for (pp, meth), (hit, c) in hit_store.items():
            mk = "x" if meth == "fixed" else ("o" if meth == "static" else ("s" if meth.startswith("mondrian") else "^"))
            ax.scatter(c[m].mean(), hit[m].mean(), color=col, marker=mk, s=22, zorder=3)
    ax.axhline(1 - alpha, color="gray", ls="--", lw=1)
    ax.set_xlabel("mean camera-seconds per hop"); ax.set_ylabel("hop recall")
    ax.set_title("frontier (x spatula, o static, s mondrian*, ^ aci*)", fontsize=8)
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
