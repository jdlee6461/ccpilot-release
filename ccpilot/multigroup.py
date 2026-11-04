"""Multi-group (overlapping-group) calibration layers.

Both methods target  P(score < tau(x) | x in G) ~= alpha  simultaneously for every
group G in a collection of possibly intersecting groups (e.g. hour group, hop kind,
exit-speed bin, exit zone), without multiplying them into disjoint cells.

1) MVP -- Bastani et al., "Practical Adversarial Multivalid Conformal Prediction",
   NeurIPS 2022 (Algorithm 1, normalized version). Online, threshold-calibrated,
   group-conditional empirical coverage against adversarially chosen sequences.

   Mapping to our setting
   - MVP covers iff s' <= q'. Our transitions are covered iff score >= tau.
     We use the monotone transform  s' = 1 - ECDF_cal(score)  (ECDF of the
     calibration scores) and map a threshold q' back to
         tau(q') = lower (1 - q')-quantile of the calibration scores,
     so that 'score >= tau(q')' <=> 's' <= q'' up to ties. Because the transform
     is ~uniform, MVP's uniform buckets have useful resolution near q' ~ 0.95.
   - Coverage indicators fed back to MVP are the realized hits of the set that
     was actually searched.
   - Warm start: MVP is first run over the calibration period in time order (with
     immediate feedback) so that it does not start from bucket 1 on test data.
   - DEVIATION FROM THE THEORY: the paper assumes the label is revealed before the
     next round. Here feedback is delayed (arrival time or t_exit + T_max) and only
     a fraction of transitions give feedback (background vehicles). State updates
     are applied when feedback resolves. The formal guarantee does not directly
     cover this setting; this must be stated in the paper.

2) Group-conditional quantile regression ("qr_groups").
   Split/offline: linear quantile regression of calibration scores at level alpha
   on an intercept + group indicators (reference coding per dimension). The QR
   first-order conditions give ~alpha miscoverage within every group spanned by
   the design (Gibbs, Cherian & Candes 2023 give the exact finite-sample version,
   which additionally augments the fit with the test point; with ~10^5 calibration
   points the difference should be negligible, but that is an assumption).
"""
import heapq

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

from .predictors import TAU_MIN


# ---------------------------------------------------------------- groups
def group_matrix(frames, dims):
    """Boolean membership matrices (one per frame) for groups:
    'all' + one group per observed value of each dimension."""
    names = ["all"]
    values = {}
    for d in dims:
        vals = sorted(set(np.concatenate([f[d].to_numpy() for f in frames]).tolist()))
        values[d] = vals
        names += [f"{d}={v}" for v in vals]
    mats = []
    for f in frames:
        cols = [np.ones(len(f), bool)]
        for d in dims:
            x = f[d].to_numpy()
            cols += [x == v for v in values[d]]
        mats.append(np.column_stack(cols))
    return mats, names


# ---------------------------------------------------------------- MVP
def _K_eps(eps):
    n = np.arange(10 ** 6, dtype=float)
    return float(np.sum(1.0 / ((n + 1) * np.log(n + 2) ** (1 + eps))) + 1 / (eps * np.log(1e6) ** eps))


