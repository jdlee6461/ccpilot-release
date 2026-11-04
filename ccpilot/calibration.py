"""Threshold selection ('calibration layer') on top of any scoring predictor.

A transition is covered iff score >= tau. With calibration scores s_1..s_n,
    tau = s_(k),  k = floor(alpha * (n + 1))
gives P(miss) <= k/(n+1) <= alpha under exchangeability (split conformal).
This is the same as 'tuning the threshold on validation data' up to the
finite-sample correction -- by design; it is the baseline the adaptive
methods must beat under distribution shift.

Methods
  static       : one tau from the calibration period.
  mondrian     : one tau per hour group (anticipated, recurring shifts).
  aci          : adaptive conformal inference (Gibbs & Candes, 2021):
                 alpha_{t+1} = alpha_t + gamma * (alpha - err_t),
                 tau_t = quantile of a sliding window of recent resolved scores.
                 Feedback err_t becomes available only when the outcome is
                 resolved (arrival time if hit, t_exit + T_max if miss), and
                 only for a random fraction of background transitions.
  mondrian_aci : aci run separately per hour group.

Variant knobs (config eval.aci_variants): gamma (step size), alpha_floor
(lower bound on alpha_t; alpha_floor > 0 prevents 'search everything' spikes,
which inflate mean cost because cost is convex in alpha), and groups.
"""
import heapq
from collections import deque

import numpy as np

from .predictors import TAU_MIN


def conformal_tau(scores, alpha):
    s = np.sort(np.asarray(scores))
    n = len(s)
    if n == 0:
        return TAU_MIN
    if alpha >= 1:
        return np.inf
    k = int(np.floor(alpha * (n + 1)))
    if k < 1:
        return TAU_MIN
    return max(float(s[k - 1]), TAU_MIN)


def static_taus(cal_scores, n_test, alpha):
    return np.full(n_test, conformal_tau(cal_scores, alpha))


def mondrian_taus(cal_scores, cal_groups, test_groups, alpha, min_n=50):
    glob = conformal_tau(cal_scores, alpha)
    out = np.empty(len(test_groups))
    for g in np.unique(test_groups):
        m = cal_groups == g
        tau = conformal_tau(cal_scores[m], alpha) if m.sum() >= min_n else glob
        out[test_groups == g] = tau
    return out


def aci_taus(test_scores, test_t_exit, test_t_resolve_hit, test_t_resolve_miss,
             test_groups, cal_scores, cal_groups, alpha, gamma, window,
             feedback_mask, alpha_clip=(-0.5, 1.0)):
    """Online thresholds, processed in order of t_exit. Returns (taus, alpha_trace)."""
    n = len(test_scores)
    order = np.argsort(test_t_exit, kind="stable")
    groups = np.unique(np.r_[test_groups, cal_groups])
    a_t = {g: alpha for g in groups}
    recent = {}
    for g in groups:
        cs = cal_scores[cal_groups == g] if (cal_groups == g).sum() >= 50 else cal_scores
        recent[g] = deque(cs[-window:].tolist(), maxlen=window)
    taus = np.empty(n); a_trace = np.empty(n)
    heap = []
    for i in order:
        t = test_t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            g = test_groups[j]
            err = 1.0 if test_scores[j] < taus[j] else 0.0
            a_t[g] = float(np.clip(a_t[g] + gamma * (alpha - err), *alpha_clip))
            recent[g].append(test_scores[j])
        g = test_groups[i]
        a = a_t[g]
        tau = TAU_MIN if a <= 0 else conformal_tau(np.fromiter(recent[g], float), a)
        taus[i] = tau; a_trace[i] = a
        if feedback_mask[i]:
            t_res = test_t_resolve_hit[i] if test_scores[i] >= tau else test_t_resolve_miss[i]
            heapq.heappush(heap, (t_res, i))
    return taus, a_trace
