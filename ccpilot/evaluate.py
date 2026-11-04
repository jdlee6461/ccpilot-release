"""Pilot evaluation.

RQ1  (original)  : does a validation-tuned threshold keep the target hop recall
                   under traffic shift, and does adaptive calibration keep it?
RQ1' (exploratory, from the first Porto run): marginal recall is kept, but is it
                   systematically violated in operationally relevant conditions
                   (time of day, first hop of a track, exit zone, exit speed)?
                   -> conditional / worst-group coverage.
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import static_taus, mondrian_taus, aci_taus, conformal_tau
from .geo import date_to_unix
from .predictors import (TAU_MIN, VisibilityModel, OutageAwareModel, SpatulaRule, CityTracRule, candidate_sets,
                         _truth_by_tr)
from . import plots
from .multigroup import group_matrix, mvp_taus, qr_group_taus, qr_ogd_taus, qr_refit_taus


def _period_mask(t, rng, tz):
    return (t >= date_to_unix(rng[0], tz)) & (t < date_to_unix(rng[1], tz))


def _group_ids(df_list, cols):
    """Consistent integer group ids for a combination of columns across frames."""
    if not cols:
        return [np.zeros(len(d), int) for d in df_list]
    keys = [pd.MultiIndex.from_frame(d[cols].astype(int)) for d in df_list]
    allk = keys[0]
    for k in keys[1:]:
        allk = allk.append(k)
    codes = pd.Index(allk.unique())
    return [codes.get_indexer(k) for k in keys]


def _add_strata(trans, tr_train, n_speed_bins):
    trans = trans.copy()
    trans["hopfirst"] = (trans["hop"] == 0).astype(int)
    trans["grp_all"] = 0          # the 'all hops' group, so it can be listed in strata
    # hopkind: 0 = later hop, 1 = first hop of a trip (e.g. taxi departing),
    #          2 = first hop of a chain resumed after an 'exit' gap within the same trip
    trans["hopkind"] = np.where(trans["hop"] > 0, 0, np.where(trans["chain"] == 0, 1, 2))
    q = np.quantile(tr_train["speed_out"], np.linspace(0, 1, n_speed_bins + 1)[1:-1])
    trans["speed_bin"] = np.digitize(trans["speed_out"], q)
    return trans


def _add_spatial(trans, m_train, cams, k=4, nn_radius_note=None):
    """Camera-level strata known in advance (from the camera map and historical data):
    entropy_bin : entropy of the source camera's next-camera distribution in TRAINING
                  (how 'branchy' the source is); unseen sources -> highest bin
    nn_bin      : distance from the source camera to its nearest other camera (isolation)
    Bin edges are quantiles over TRAINING transitions."""
    trans = trans.copy()
    trn = trans[m_train & ~trans["is_exit"].to_numpy()]
    p = trn.groupby(["src", "first_cam"]).size()
    p = p / p.groupby(level=0).transform("sum")
    ent = (-(p * np.log(p))).groupby(level=0).sum()
    e = trans["src"].map(ent).to_numpy(dtype=float)
    xy = cams[["x", "y"]].to_numpy()
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1)[trans["src"].to_numpy()]
    for col, v in [("entropy_bin", e), ("nn_bin", nn)]:
        ref = v[m_train & np.isfinite(v)]
        edges = np.unique(np.quantile(ref, np.linspace(0, 1, k + 1)[1:-1]))
        b = np.digitize(np.nan_to_num(v, nan=np.inf), edges)
        trans[col] = np.minimum(b, k - 1)
    return trans


def _wilson_ub(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n)) / d + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d


def run(cfg, trans, truth, cams, n_bins, out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    tz = cfg["timezone"]; ev = cfg["events"]; ex = cfg["eval"]
    delta = ev["bin_s"]; t_max = ev["t_max_s"]
    alpha = 1.0 - ex["target_recall"]
    rng = np.random.default_rng(ex.get("seed", 0))

    t = trans["t_exit"].to_numpy()
    sp = ex["splits"]
    seg_names = [s["name"] for s in sp["test"]]
    m_train = _period_mask(t, sp["train"], tz)
    m_cal = _period_mask(t, sp["cal"], tz)
    seg_masks = {s["name"]: _period_mask(t, s["range"], tz) for s in sp["test"]}
    m_test = np.zeros(len(t), bool)
    for m in seg_masks.values():
        m_test |= m
    trans = _add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    trans = _add_spatial(trans, m_train, cams, ex.get("n_spatial_bins", 4))

    tr_train = trans[m_train]
    ok = ~trans["is_exit"].to_numpy()
    tr_cal = trans[m_cal & ok].sort_values("t_exit").reset_index(drop=True)
    tr_test = trans[m_test & ok].sort_values("t_exit").reset_index(drop=True)
    print(f"[eval] train={m_train.sum()} cal={len(tr_cal)} test={len(tr_test)} "
          f"(exit rate train={trans.loc[m_train, 'is_exit'].mean():.3f})")
    if m_train.sum() == 0 or len(tr_cal) == 0 or len(tr_test) == 0:
        span = pd.to_datetime([t.min(), t.max()], unit="s", utc=True).tz_convert(tz)
        raise SystemExit(f"[eval] empty split. Data covers {span[0]} .. {span[1]}; "
                         f"check eval.splits in the config.")
    seg_of = np.full(len(tr_test), "", dtype=object)
    for name, m in seg_masks.items():
        ids = set(trans.loc[m, "tr_id"].tolist())
        seg_of[tr_test["tr_id"].isin(ids).to_numpy()] = name

    truth_map = _truth_by_tr(truth)
    # ---- post-hoc sensitivity: imperfect detection (default p_det = 1 -> identical to before)
    det = ex.get("detection", {}) or {}
    p_det = float(det.get("p_det", 1.0))
    if p_det < 1.0:
        drng = np.random.default_rng(det.get("seed", 1))
        keep = drng.random(len(truth)) < p_det          # each (transition, camera) visit detected w.p. p_det
        truth_map_obs = _truth_by_tr(truth[keep])
        print(f"[eval] detection p_det={p_det}: kept {keep.mean():.3f} of camera visits as detected")
    else:
        truth_map_obs = truth_map
    # observed labels drive training, calibration and feedback; true labels are used for evaluation
    truth_map_train = truth_map_obs if det.get("train_on_detected", True) else truth_map
    a_m = 1.0 - (1.0 - alpha) * p_det if det.get("adjust_target", False) else alpha
    if a_m != alpha:
        print(f"[eval] target adjusted for detection: observed-coverage target {1 - a_m:.4f}")
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    # ---- post-hoc stress test: camera outage (offline sites from t_start onwards)
    outg = ex.get("outage", {}) or {}
    offline = [int(c) for c in outg.get("cams", [])]
    out_mask = None

    rows, hit_store = [], {}
    a_cfg = ex["aci"]
    fb_mask = rng.random(len(tr_test)) < a_cfg["feedback_fraction"]
    t_exit = tr_test["t_exit"].to_numpy()
    t_res_hit = tr_test["t_arrive"].to_numpy()
    t_res_miss = t_exit + t_max
    if offline:
        out_mask = t_exit >= float(outg["t_start"])
        print(f"[eval] outage: {len(offline)} sites offline for {out_mask.mean():.3f} of test hops")
    if a_cfg.get("feedback_delay", "realistic") == "none":   # theory setting: outcome known immediately
        t_res_hit = t_exit.copy(); t_res_miss = t_exit.copy()
    W = ex["rolling_window"]; dip = ex.get("dip_margin", 0.05)

    def dip_stats(hit, m):
        r = pd.Series(hit[m].astype(float)).rolling(W, min_periods=W).mean().dropna()
        if len(r) == 0:
            return {"roll_p05": np.nan, "frac_below": np.nan}
        return {"roll_p05": float(np.quantile(r, 0.05)),
                "frac_below": float((r < (1 - alpha) - dip).mean())}

    strata_vals = {d: tr_test[d].to_numpy() for d in ex["strata"]}
    min_n = ex.get("min_group_n", 200)

    bar = ex.get("group_bar", 0.94)

    def worst_group(hit, m):
        best = (np.inf, "", 0, np.nan); n_sig = 0
        for d, v in strata_vals.items():
            for g in np.unique(v[m]):
                mm = m & (v == g)
                nn = int(mm.sum())
                if nn < min_n:
                    continue
                k = int(hit[mm].sum()); cov = k / nn; ub = _wilson_ub(k, nn)
                if ub < bar:
                    n_sig += 1
                if cov < best[0]:
                    best = (cov, f"{d}={g}", nn, ub)
        return best + (n_sig,)

    def record(pred, method, hit, cost, struct=None, hit_obs=None):
        hit_store[(pred, method)] = (hit, cost)
        hit_obs = hit if hit_obs is None else hit_obs
        for seg in seg_names:
            m = seg_of == seg
            wg = worst_group(hit, m)
            rows.append({"predictor": pred, "method": method, "segment": seg, "n": int(m.sum()),
                         "coverage": hit[m].mean(), "coverage_detected": hit_obs[m].mean(),
                         "target": 1 - alpha, "target_used": 1 - a_m,
                         "worst_group_cov": wg[0], "worst_group": wg[1], "worst_group_n": wg[2],
                         "worst_group_ub95": wg[3], "n_groups_sig_below_bar": wg[4],
                         "cost_mean_cam_s": cost[m].mean(), "cost_median_cam_s": np.median(cost[m]),
                         **dip_stats(hit, m),
                         "structural_miss": (struct[m].mean() if struct is not None else np.nan)})

    sr = SpatulaRule(cand, n_bins, delta, ex["spatula"]["s_thresh"], ex["spatula"]["t_quantile"]).fit(tr_train)
    h, c = sr.evaluate(tr_test, truth_map, out_mask, offline)
    h_obs, _ = sr.evaluate(tr_test, truth_map_obs, out_mask, offline) if p_det < 1.0 else (h, c)
    record("spatula_rule", "fixed", h, c, hit_obs=h_obs)
    ct = ex.get("citytrac", {}) or {}
    for tgt in ct.get("targets", []):
        cr = CityTracRule(cand, n_bins, delta, tgt, ct.get("window_q", 0.98), ct.get("min_n", 30)).fit(tr_train)
        h, c = cr.evaluate(tr_test, truth_map, out_mask, offline)
        h_obs, _ = cr.evaluate(tr_test, truth_map_obs, out_mask, offline) if p_det < 1.0 else (h, c)
        record("citytrac_rule", f"target{int(round(tgt * 100)):03d}", h, c, hit_obs=h_obs)

    traces = {}
    score_store = {}
    det_store, refit_log = {}, []
    diag = ex.get("mvp_diag")          # post-hoc: per-query q and (V, N) snapshots of MVP variants
    diag_q, diag_state = {}, []
    pred_items = [(p, lv, False) for p, lv in ex["predictors"].items()]
    if offline:     # post-hoc: outage-aware copies of listed predictors, evaluated as separate predictors
        pred_items += [(f"{p}_oa", ex["predictors"][p], True) for p in outg.get("aware_predictors", [])]
    for pname, levels, aware in pred_items:
        vm = (OutageAwareModel if aware else VisibilityModel)(levels, cand, n_bins, **ex["model"]).fit(
            tr_train, truth_map_train)
        if aware:
            vm.fit_next(tr_train, trans, delta)
        s_cal, _, _ = vm.score(tr_cal, truth_map_obs)                 # observed labels
        if offline:
            vm.set_offline(offline)
        s_true, kid, struct = vm.score(tr_test, truth_map, out_mask)            # evaluation (true)
        s_test = vm.score(tr_test, truth_map_obs, out_mask)[0] if p_det < 1.0 else s_true   # feedback (observed)
        alpha_true = alpha; alpha = a_m                               # methods calibrate to a_m

        taus = {"static": static_taus(s_cal, len(tr_test), alpha)}
        for mname, cols in ex["mondrian"].items():
            g_cal, g_test = _group_ids([tr_cal, tr_test], cols)
            taus[mname] = mondrian_taus(s_cal, g_cal, g_test, alpha, ex.get("min_group_n", 200))
        for v in ex["aci_variants"]:
            g_cal, g_test = _group_ids([tr_cal, tr_test], v.get("groups", []))
            floor = v.get("alpha_floor", -0.5)
            if isinstance(floor, str) and floor.startswith("alpha/"):
                floor = alpha / float(floor.split("/")[1])
            taus[v["name"]], trc = aci_taus(
                s_test, t_exit, t_res_hit, t_res_miss, g_test, s_cal, g_cal, alpha,
                v["gamma"], a_cfg["window"], fb_mask, alpha_clip=(floor, 1.0))
            traces[(pname, v["name"])] = trc
        mg = ex.get("multigroup", {})
        if pname in mg.get("predictors", []):
            (G_cal, G_test), gnames = group_matrix([tr_cal, tr_test], mg["dims"])
            cal_t = tr_cal["t_exit"].to_numpy()
            for v in mg.get("mvp_variants", [{"name": "mvp_groups"}]):
                kw = dict(m=v.get("m", 40), r=v.get("r", 1000), eta=v.get("eta", "theory"),
                          eps=v.get("eps", 1.0), seed=ex.get("seed", 0),
                          scale=v.get("scale", "quantile"), a_min=v.get("a_min", 0.002))
                if v.get("warm_weight", 1.0) != 1.0:
                    kw["warm_weight"] = v["warm_weight"]
                if v.get("floor_level") is not None:
                    kw["floor_level"] = v["floor_level"]
                if diag:
                    kw["snapshot_times"] = diag.get("snapshot_times", [])
                Gc, Gt = (G_cal[:, :1], G_test[:, :1]) if v.get("global_only") else (G_cal, G_test)
                taus[v["name"]], qs, mobj = mvp_taus(s_test, t_exit, t_res_hit, t_res_miss, Gt,
                                                     s_cal, cal_t, Gc, alpha, fb_mask, **kw)
                if diag:
                    diag_q[f"q|{pname}|{v['name']}"] = qs
                    gn = gnames[:Gt.shape[1]]
                    for ts, V, N in mobj.snapshots:
                        for gi, g in enumerate(gn):
                            diag_state.append(pd.DataFrame({
                                "predictor": pname, "method": v["name"], "t_snap": ts, "group": g,
                                "bucket": np.arange(mobj.m), "V": V[gi], "N": N[gi]}))
                print(f"[mvp] {pname}/{v['name']}: groups={Gt.shape[1]} eta={mobj.eta:.4f} "
                      f"m={mobj.m} scale={mobj.scale}")
            taus["qr_groups"], _ = qr_group_taus(tr_cal, s_cal, tr_test, mg["dims"], alpha,
                                                 mg.get("qr_max_n", 80000), ex.get("seed", 0))
            if "qr_ogd" in mg:
                o = mg["qr_ogd"]
                taus["qr_ogd"] = qr_ogd_taus(taus["qr_groups"], s_test, t_exit, t_res_hit, t_res_miss,
                                             G_test, alpha, fb_mask, o.get("gamma", 0.005), o.get("clip", 3.0))
            # confirm2 comparators (2026-10-13): qr_groups refitted every evaluation day at 00:00 local time
            for v in mg.get("qr_refit", []):
                if pname not in v.get("predictors", mg.get("predictors", [])):
                    continue
                d0 = pd.Timestamp(min(r["range"][0] for r in sp["test"]))
                d1 = pd.Timestamp(max(r["range"][1] for r in sp["test"]))
                refit_t = [date_to_unix(str(d.date()), tz) for d in pd.date_range(d0, d1 - pd.Timedelta(days=1))]
                w = v.get("window_days")
                t0r = time.time()
                taus[v["name"]], nfit, _ = qr_refit_taus(
                    tr_cal, s_cal, tr_cal["t_arrive"].to_numpy(), tr_test, s_test, t_exit, t_res_hit, t_res_miss,
                    fb_mask, mg["dims"], alpha, refit_t, mg.get("qr_max_n", 80000), ex.get("seed", 0),
                    None if w is None else float(w) * 86400.0, v.get("lp_method", "highs"))
                refit_log.append({"predictor": pname, "method": v["name"], "n_refits": len(nfit),
                                  "fit_rows_min": int(nfit.min()), "fit_rows_max": int(nfit.max()),
                                  "seconds": time.time() - t0r})
                print(f"[qr_refit] {pname}/{v['name']}: {len(nfit)} refits, rows {nfit.min()}..{nfit.max()}, "
                      f"{time.time() - t0r:.0f}s")
        alpha = alpha_true
        if ex.get("save_scores"):     # post-hoc: per-hop scores and the lowest mvp_log threshold
            score_store[pname] = s_true
            cs = np.sort(s_cal)
            for a_min in ex["save_scores"].get("tau_min_levels", [0.002]):
                k = int(np.floor(a_min * len(cs)))
                score_store[f"taumin{a_min:g}|{pname}"] = max(float(cs[min(k, len(cs) - 1)]), TAU_MIN) if k > 0 \
                    else TAU_MIN
        for mname, tau in taus.items():
            record(pname, mname, s_true >= tau, vm.cost(kid, tau, delta), struct, hit_obs=s_test >= tau)
            sdt = ex.get("save_detect_time") or {}               # post-hoc output: detection time per hop
            if pname in sdt.get("predictors", []) and mname in sdt.get("methods", []):
                det_store[(pname, mname)] = vm.detect_bins(tr_test, truth_map, tau, out_mask)
                assert np.array_equal(det_store[(pname, mname)] >= 0, s_true >= tau)
        if pname in (ex.get("save_cost_lookup") or []):         # post-hoc output: per-hop key for cost at any tau
            score_store[f"kid|{pname}"] = kid
            used = np.unique(kid)
            np.savez_compressed(out_dir / f"cost_lookup_{pname}.npz", kid=used, delta=delta,
                                **{f"v{int(k)}": vm.sorted_vals[int(k)] for k in used})
        for seg in seg_names:
            m = seg_of == seg
            tau_o = conformal_tau(s_test[m], a_m)      # post-hoc on observed labels
            co = vm.cost(kid[m], tau_o, delta)
            rows.append({"predictor": pname, "method": "oracle(post-hoc)", "segment": seg,
                         "n": int(m.sum()), "coverage": (s_true[m] >= tau_o).mean(),
                         "coverage_detected": (s_test[m] >= tau_o).mean(),
                         "target": 1 - alpha, "target_used": 1 - a_m,
                         **dict(zip(["worst_group_cov", "worst_group", "worst_group_n", "worst_group_ub95",
                                     "n_groups_sig_below_bar"], worst_group(s_true >= tau_o, m))),
                         "cost_mean_cam_s": co.mean(), "cost_median_cam_s": np.median(co),
                         "roll_p05": np.nan, "frac_below": np.nan, "structural_miss": struct[m].mean()})
        plots.frontier(vm, s_true, kid, seg_of, delta, alpha, pname,
                       {k: v for k, v in hit_store.items() if k[0] in (pname, "spatula_rule")},
                       out_dir / f"frontier_{pname}.png")

    res = pd.DataFrame(rows)
    res.to_csv(out_dir / "summary.csv", index=False)
    if refit_log:
        pd.DataFrame(refit_log).to_csv(out_dir / "qr_refit_log.csv", index=False)

    cond, worst = conditional_tables(tr_test, hit_store, seg_of, ex["strata"], ex.get("min_group_n", 200))
    cond.to_csv(out_dir / "conditional_coverage.csv", index=False)
    worst.to_csv(out_dir / "worst_group.csv", index=False)

    conf = confound_table(tr_test, hit_store, seg_of)
    conf.to_csv(out_dir / "confound_crosstab.csv", index=False)

    if ex.get("save_hits"):
        # per-hop outcomes for post-hoc regrading (group definitions, bars) without re-running
        keep = ["tr_id", "trip_id", "chain", "hop", "t_exit", "grp_all", "hgroup", "hopfirst", "hopkind",
                "speed_bin", "zone", "entropy_bin", "nn_bin"]
        H = tr_test[[c for c in keep if c in tr_test.columns]].copy()
        H["segment"] = seg_of
        for (pred, meth), (hit, cost) in hit_store.items():
            H[f"hit|{pred}|{meth}"] = hit.astype(np.int8)
            H[f"cost|{pred}|{meth}"] = cost.astype(np.float32)
        for k, v in score_store.items():
            H[k if k.startswith(("taumin", "kid|")) else f"score|{k}"] = v
        for (pred, meth), b in det_store.items():          # seconds after exit (bin start); NaN = not detected
            H[f"tdet|{pred}|{meth}"] = np.where(b >= 0, b * delta, np.nan).astype(np.float32)
        if ex.get("save_feedback_mask"):
            H["feedback"] = fb_mask.astype(np.int8)
            H["t_res_hit"] = t_res_hit; H["t_res_miss"] = t_res_miss
        H.to_parquet(out_dir / "hits.parquet")
        print(f"[eval] saved per-hop outcomes -> {out_dir / 'hits.parquet'}")

    if diag:
        Q = tr_test[["tr_id", "t_exit"]].copy()
        for c, qs in diag_q.items():
            Q[c] = qs
        Q.to_parquet(out_dir / "mvp_q.parquet")
        if diag_state:
            pd.concat(diag_state, ignore_index=True).to_parquet(out_dir / "mvp_state.parquet")
        print(f"[eval] saved MVP diagnostics -> {out_dir / 'mvp_q.parquet'}, mvp_state.parquet")

    cust = custody_table(tr_test, hit_store, seg_of, ex["max_hops"])
    cust.to_csv(out_dir / "custody_by_hops.csv", index=False)

    pm = ex.get("plot_methods")
    plots.rolling(tr_test, hit_store, seg_of, alpha, W, out_dir, methods=pm)
    plots.custody(cust, alpha, out_dir, methods=pm)
    plots.alpha_trace(tr_test, traces, alpha, out_dir)
    plots.conditional(cond, alpha, out_dir, methods=pm)
    return res, worst, conf


def conditional_tables(tr_test, hit_store, seg_of, strata, min_n):
    rows = []
    for (pred, meth), (hit, cost) in hit_store.items():
        for seg in np.unique(seg_of):
            ms = seg_of == seg
            for dim in strata:
                vals = tr_test[dim].to_numpy()
                for g in np.unique(vals[ms]):
                    m = ms & (vals == g)
                    rows.append({"predictor": pred, "method": meth, "segment": seg, "dim": dim,
                                 "group": int(g), "n": int(m.sum()), "coverage": hit[m].mean(),
                                 "cost_mean_cam_s": cost[m].mean()})
    cond = pd.DataFrame(rows)
    big = cond[cond["n"] >= min_n]
    idx = big.groupby(["predictor", "method", "segment", "dim"])["coverage"].idxmin()
    worst = big.loc[idx, ["predictor", "method", "segment", "dim", "group", "n", "coverage"]]
    worst = worst.rename(columns={"group": "worst_group", "coverage": "worst_coverage"})
    return cond, worst.reset_index(drop=True)


def confound_table(tr_test, hit_store, seg_of):
    """Coverage and counts in the hopkind x speed_bin cross-classification."""
    hk = tr_test["hopkind"].to_numpy(); sb = tr_test["speed_bin"].to_numpy()
    rows = []
    for (pred, meth), (hit, _) in hit_store.items():
        for seg in np.unique(seg_of):
            ms = seg_of == seg
            for k in np.unique(hk[ms]):
                for b in np.unique(sb[ms]):
                    m = ms & (hk == k) & (sb == b)
                    if m.sum() == 0:
                        continue
                    rows.append({"predictor": pred, "method": meth, "segment": seg, "hopkind": int(k),
                                 "speed_bin": int(b), "n": int(m.sum()), "share": m.sum() / ms.sum(),
                                 "coverage": hit[m].mean()})
    return pd.DataFrame(rows)


def custody_table(tr_test, hit_store, seg_of, max_hops):
    key = tr_test["trip_id"].astype(str) + "_" + tr_test["chain"].astype(str)
    hop = tr_test["hop"].to_numpy()
    out = []
    for (pred, meth), (hit, _) in hit_store.items():
        df = pd.DataFrame({"key": key, "hop": hop, "hit": hit, "seg": seg_of}).sort_values(["key", "hop"])
        df = df[df.groupby("key")["hop"].transform("min") == 0]
        df["ok_so_far"] = df.groupby("key")["hit"].cummin()
        df["h"] = df.groupby("key").cumcount() + 1
        seg_first = df.groupby("key")["seg"].transform("first")
        for seg in np.unique(seg_of):
            d = df[seg_first == seg]
            for h in range(1, max_hops + 1):
                dh = d[d["h"] == h]
                if len(dh) < 30:
                    continue
                out.append({"predictor": pred, "method": meth, "segment": seg, "hops": h,
                            "n_chains": len(dh), "custody": dh["ok_so_far"].mean()})
    return pd.DataFrame(out)