class MVP:
    """scale='quantile': MVP's threshold q in [0,1] is the target coverage level itself
                         (tau = calibration-score quantile at miss level 1-q).
       scale='log'     : q in [0,1] indexes the miss level on a log grid,
                         a(q) = a_min ** q  (q=0 -> miss level 1 = search nothing,
                         q=1 -> miss level a_min). Uniform buckets in q are then fine near
                         small miss levels (e.g. 0.05) and the 'search everything' extreme is
                         capped at the a_min calibration quantile. Any monotone
                         re-parameterisation of the threshold keeps MVP's calibration logic."""

    def __init__(self, cal_scores, n_groups, alpha, m=40, r=1000, eta="theory", eps=1.0, seed=0,
                 scale="quantile", a_min=0.002, floor_level=None):
        # floor_level (post-hoc ablation, quantile scale only): miss level never below this value,
        # i.e. the same cap on the 'search everything' extreme that the log scale has via a_min
        self.scale = scale; self.a_min = float(a_min); self.floor_level = floor_level
        self.cs = np.sort(np.asarray(cal_scores))
        self.alpha = alpha
        self.m = m; self.r = r; self.eps = eps
        if eta == "theory":
            K = _K_eps(eps)
            eta = np.sqrt(np.log(n_groups * m) / (2 * K * n_groups * m))
        self.eta = float(eta)
        self.V = np.zeros((n_groups, m)); self.N = np.zeros((n_groups, m))
        self.rng = np.random.default_rng(seed)

    def q_to_tau(self, q):
        if q <= 0:
            return np.inf                       # cover nothing
        lvl = self.a_min ** q if self.scale == "log" else 1.0 - q
        if self.floor_level is not None and self.scale != "log":
            lvl = max(lvl, self.floor_level)
        k = int(np.floor(lvl * len(self.cs)))
        if k <= 0:
            return TAU_MIN                      # cover everything the predictor allows
        return max(float(self.cs[min(k, len(self.cs) - 1)]), TAU_MIN)

    def choose(self, gidx):
        V = self.V[gidx]; N = self.N[gidx]
        f = np.sqrt((N + 1) * np.log(N + 2) ** (1 + self.eps))
        z = np.clip(self.eta * V / f, -50, 50)
        C = ((np.exp(z) - np.exp(-z)) / f).sum(axis=0)       # length m
        if np.all(C > 0):
            q = 0.0
        elif np.all(C < 0):
            q = 1.0
        else:
            prod = C[:-1] * C[1:]
            j = int(np.flatnonzero(prod <= 0)[0])             # 0-based i* - 1
            a, b = abs(C[j]), abs(C[j + 1])
            p = 1.0 if (a + b) == 0 else b / (a + b)
            i_star = j + 1                                    # 1-based
            q = i_star / self.m - 1.0 / (self.r * self.m) if self.rng.random() < p else i_star / self.m
        return q

    def bucket(self, q):
        return min(int(np.floor(q * self.m)), self.m - 1)

    def update(self, gidx, q, covered):
        b = self.bucket(q)
        self.N[gidx, b] += 1
        self.V[gidx, b] += float(covered) - (1.0 - self.alpha)


def mvp_taus(scores, t_exit, t_res_hit, t_res_miss, G_test, cal_scores, cal_t, G_cal,
             alpha, feedback_mask, m=40, r=1000, eta="theory", eps=1.0, seed=0,
             scale="quantile", a_min=0.002, warm_weight=1.0, snapshot_times=None, floor_level=None):
    """Post-hoc diagnostics (defaults leave the method unchanged):
    warm_weight    : multiply the warm-start V and N by this factor before the test stream
                     (1 = as registered, 0 = start from scratch). A diagnostic ablation.
    snapshot_times : unix times at which copies of (V, N) are stored in mvp.snapshots,
                     after applying all feedback that resolved at or before that time."""
    mvp = MVP(cal_scores, G_test.shape[1], alpha, m, r, eta, eps, seed, scale, a_min, floor_level)
    # warm start on the calibration stream (immediate feedback)
    for i in np.argsort(cal_t, kind="stable"):
        g = np.flatnonzero(G_cal[i])
        q = mvp.choose(g)
        mvp.update(g, q, cal_scores[i] >= mvp.q_to_tau(q))
    if warm_weight != 1.0:
        mvp.V *= warm_weight; mvp.N *= warm_weight
    snaps = sorted(snapshot_times or []); k = 0
    mvp.snapshots = []
    n = len(scores)
    taus = np.empty(n); qs = np.empty(n)
    heap = []
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while k < len(snaps) and snaps[k] <= t:
            while heap and heap[0][0] <= snaps[k]:
                _, j = heapq.heappop(heap)
                mvp.update(np.flatnonzero(G_test[j]), qs[j], scores[j] >= taus[j])
            mvp.snapshots.append((snaps[k], mvp.V.copy(), mvp.N.copy())); k += 1
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            mvp.update(np.flatnonzero(G_test[j]), qs[j], scores[j] >= taus[j])
        g = np.flatnonzero(G_test[i])
        q = mvp.choose(g)
        qs[i] = q; taus[i] = mvp.q_to_tau(q)
        if feedback_mask[i]:
            heapq.heappush(heap, (t_res_hit[i] if scores[i] >= taus[i] else t_res_miss[i], i))
    return taus, qs, mvp


