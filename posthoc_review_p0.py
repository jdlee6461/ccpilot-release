"""POST HOC (external review) step P0: recompute calibration scores and cost lookups; reproduction check.

    python posthoc_review_p0.py --scores              # per block: fit the 5 predictors, save s_cal + cost lookups,
                                                      #   check evaluation scores / key ids / primary lookup bit for bit
    python posthoc_review_p0.py --check BLOCK T SEED  # one run: static, qr_groups, mvp_log hits (primary and
                                                      #   src_zone_speed) recomputed = stored hit columns
    python posthoc_review_p0.py --summary             # collect the per-run checks
    python posthoc_review_p0.py --check-qrogd BLOCK T SEED   # (instruction 01 v02 §5) qr_ogd hits, primary and
                                                      #   src_zone_speed, recomputed = stored hit columns
    python posthoc_review_p0.py --summary-qrogd       # collect into review/p0/qr_ogd_hits_check.csv

The model fit follows ccpilot/evaluate.run (same order: strata, spatial bins, candidate sets, fit on the training split,
score calibration hops then evaluation hops), with the stored run configuration (read only). Nothing in
results/porto_cctv_confirm2/ is written.
"""
import argparse
import hashlib
import time

import numpy as np
import pandas as pd

import posthoc_review_common as C

C.threads(1)
from ccpilot import evaluate as E  # noqa: E402
from ccpilot.calibration import static_taus  # noqa: E402
from ccpilot.multigroup import group_matrix, mvp_taus, qr_group_taus, qr_ogd_taus  # noqa: E402
from ccpilot.posthoc import load_work  # noqa: E402
from ccpilot.predictors import VisibilityModel, candidate_sets, _truth_by_tr  # noqa: E402


def scores(block):
    t0 = time.time()
    cfg = C.run_cfg(block)
    ex = cfg["eval"]; delta = cfg["events"]["bin_s"]
    trans, truth, cams, n_bins = load_work(cfg)
    tz = cfg["timezone"]; sp = ex["splits"]
    t = trans["t_exit"].to_numpy()
    m_train = E._period_mask(t, sp["train"], tz)
    m_cal = E._period_mask(t, sp["cal"], tz)
    m_test = np.zeros(len(t), bool)
    for s in sp["test"]:
        m_test |= E._period_mask(t, s["range"], tz)
    trans = E._add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    trans = E._add_spatial(trans, m_train, cams, ex.get("n_spatial_bins", 4))
    tr_train = trans[m_train]
    ok = ~trans["is_exit"].to_numpy()
    tr_cal = trans[m_cal & ok].sort_values("t_exit").reset_index(drop=True)
    tr_test = trans[m_test & ok].sort_values("t_exit").reset_index(drop=True)
    truth_map = _truth_by_tr(truth)
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    H = C.load_hits(block, 0.95, 0, columns=["tr_id"] + C.DIMS + [f"score|{p}" for p in C.PREDICTORS]
                    + [f"kid|{C.PRIMARY}"])
    chk = {"block": block, "n_train": int(m_train.sum()), "n_cal": len(tr_cal), "n_test": len(tr_test)}
    chk["tr_id_equal"] = bool(np.array_equal(H.tr_id.to_numpy(), tr_test.tr_id.to_numpy()))
    chk["dims_equal"] = {d: bool(np.array_equal(H[d].to_numpy(), tr_test[d].to_numpy())) for d in C.DIMS}
    cal = tr_cal[C.CAL_COLS].copy()
    (C.CACHE / block).mkdir(parents=True, exist_ok=True)
    for p in C.PREDICTORS:
        t1 = time.time()
        vm = VisibilityModel(ex["predictors"][p], cand, n_bins, **ex["model"]).fit(tr_train, truth_map)
        s_cal, kid_cal, _ = vm.score(tr_cal, truth_map)
        s_true, kid, _ = vm.score(tr_test, truth_map)
        cal[f"score|{p}"] = s_cal
        stored = H[f"score|{p}"].to_numpy()
        chk[f"score_bitwise|{p}"] = bool(stored.dtype == s_true.dtype and np.array_equal(stored, s_true))
        chk[f"score_maxabs|{p}"] = float(np.max(np.abs(stored - s_true)))
        used = np.unique(kid)
        lk = {f"v{int(k)}": vm.sorted_vals[int(k)] for k in used}
        np.savez_compressed(C.CACHE / block / f"cost_lookup_{p}.npz", kid=used, delta=delta, **lk)
        np.save(C.CACHE / block / f"kid_{p}.npy", kid)
        if p == C.PRIMARY:
            chk["kid_bitwise"] = bool(np.array_equal(H[f"kid|{p}"].to_numpy(), kid))
            z = np.load(C.run_dir(block, 0.95, 0) / f"cost_lookup_{p}.npz")
            same = set(z.files) == set(["kid", "delta"] + list(lk))
            same = same and np.array_equal(z["kid"], used) and int(z["delta"]) == int(delta)
            same = same and all(np.array_equal(z[k], v) for k, v in lk.items())
            chk["cost_lookup_bitwise"] = bool(same)
        chk[f"seconds|{p}"] = round(time.time() - t1, 1)
        print(f"[p0] {block} {p}: score bitwise {chk[f'score_bitwise|{p}']}, {chk[f'seconds|{p}']}s", flush=True)
        del vm
    cal.to_parquet(C.CACHE / block / "cal.parquet")
    chk["seconds_total"] = round(time.time() - t0, 1)
    C.write_json(chk, C.OUT / "p0" / f"scores_{block}.json")
    print(chk, flush=True)


