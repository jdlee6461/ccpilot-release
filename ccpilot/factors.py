"""Factor analysis: which hop-level conditions are associated with misses?

Outcome
  miss_static : miss under a single global threshold (split conformal) for the
                chosen predictor  -> "where does marginal calibration fail?"
  miss_qr     : miss under group-conditional QR on the CURRENT groups
                (hgroup, hopkind, speed_bin, zone) -> "what is still left after
                calibrating the groups we already know about?"

Factors (computed per transition; continuous ones binned by TRAINING quantiles)
  existing : hgroup, hopkind, speed_bin, zone
  in-camera: dwell_bin (time inside source camera), turn (heading change inside
             the source camera: straight / turn / u-turn / unknown)
  spatial  : center_bin (distance of source camera from camera centroid),
             density_bin (#cameras within 1 km), nn_bin (nearest-camera distance),
             entropy_bin (entropy of the source camera's next-camera distribution
             in training = how 'branchy' the source is)
  trip     : daytype (weekday/weekend), elapsed_bin (time since trip start),
             prevratio (previous hop's delay / training median delay for that
             camera pair: fast / normal / slow / none)

Analyses
  1. univariate miss rate per level with Wilson 95% CI
  2. multivariable logistic regression (statsmodels); odds ratios vs the most common level
     of each factor; levels with n<200 or no/all misses are merged into that level
  3. shallow decision tree (sklearn) -> leaves with the highest miss rates
  4. delay spread by exit-speed bin (tests the 'slow exit -> less predictable' story)

These are ASSOCIATIONS on exploratory periods, not causal effects.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import static_taus
from .evaluate import _period_mask, _add_strata
from .multigroup import qr_group_taus
from .predictors import VisibilityModel, candidate_sets, _truth_by_tr

CURRENT_DIMS = ["hgroup", "hopkind", "speed_bin", "zone"]


# ------------------------------------------------------------------ helpers
def interp_xy(traj, q_trip, q_t):
    """Linear interpolation of (x, y) for queries (trip, t). traj sorted by trip, t."""
    tr = traj["trip_id"].to_numpy().astype(np.int64)
    t = traj["t"].to_numpy(); x = traj["x"].to_numpy(); y = traj["y"].to_numpy()
    tmin = t.min()
    key = tr * (1 << 40) + np.round((t - tmin) * 10).astype(np.int64)
    qk = q_trip.astype(np.int64) * (1 << 40) + np.round((q_t - tmin) * 10).astype(np.int64)
    n = len(t)
    idx = np.searchsorted(key, qk, side="right")
    lo = np.clip(idx - 1, 0, n - 1); hi = np.clip(idx, 0, n - 1)
    lo_ok = tr[lo] == q_trip; hi_ok = tr[hi] == q_trip
    lo = np.where(lo_ok, lo, hi); hi = np.where(hi_ok, hi, lo)
    dt = t[hi] - t[lo]
    w = np.where(dt > 0, np.clip((q_t - t[lo]) / np.where(dt > 0, dt, 1), 0, 1), 0.0)
    return x[lo] + w * (x[hi] - x[lo]), y[lo] + w * (y[hi] - y[lo])


def _qbins(values, ref, k=4):
    edges = np.unique(np.nanquantile(ref, np.linspace(0, 1, k + 1)[1:-1]))
    b = np.digitize(values, edges).astype(float)
    b[np.isnan(values)] = np.nan
    return b


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


# ------------------------------------------------------------------ features
def build_features(trans, sight, traj, cams, tr_train_mask, h=4.0):
    df = trans.copy()
    # dwell: join source sighting
    s = sight[["trip_id", "cam", "t_in", "t_out"]].rename(columns={"cam": "src", "t_out": "t_exit"})
    df = df.merge(s, on=["trip_id", "src", "t_exit"], how="left")
    df["dwell"] = df["t_exit"] - df["t_in"]
    # heading change inside the source camera
    trips = df["trip_id"].to_numpy()
    hi = np.minimum(h, np.maximum(df["dwell"].fillna(0).to_numpy(), 0))
    t_in = df["t_in"].to_numpy(); t_out = df["t_exit"].to_numpy()
    x0, y0 = interp_xy(traj, trips, t_in)
    x1, y1 = interp_xy(traj, trips, t_in + hi)
    x2, y2 = interp_xy(traj, trips, t_out - hi)
    x3, y3 = interp_xy(traj, trips, t_out)
    a_in = np.arctan2(y1 - y0, x1 - x0); a_out = np.arctan2(y3 - y2, x3 - x2)
    moved = (np.hypot(x1 - x0, y1 - y0) > 2) & (np.hypot(x3 - x2, y3 - y2) > 2)
    dang = np.abs((a_out - a_in + np.pi) % (2 * np.pi) - np.pi)
    turn = np.where(~moved | np.isnan(t_in), 3, np.where(dang < np.radians(30), 0,
                    np.where(dang < np.radians(120), 1, 2)))
    df["turn"] = turn  # 0 straight, 1 turn, 2 u-turn, 3 unknown
    # trip elapsed time
    tstart = traj.groupby("trip_id")["t"].min()
    df["elapsed"] = df["t_exit"] - df["trip_id"].map(tstart).to_numpy()
    # camera-level spatial features
    xy = cams[["x", "y"]].to_numpy()
    c = xy.mean(axis=0)
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    cam_center = np.hypot(xy[:, 0] - c[0], xy[:, 1] - c[1])
    cam_density = (d <= 1000).sum(axis=1)
    cam_nn = d.min(axis=1)
    src = df["src"].to_numpy()
    df["center_d"] = cam_center[src]; df["density"] = cam_density[src]; df["nn_d"] = cam_nn[src]
    # next-camera entropy of the source (training)
    trn = trans[tr_train_mask & ~trans["is_exit"].to_numpy()]
    p = trn.groupby(["src", "first_cam"]).size()
    p = p / p.groupby(level=0).transform("sum")
    ent = (-(p * np.log(p))).groupby(level=0).sum()
    df["entropy"] = df["src"].map(ent).to_numpy()
    # previous hop delay ratio (within trip & chain)
    df["delay"] = df["t_arrive"] - df["t_exit"]
    med = trn.assign(delay=trn["t_arrive"] - trn["t_exit"]).groupby(["src", "first_cam"])["delay"].median()
    df = df.sort_values(["trip_id", "chain", "hop"])
    prev = df.groupby(["trip_id", "chain"])[["src", "first_cam", "delay"]].shift(1)
    key = pd.MultiIndex.from_arrays([prev["src"].fillna(-1).astype(int), prev["first_cam"].fillna(-1).astype(int)])
    exp = med.reindex(key).to_numpy()
    ratio = prev["delay"].to_numpy() / exp
    df["prevratio"] = np.where(np.isnan(ratio), 3, np.where(ratio < 0.8, 0, np.where(ratio <= 1.25, 1, 2)))
    df["daytype"] = (df["dow"] >= 5).astype(int)
    df = df.sort_values("tr_id").reset_index(drop=True)
    # bins from training quantiles
    m_tr = df["tr_id"].isin(trans.loc[tr_train_mask, "tr_id"]).to_numpy()
    for col, name in [("dwell", "dwell_bin"), ("center_d", "center_bin"), ("density", "density_bin"),
                      ("nn_d", "nn_bin"), ("entropy", "entropy_bin"), ("elapsed", "elapsed_bin")]:
        df[name] = _qbins(df[col].to_numpy(dtype=float), df.loc[m_tr, col].to_numpy(dtype=float))
    return df


FACTORS = ["hgroup", "hopkind", "speed_bin", "zone", "turn", "dwell_bin", "center_bin",
           "density_bin", "nn_bin", "entropy_bin", "daytype", "elapsed_bin", "prevratio"]
LABELS = {
    "turn": {0: "straight", 1: "turn", 2: "u-turn", 3: "unknown"},
    "prevratio": {0: "prev fast", 1: "prev normal", 2: "prev slow", 3: "no prev"},
    "daytype": {0: "weekday", 1: "weekend"},
    "hopkind": {0: "later", 1: "first(trip)", 2: "first(resume)"},
}


# ------------------------------------------------------------------ analyses
def univariate(df, outcome):
    overall = df[outcome].mean()
    rows = []
    for f in FACTORS:
        for lv, g in df.groupby(f, dropna=False):
            n = len(g); k = int(g[outcome].sum())
            if n == 0:
                continue
            lo, hi = wilson(k, n)
            rows.append({"factor": f, "level": LABELS.get(f, {}).get(lv, lv), "n": n,
                         "share": n / len(df), "miss_rate": k / n, "ci_lo": lo, "ci_hi": hi,
                         "ratio_to_overall": (k / n) / overall if overall > 0 else np.nan})
    out = pd.DataFrame(rows)
    # spread = max-min miss rate across levels with n >= 500 -> factor importance proxy
    sp = (out[out["n"] >= 500].groupby("factor")["miss_rate"].agg(lambda s: s.max() - s.min())
          .rename("spread").sort_values(ascending=False))
    return out, sp, overall


def logit(df, outcome, max_n=300_000, seed=0):
    import statsmodels.formula.api as smf
    d = df.dropna(subset=FACTORS)
    if len(d) > max_n:
        d = d.sample(max_n, random_state=seed)
    d = d.copy()
    for f in FACTORS:
        d[f] = d[f].astype(int)
    # 'no previous hop' (prevratio=3) is identical to hopkind != 0 -> perfectly collinear.
    # In the regression, first hops get the reference level; their effect is carried by hopkind.
    d.loc[d["prevratio"] == 3, "prevratio"] = 1
    # merge sparse or perfectly separated levels into the most common level (avoids
    # non-convergence); drop factors left with a single level
    use = []
    for f in FACTORS:
        vc = d[f].value_counts()
        mode = vc.index[0]
        rate = d.groupby(f)[outcome].mean()
        bad = [lv for lv in vc.index if vc[lv] < 200 or rate[lv] in (0.0, 1.0)]
        d.loc[d[f].isin(bad), f] = mode
        if d[f].nunique() > 1:
            use.append(f)
    formula = f"{outcome} ~ " + " + ".join(f"C({f}, Treatment(reference={int(d[f].value_counts().index[0])}))"
                                           for f in use)
    m = smf.logit(formula, data=d).fit(disp=False, maxiter=300, method="newton")
    if not m.mle_retvals.get("converged", True):
        print(f"[factors] WARNING: logit for {outcome} did not converge; interpret odds ratios with care")
    ci = m.conf_int()
    res = pd.DataFrame({"odds_ratio": np.exp(m.params), "or_lo": np.exp(ci[0]), "or_hi": np.exp(ci[1]),
                        "p_value": m.pvalues})
    return res.drop(index="Intercept"), len(d)


def tree(df, outcome, max_depth=4, min_leaf_frac=0.005, seed=0):
    from sklearn.tree import DecisionTreeClassifier, export_text
    d = df.dropna(subset=FACTORS)
    X = pd.get_dummies(d[FACTORS].astype(int).astype(str), prefix=FACTORS)
    y = d[outcome].to_numpy()
    clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=max(500, int(min_leaf_frac * len(d))),
                                 random_state=seed).fit(X, y)
    txt = export_text(clf, feature_names=list(X.columns), show_weights=False, decimals=2)
    leaf = clf.apply(X)
    L = pd.DataFrame({"leaf": leaf, "y": y}).groupby("leaf")["y"].agg(["size", "mean"])
    # human-readable path per leaf
    tr = clf.tree_; paths = {}
    def walk(node, conds):
        if tr.children_left[node] == -1:
            paths[node] = " AND ".join(conds) if conds else "(all)"
            return
        name = X.columns[tr.feature[node]]
        walk(tr.children_left[node], conds + [f"NOT {name}"])
        walk(tr.children_right[node], conds + [name])
    walk(0, [])
    L["path"] = [paths[i] for i in L.index]
    L = L.rename(columns={"size": "n", "mean": "miss_rate"}).sort_values("miss_rate", ascending=False)
    return txt, L


def delay_by_speed(df):
    d = df[~df["is_exit"]]
    g = d.groupby("speed_bin")["delay"]
    out = pd.DataFrame({"n": g.size(), "delay_p10": g.quantile(0.1), "delay_median": g.median(),
                        "delay_p90": g.quantile(0.9)})
    out["p90_minus_p10"] = out["delay_p90"] - out["delay_p10"]
    ex = df.groupby("speed_bin")["is_exit"].mean().rename("exit_rate")
    same = d.assign(same=d["first_cam"] == d["src"]).groupby("speed_bin")["same"].mean().rename("return_same_cam")
    return out.join(ex).join(same)


# ------------------------------------------------------------------ driver
def run(cfg, predictor, work, out_dir, max_logit_n=300_000):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    tz = cfg["timezone"]; ex = cfg["eval"]; ev = cfg["events"]
    trans = pd.read_parquet(work / "transitions.parquet")
    truth = pd.read_parquet(work / "truth.parquet")
    sight = pd.read_parquet(work / "sightings.parquet")
    traj = pd.read_parquet(work / "trajectories.parquet").sort_values(["trip_id", "t"], kind="stable")
    cams = pd.read_csv(work / "cameras.csv")
    import json
    n_bins = json.load(open(work / "meta.json"))["n_bins"]

    t = trans["t_exit"].to_numpy(); sp = ex["splits"]
    m_train = _period_mask(t, sp["train"], tz); m_cal = _period_mask(t, sp["cal"], tz)
    m_test = np.zeros(len(t), bool)
    for s in sp["test"]:
        m_test |= _period_mask(t, s["range"], tz)
    trans = _add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    print("[factors] building features ...")
    feat = build_features(trans, sight, traj, cams, m_train)
    feat = feat.set_index("tr_id").loc[trans["tr_id"]].reset_index()   # align with trans order

    ok = ~trans["is_exit"].to_numpy()
    tr_train = trans[m_train]; tr_cal = trans[m_cal & ok]; tr_test = trans[m_test & ok]
    truth_map = _truth_by_tr(truth)
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    vm = VisibilityModel(ex["predictors"][predictor], cand, n_bins, **ex["model"]).fit(tr_train, truth_map)
    s_cal, _, _ = vm.score(tr_cal, truth_map)
    s_test, _, _ = vm.score(tr_test, truth_map)
    alpha = 1 - ex["target_recall"]
    tau_s = static_taus(s_cal, len(tr_test), alpha)
    tau_q, _ = qr_group_taus(tr_cal, s_cal, tr_test, CURRENT_DIMS, alpha)

    df = feat.set_index("tr_id").loc[tr_test["tr_id"]].reset_index()
    df["miss_static"] = (s_test < tau_s).astype(int)
    df["miss_qr"] = (s_test < tau_q).astype(int)
    print(f"[factors] test hops={len(df)}  miss_static={df.miss_static.mean():.4f}  "
          f"miss_qr={df.miss_qr.mean():.4f}")

    # delay spread uses all test transitions (incl. exits) for exit rate
    allt = feat.set_index("tr_id").loc[trans.loc[m_test, "tr_id"]].reset_index()
    dbs = delay_by_speed(allt); dbs.to_csv(out_dir / "delay_by_speed.csv")

    results = {"delay_by_speed": dbs}
    for outcome in ["miss_static", "miss_qr"]:
        uni, spread, overall = univariate(df, outcome)
        uni.to_csv(out_dir / f"univariate_{outcome}.csv", index=False)
        spread.to_csv(out_dir / f"spread_{outcome}.csv")
        lg, nlg = logit(df, outcome, max_logit_n)
        lg.to_csv(out_dir / f"logit_{outcome}.csv")
        txt, leaves = tree(df, outcome)
        (out_dir / f"tree_{outcome}.txt").write_text(txt, encoding="utf-8")
        leaves.to_csv(out_dir / f"tree_leaves_{outcome}.csv")
        results[outcome] = dict(uni=uni, spread=spread, overall=overall, logit=lg, n_logit=nlg, leaves=leaves)
        _plot_univariate(uni, overall, alpha, out_dir / f"univariate_{outcome}.png", outcome)
    return results


def _plot_univariate(uni, overall, alpha, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fs = list(dict.fromkeys(uni["factor"]))
    ncol = 4; nrow = int(np.ceil(len(fs) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.0 * ncol, 2.8 * nrow), squeeze=False, sharey=True)
    for ax, f in zip(axes.ravel(), fs):
        d = uni[uni["factor"] == f]
        xs = np.arange(len(d))
        ax.bar(xs, d["miss_rate"], color="tab:blue", alpha=0.8)
        ax.errorbar(xs, d["miss_rate"], yerr=[d["miss_rate"] - d["ci_lo"], d["ci_hi"] - d["miss_rate"]],
                    fmt="none", color="k", lw=0.8)
        ax.axhline(overall, color="gray", ls="--", lw=1); ax.axhline(alpha, color="red", ls=":", lw=1)
        ax.set_xticks(xs); ax.set_xticklabels([str(v) for v in d["level"]], fontsize=6, rotation=30)
        ax.set_title(f, fontsize=9)
    for ax in axes.ravel()[len(fs):]:
        ax.axis("off")
    axes[0, 0].set_ylabel("miss rate")
    fig.suptitle(f"{title}: miss rate by factor level (dashed=overall, dotted=target alpha)", fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