# ---------------------------------------------------------------- group QR
def _design(frames, dims):
    """intercept + reference-coded indicators per dimension (consistent across frames)."""
    cols_all = []
    levels = {d: sorted(set(np.concatenate([f[d].to_numpy() for f in frames]).tolist())) for d in dims}
    for f in frames:
        cols = [np.ones(len(f))]
        for d in dims:
            x = f[d].to_numpy()
            cols += [(x == v).astype(float) for v in levels[d][1:]]
        cols_all.append(np.column_stack(cols))
    return cols_all


def qr_group_taus(cal_df, cal_scores, test_df, dims, alpha, max_n=80000, seed=0, floor=1e-8, lp_method="highs"):
    """Fitted on log(score): tau = exp(x'beta) > 0 for every group combination
    (a linear fit on the raw scale can go negative for some combinations and then
    'search everything'). Quantiles are equivariant to monotone transforms, so the
    group-coverage property of the QR first-order conditions is unchanged.
    lp_method: scipy linprog method; the default reproduces earlier results ("highs-ipm" is much faster on
    large post-hoc fits, same optimum)."""
    Xc, Xt = _design([cal_df, test_df], dims)
    y = np.log(np.maximum(np.asarray(cal_scores, float), floor))
    if len(y) > max_n:
        idx = np.random.default_rng(seed).choice(len(y), max_n, replace=False)
        Xc, y = Xc[idx], y[idx]
    n, p = Xc.shape
    # min alpha*sum(u+) + (1-alpha)*sum(u-)  s.t.  X b + u+ - u- = y
    c = np.r_[np.zeros(p), np.full(n, alpha), np.full(n, 1 - alpha)]
    A = sparse.hstack([sparse.csr_matrix(Xc), sparse.identity(n, format="csr"),
                       -sparse.identity(n, format="csr")], format="csr")
    bounds = [(None, None)] * p + [(0, None)] * (2 * n)
    res = linprog(c, A_eq=A, b_eq=y, bounds=bounds, method=lp_method)
    if not res.success:
        raise RuntimeError(f"quantile regression failed: {res.message}")
    beta = res.x[:p]
    tau = np.exp(Xt @ beta)
    return np.maximum(tau, TAU_MIN), beta


# ---------------------------------------------------------------- QR + online group updates
def qr_ogd_taus(base_tau, scores, t_exit, t_res_hit, t_res_miss, G_test, alpha, feedback_mask,
                gamma=0.005, clip=3.0):
    """Hybrid: offline group QR gives the starting threshold; an online correction
        log tau_t(x) = log tau_QR(x) + sum_{G containing x} theta_G
    is updated with delayed/partial feedback by projected online gradient steps on the
    pinball loss:  theta_G <- clip(theta_G - gamma * (err - alpha))  for every group G
    containing the resolved transition (err = 1 if missed).
    Informal property: if the iterates stay bounded, the long-run miss rate of every
    group tends to alpha (sum over the group's rounds of (err - alpha) is bounded).
    This is the multi-group analogue of ACI; a formal guarantee for our delayed and
    partial feedback setting has NOT been established here."""
    logb = np.log(np.maximum(base_tau, 1e-300))
    theta = np.zeros(G_test.shape[1])
    n = len(scores)
    taus = np.empty(n)
    heap = []
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            err = 1.0 if scores[j] < taus[j] else 0.0
            g = G_test[j]
            theta[g] = np.clip(theta[g] - gamma * (err - alpha), -clip, clip)
        taus[i] = np.exp(logb[i] + theta[G_test[i]].sum())
        if feedback_mask[i]:
            heapq.heappush(heap, (t_res_hit[i] if scores[i] >= taus[i] else t_res_miss[i], i))
    return taus