def check(block, t, s):
    t0 = time.time()
    cfg = C.run_cfg(block, t, s)
    ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    cal = C.load_cal(block)
    cols = ["t_exit", "feedback", "t_res_hit", "t_res_miss"] + C.DIMS
    H = C.load_hits(block, t, s)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    (G_cal, G_test), _ = group_matrix([cal, H[cols]], mg["dims"])
    v = next(v for v in mg["mvp_variants"] if v["name"] == "mvp_log")
    rows = []
    for p in ("src_zone_hour_speed", "src_zone_speed"):
        s_cal = cal[f"score|{p}"].to_numpy(); s_test = H[f"score|{p}"].to_numpy()
        taus = {"static": static_taus(s_cal, len(H), alpha)}
        taus["qr_groups"], _ = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000),
                                             ex.get("seed", 0))
        taus["mvp_log"], _, _ = mvp_taus(s_test, t_exit, th, tm, G_test, s_cal, cal["t_exit"].to_numpy(), G_cal,
                                         alpha, fb, m=v.get("m", 40), r=v.get("r", 1000), eta=v.get("eta", "theory"),
                                         eps=v.get("eps", 1.0), seed=ex.get("seed", 0), scale=v.get("scale", "quantile"),
                                         a_min=v.get("a_min", 0.002))
        for m, tau in taus.items():
            h = (s_test >= tau).astype(np.int8); st = H[f"hit|{p}|{m}"].to_numpy()
            rows.append({"block": block, "target": t, "seed": s, "predictor": p, "method": m,
                         "n_diff": int((h != st).sum()), "bitwise": bool(np.array_equal(h, st))})
    D = pd.DataFrame(rows)
    D["seconds"] = round(time.time() - t0, 1)
    (C.OUT / "p0" / "runs").mkdir(parents=True, exist_ok=True)
    D.to_csv(C.OUT / "p0" / "runs" / f"check_{block}_t{int(round(t * 1000)):04d}_s{s}.csv", index=False)
    print(D.to_string(index=False), flush=True)


def check_qrogd(block, t, s):
    """qr_ogd as in evaluate.run: base thresholds from qr_group_taus (seed = evaluation seed), online correction with the
    stored feedback mask and resolution times."""
    t0 = time.time()
    cfg = C.run_cfg(block, t, s)
    ex = cfg["eval"]; mg = ex["multigroup"]; o = mg["qr_ogd"]; alpha = C.alpha_of(cfg)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    cal = C.load_cal(block)
    cols = ["t_exit", "feedback", "t_res_hit", "t_res_miss"] + C.DIMS
    H = C.load_hits(block, t, s)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    (_, G_test), _ = group_matrix([cal, H[cols]], mg["dims"])
    rows = []
    for p in ("src_zone_hour_speed", "src_zone_speed"):
        s_cal = cal[f"score|{p}"].to_numpy(); s_test = H[f"score|{p}"].to_numpy()
        base, _ = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))
        tau = qr_ogd_taus(base, s_test, t_exit, th, tm, G_test, alpha, fb, o.get("gamma", 0.005), o.get("clip", 3.0))
        h = (s_test >= tau).astype(np.int8); st = H[f"hit|{p}|qr_ogd"].to_numpy()
        rows.append({"block": block, "target": t, "seed": s, "predictor": p, "method": "qr_ogd",
                     "n_hops": len(h), "n_diff": int((h != st).sum()), "bitwise": bool(np.array_equal(h, st)),
                     "sha256_recomputed": hashlib.sha256(h.tobytes()).hexdigest(),
                     "sha256_stored": hashlib.sha256(st.astype(np.int8).tobytes()).hexdigest()})
    D = pd.DataFrame(rows)
    D["seconds"] = round(time.time() - t0, 1)
    (C.OUT / "p0" / "runs_qrogd").mkdir(parents=True, exist_ok=True)
    D.to_csv(C.OUT / "p0" / "runs_qrogd" / f"check_{block}_t{int(round(t * 1000)):04d}_s{s}.csv", index=False)
    print(D.to_string(index=False), flush=True)


def summary_qrogd():
    D = pd.concat([pd.read_csv(f) for f in sorted((C.OUT / "p0" / "runs_qrogd").glob("check_*.csv"))], ignore_index=True)
    D.to_csv(C.OUT / "p0" / "qr_ogd_hits_check.csv", index=False)
    print(D.groupby("predictor").agg(runs=("bitwise", "size"), bitwise=("bitwise", "sum"), n_diff=("n_diff", "sum")).to_string())


def summary():
    D = pd.concat([pd.read_csv(f) for f in sorted((C.OUT / "p0" / "runs").glob("check_*.csv"))], ignore_index=True)
    D.to_csv(C.OUT / "p0_repro_hits.csv", index=False)
    print(D.groupby(["predictor", "method"]).agg(runs=("bitwise", "size"), bitwise=("bitwise", "sum"),
                                                 n_diff=("n_diff", "sum")).to_string())
    print("seconds per run:", D.groupby(["block", "target", "seed"]).seconds.first().describe().round(0).to_dict())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", action="store_true")
    ap.add_argument("--check", nargs=3)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--check-qrogd", nargs=3)
    ap.add_argument("--summary-qrogd", action="store_true")
    a = ap.parse_args()
    if a.scores:
        for b in C.BLOCKS:
            scores(b)
    if a.check:
        check(a.check[0], float(a.check[1]), int(a.check[2]))
    if a.summary:
        summary()
    if a.check_qrogd:
        check_qrogd(a.check_qrogd[0], float(a.check_qrogd[1]), int(a.check_qrogd[2]))
    if a.summary_qrogd:
        summary_qrogd()


if __name__ == "__main__":
    main()
