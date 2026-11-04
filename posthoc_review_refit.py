"""POST HOC (external review): daily-refitted group QR under censored feedback (REVIEW_PLAN.md B (a), (b)) and the C refit.

    python posthoc_review_refit.py --job LABEL BLOCK SEED [--target T]   # t = 0.95 unless --target (conditional 0.93)
LABEL:
  copy_check   : post-hoc copy below with every feedback hop labelled (= qr_groups_refit); must equal the stored hits
  Bi_refit_a   : (i)  labelled rows = calibration hops + detected feedback hops
  Bii_refit_a  : (ii) feedback set fb_mask | audit; labelled = detected feedback hops + every audited hop
  Bi_refit_b_k0005, Bi_refit_b_k002 : (i) Chernozhukov-Hong three-step left-censored QR, kappa 0.005 / 0.02, delta 0
  C_src_zone_speed_qr_groups_refit  : multigroup.qr_refit_taus (unchanged) with predictor src_zone_speed
  copy_check7  : post-hoc copy with the 7-day window and every feedback hop labelled (= qr_groups_refit7); must equal
                 the stored hits (REVIEW_PLAN rev 5)
  Biv_refit7_a : (iv) qr_groups_refit7: feedback set fb_mask | audit; labelled = detected feedback hops + every audited
                 hop, calibration and labelled hops resolved in (T - 7 days, T] (REVIEW_PLAN rev 5; = refit7 under (ii))
Output: work/review_cache/runs/<block>_t0950_s<seed>__<LABEL>.parquet (hit|LABEL, cost|LABEL), timing json in review/timing/.
"""
import argparse
import time

import numpy as np
import pandas as pd

import posthoc_review_common as C

C.threads(1)
import pandas  # noqa: E402,F401
from scipy import sparse  # noqa: E402
from scipy.optimize import linprog  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from ccpilot.geo import date_to_unix  # noqa: E402
from ccpilot.multigroup import _design, qr_refit_taus  # noqa: E402
from ccpilot.predictors import TAU_MIN  # noqa: E402
from posthoc_review_methods import audit_mask, lookups  # noqa: E402


def _qr(X, y, alpha, max_n, seed, lp_method):
    if len(y) > max_n:
        idx = np.random.default_rng(seed).choice(len(y), max_n, replace=False)
        X, y = X[idx], y[idx]
    n, p = X.shape
    c = np.r_[np.zeros(p), np.full(n, alpha), np.full(n, 1 - alpha)]
    A = sparse.hstack([sparse.csr_matrix(X), sparse.identity(n, format="csr"), -sparse.identity(n, format="csr")],
                      format="csr")
    res = linprog(c, A_eq=A, b_eq=y, bounds=[(None, None)] * p + [(0, None)] * (2 * n), method=lp_method)
    if not res.success:
        raise RuntimeError(f"quantile regression failed: {res.message}")
    return res.x[:p], n