# ---------------------------------------------------------------- QR refitted daily (confirm2 comparators, added 2026-10-13)
def qr_refit_taus(cal_df, cal_scores, cal_t_res, test_df, test_scores, t_exit, t_res_hit, t_res_miss,
                  feedback_mask, dims, alpha, refit_times, max_n=80000, seed=0, window_s=None, lp_method="highs"):
    """qr_groups refitted at fixed times (confirm2 comparators qr_groups_refit / qr_groups_refit7).

    Same model and parameters as qr_groups (qr_group_taus: log score, intercept + reference-coded indicators of
    `dims`, quantile level alpha, at most max_n rows subsampled with `seed`, LP `lp_method`). At each refit time T
    (sorted unix times; the evaluation days' 00:00 local time) the model is refitted and used for every hop with
    T <= t_exit < next T. Hops before the first refit time use the first fit.
    Fitting data at T, a labelled hop counting once its outcome is resolved (resolution time <= T):
      window_s None : every calibration hop + every feedback hop resolved by T (cumulative; qr_groups_refit)
      window_s = w  : calibration and feedback hops resolved in (T - w, T] (qr_groups_refit7: w = 7 days)
    Calibration hops resolve at cal_t_res (their arrival time at the next camera). A feedback hop (feedback_mask)
    resolves at t_res_hit if it was detected under the threshold in force for it (score >= tau), else at
    t_res_miss, as for ACI / MVP / qr_ogd; its label is test_scores (the observed score).
    Returns (taus, n_fit per refit, refit times used)."""
    test_scores = np.asarray(test_scores, float); t_exit = np.asarray(t_exit, float)
    cal_scores = np.asarray(cal_scores, float); cal_t_res = np.asarray(cal_t_res, float)
    Xc_all, Xt_all = _design([cal_df, test_df], dims)
    yc = np.log(np.maximum(cal_scores, 1e-8)); yt = np.log(np.maximum(test_scores, 1e-8))
    taus = np.full(len(test_scores), np.nan)
    t_res = np.full(len(test_scores), np.inf)          # resolution time of feedback hops (set once tau is known)
    refit_times = np.sort(np.asarray(refit_times, float))
    bounds_t = np.r_[refit_times[1:], np.inf]
    n_fit = []
    p = Xc_all.shape[1]
    for k, (T, T_next) in enumerate(zip(refit_times, bounds_t)):
        lo = -np.inf if window_s is None else T - window_s
        mc = (cal_t_res <= T) & (cal_t_res > lo) if window_s is not None else np.ones(len(yc), bool)
        mf = feedback_mask & (t_res <= T) & (t_res > lo)
        X = np.vstack([Xc_all[mc], Xt_all[mf]]); y = np.r_[yc[mc], yt[mf]]
        if len(y) > max_n:
            idx = np.random.default_rng(seed).choice(len(y), max_n, replace=False)
            X, y = X[idx], y[idx]
        n = len(y)
        c = np.r_[np.zeros(p), np.full(n, alpha), np.full(n, 1 - alpha)]
        A = sparse.hstack([sparse.csr_matrix(X), sparse.identity(n, format="csr"),
                           -sparse.identity(n, format="csr")], format="csr")
        res = linprog(c, A_eq=A, b_eq=y, bounds=[(None, None)] * p + [(0, None)] * (2 * n), method=lp_method)
        if not res.success:
            raise RuntimeError(f"quantile regression (refit {k}) failed: {res.message}")
        beta = res.x[:p]
        m = (t_exit < T_next) if k == 0 else (t_exit >= T) & (t_exit < T_next)
        taus[m] = np.maximum(np.exp(Xt_all[m] @ beta), TAU_MIN)
        fm = m & feedback_mask
        t_res[fm] = np.where(test_scores[fm] >= taus[fm], t_res_hit[fm], t_res_miss[fm])
        n_fit.append(n)
    assert not np.isnan(taus).any()
    return taus, np.array(n_fit), refit_times