def refit_censored(cal_df, cal_scores, test_df, test_scores, t_exit, t_res_hit, t_res_miss, fbset, dims, alpha,
                   refit_times, max_n=80000, seed=0, mode="full", audit=None, kappa=None, delta=0.0, lp_method="highs",
                   window_s=None, cal_t_res=None):
    """post-hoc copy of multigroup.qr_refit_taus (window_s None) with the label rule of a feedback hop as a parameter:
      mode 'full'     : every resolved feedback hop gives its score (= qr_refit_taus)
      mode 'labelled' : only detected (score >= tau) or audited hops give their score; missed ones are dropped
      mode 'ch'       : Chernozhukov-Hong three-step left-censored QR; a missed hop enters with y = log tau (its
                        censoring value). Step 1 logit P(detected | x) on the resolved feedback hops; step 2 QR on the
                        calibration hops + feedback hops with fitted P > 1 - alpha + kappa; step 3 QR on the calibration
                        hops + feedback hops with x'beta_2 > log tau + delta.
    window_s (rev 5): None = cumulative (every calibration hop); w = calibration hops (resolved at cal_t_res) and
    feedback hops resolved in (T - w, T], as multigroup.qr_refit_taus for qr_groups_refit7 ('full' and 'labelled')."""
    test_scores = np.asarray(test_scores, float); t_exit = np.asarray(t_exit, float)
    Xc, Xt = _design([cal_df, test_df], dims)
    yc = np.log(np.maximum(np.asarray(cal_scores, float), 1e-8)); yt = np.log(np.maximum(test_scores, 1e-8))
    audit = np.zeros(len(test_scores), bool) if audit is None else audit
    taus = np.full(len(test_scores), np.nan); t_res = np.full(len(test_scores), np.inf)
    refit_times = np.sort(np.asarray(refit_times, float)); bounds_t = np.r_[refit_times[1:], np.inf]
    log = []
    for k, (T, T_next) in enumerate(zip(refit_times, bounds_t)):
        mf = fbset & (t_res <= T)
        if window_s is None:
            Xw, yw = Xc, yc
        else:
            assert mode in ("full", "labelled")
            mc = (cal_t_res <= T) & (cal_t_res > T - window_s)
            mf = mf & (t_res > T - window_s)
            Xw, yw = Xc[mc], yc[mc]
        rec = {"k": k, "n_fb_resolved": int(mf.sum())}
        if mode == "full":
            beta, n = _qr(np.vstack([Xw, Xt[mf]]), np.r_[yw, yt[mf]], alpha, max_n, seed, lp_method)
        elif mode == "labelled":
            ml = mf & ((test_scores >= taus) | audit)
            rec["n_fb_labelled"] = int(ml.sum())
            beta, n = _qr(np.vstack([Xw, Xt[ml]]), np.r_[yw, yt[ml]], alpha, max_n, seed, lp_method)
        else:
            idx = np.flatnonzero(mf)
            det = test_scores[idx] >= taus[idx]
            c_ = np.log(np.maximum(taus[idx], 1e-300))
            yobs = np.where(det, yt[idx], c_)
            if len(idx) == 0 or det.all():
                beta, n = _qr(np.vstack([Xc, Xt[idx]]), np.r_[yc, yobs], alpha, max_n, seed, lp_method)
                rec.update(step2_kept=len(idx), step3_kept=len(idx))
            else:
                lg = sm.GLM(det.astype(float), Xt[idx], family=sm.families.Binomial()).fit()
                ph = lg.predict(Xt[idx])
                j2 = ph > 1 - alpha + kappa
                b2, _ = _qr(np.vstack([Xc, Xt[idx[j2]]]), np.r_[yc, yobs[j2]], alpha, max_n, seed, lp_method)
                j3 = Xt[idx] @ b2 > c_ + delta
                beta, n = _qr(np.vstack([Xc, Xt[idx[j3]]]), np.r_[yc, yobs[j3]], alpha, max_n, seed, lp_method)
                rec.update(step2_kept=int(j2.sum()), step3_kept=int(j3.sum()), n_censored=int((~det).sum()))
        rec["n_fit"] = n
        m = (t_exit < T_next) if k == 0 else (t_exit >= T) & (t_exit < T_next)
        taus[m] = np.maximum(np.exp(Xt[m] @ beta), TAU_MIN)
        fm = m & fbset
        t_res[fm] = np.where(test_scores[fm] >= taus[fm], t_res_hit[fm], t_res_miss[fm])
        log.append(rec)
    assert not np.isnan(taus).any()
    return taus, pd.DataFrame(log)


def job(label, block, s, t=0.95):
    T0 = time.time()
    cfg = C.run_cfg(block, t, s); ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    tz = cfg["timezone"]; sp = ex["splits"]
    d0 = pd.Timestamp(min(r["range"][0] for r in sp["test"])); d1 = pd.Timestamp(max(r["range"][1] for r in sp["test"]))
    refit_t = [date_to_unix(str(d.date()), tz) for d in pd.date_range(d0, d1 - pd.Timedelta(days=1))]
    v = next(v for v in mg["qr_refit"] if v["name"] == "qr_groups_refit")
    assert v.get("window_days") is None
    cal = C.load_cal(block)
    H = C.load_hits(block, t, s)
    n = len(H); fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    cols = ["t_exit"] + C.DIMS
    lp = v.get("lp_method", "highs"); max_n = mg.get("qr_max_n", 80000); sd = ex.get("seed", 0)
    pred = "src_zone_speed" if label.startswith("C_") else C.PRIMARY
    sc = cal[f"score|{pred}"].to_numpy(); st = H[f"score|{pred}"].to_numpy()
    info = {"label": label, "block": block, "target": t, "seed": s, "predictor": pred}
    lg = None
    if label.startswith("C_"):
        taus, nfit, _ = qr_refit_taus(cal, sc, cal["t_arrive"].to_numpy(), H[cols], st, t_exit, th, tm, fb, mg["dims"],
                                      alpha, refit_t, max_n, sd, None, lp)
    elif label == "copy_check":
        taus, lg = refit_censored(cal, sc, H[cols], st, t_exit, th, tm, fb, mg["dims"], alpha, refit_t, max_n, sd,
                                  "full", lp_method=lp)
        info["bitwise_vs_stored"] = bool(np.array_equal((st >= taus).astype(np.int8),
                                                        H[f"hit|{pred}|qr_groups_refit"].to_numpy()))
    elif label in ("Bi_refit_a", "Bii_refit_a"):
        audit = audit_mask(s, n, fb) if label.startswith("Bii") else np.zeros(n, bool)
        taus, lg = refit_censored(cal, sc, H[cols], st, t_exit, th, tm, fb | audit, mg["dims"], alpha, refit_t, max_n,
                                  sd, "labelled", audit=audit, lp_method=lp)
    elif label in ("copy_check7", "Biv_refit7_a"):           # REVIEW_PLAN rev 5
        v7 = next(v for v in mg["qr_refit"] if v["name"] == "qr_groups_refit7")
        w = float(v7["window_days"]) * 86400.0
        audit = audit_mask(s, n, fb) if label == "Biv_refit7_a" else np.zeros(n, bool)
        taus, lg = refit_censored(cal, sc, H[cols], st, t_exit, th, tm, fb | audit, mg["dims"], alpha, refit_t, max_n,
                                  sd, "full" if label == "copy_check7" else "labelled", audit=audit,
                                  lp_method=v7.get("lp_method", "highs"), window_s=w,
                                  cal_t_res=cal["t_arrive"].to_numpy())
        if label == "copy_check7":
            info["bitwise_vs_stored"] = bool(np.array_equal((st >= taus).astype(np.int8),
                                                            H[f"hit|{pred}|qr_groups_refit7"].to_numpy()))
        info["window_days"] = float(v7["window_days"])
    elif label.startswith("Bi_refit_b_k"):
        kappa = {"k0005": 0.005, "k002": 0.02}[label.split("_")[-1]]
        taus, lg = refit_censored(cal, sc, H[cols], st, t_exit, th, tm, fb, mg["dims"], alpha, refit_t, max_n, sd,
                                  "ch", kappa=kappa, delta=0.0, lp_method=lp)
        info["kappa"] = kappa; info["delta"] = 0.0
    else:
        raise SystemExit(f"unknown label {label}")
    lk = lookups(block)
    tag = f"{block}_t{int(round(t * 1000)):04d}_s{s}"
    (C.CACHE / "runs").mkdir(parents=True, exist_ok=True)
    pd.DataFrame({f"hit|{label}": (st >= taus).astype(np.int8),
                  f"cost|{label}": lk[pred].cost_per_hop(taus).astype(np.float32)}).to_parquet(
        C.CACHE / "runs" / f"{tag}__{label}.parquet")
    if lg is not None:
        (C.OUT / "refit_logs").mkdir(parents=True, exist_ok=True)
        lg.to_csv(C.OUT / "refit_logs" / f"{tag}__{label}.csv", index=False)
    info["seconds"] = time.time() - T0
    C.write_json(info, C.OUT / "timing" / f"refit_{tag}__{label}.json")
    print(info, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", nargs=3, required=True)
    ap.add_argument("--target", type=float, default=0.95)      # conditional 0.93 refit (instruction 02 v02 §6.3)
    a = ap.parse_args()
    job(a.job[0], a.job[1], int(a.job[2]), a.target)


if __name__ == "__main__":
    main()
