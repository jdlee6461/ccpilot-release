"""POST HOC (external review, REVIEW_PLAN revision 4, Sean instruction 02 v02 §6.2): label sets (iii) and (iv).

    python posthoc_review_labels.py --run BLOCK T SEED
    python posthoc_review_labels.py --check-a2 BLOCK T SEED   # full-label copy of group-wise ACI = cached A2 hits (runs
                                                              #   whose A2 cache did not exist at --run time)
    python posthoc_review_labels.py --run-v BLOCK T SEED      # REVIEW_PLAN rev 5: label set (v), audit hops only

(iii) no label for failed searches: a feedback hop (stored mask F) gives a label only if it was found under the
      threshold in force for it (score >= tau); a missed feedback hop gives no label at all.
(iv)  (iii) + 5% audit: the audit set A (second draw of default_rng(seed), as in (ii); posthoc_review_methods.audit_mask)
      gives full labels (hit or miss, score) at the resolution time (hit: t_res_hit, miss: t_res_miss).
A hop without a label is skipped: no state update and no window append ("no observation"). A labelled hop updates as
in the full-feedback definition. Methods: ACI (aci_g0005 settings), group-wise ACI (A2 definition), mvp_log, qr_ogd,
primary predictor. Refit is not run here: "(iii)/(iv) refit = (i)/(ii) refit by construction" (verdict 02-1).
The functions below are post-hoc copies of calibration.aci_taus, posthoc_review_methods.aci_groups_taus,
multigroup.mvp_taus and multigroup.qr_ogd_taus with the push condition as the only change; with mode "full"
(label = F) they are the originals, checked in every run against the stored hits (aci_g0005, mvp_log, qr_ogd) and the
cached A2 hits where present.
Output: work/review_cache/runs/<tag>__labels.parquet (hit|<label>, cost|<label>), timing json in review/timing/.
Labels: iii_aci, iv_aci, iii_aci_groups, iv_aci_groups, iii_mvp_log, iv_mvp_log, iii_qr_ogd, iv_qr_ogd.
(v) (REVIEW_PLAN rev 5): only audited hops give labels (full label at the resolution time); methods group-wise ACI,
      mvp_log, qr_ogd with the same functions (push = audit[i]); the mode "full" copy is checked against the stored hits
      (mvp_log, qr_ogd) and the cached A2 hits. Output work/review_cache/runs/<tag>__labels_v.parquet (hit|v_<m>,
      cost|v_<m>), review/v_updates/<tag>.csv (label updates applied per group and method; largest |theta_G| of qr_ogd),
      timing review/timing/labels_v_<tag>.json.
"""
import argparse
import heapq
import time
from collections import deque

import numpy as np
import pandas as pd

import posthoc_review_common as C

C.threads(1)
from ccpilot.calibration import conformal_tau  # noqa: E402
from ccpilot.multigroup import MVP, group_matrix, qr_group_taus  # noqa: E402
from ccpilot.predictors import TAU_MIN  # noqa: E402
from posthoc_review_methods import ACI_CLIP, ACI_GAMMA, ACI_WINDOW, audit_mask, lookups  # noqa: E402


def pusher(fb, audit, mode):
    """returns f(i, hit) -> True if hop i gives a label (is pushed for feedback at its resolution)."""
    if mode == "full":
        return lambda i, hit: bool(fb[i])
    if mode == "v":                                                  # REVIEW_PLAN rev 5: audited hops only
        return lambda i, hit: bool(audit[i])
    return lambda i, hit: bool(audit[i] or (fb[i] and hit))


def aci_lab(s, t_exit, th, tm, s_cal, alpha, push, gamma=ACI_GAMMA, window=ACI_WINDOW, clip=ACI_CLIP):
    """calibration.aci_taus with one group; labelled hops update alpha_t and append their score."""
    n = len(s); a = alpha
    recent = deque(s_cal[-window:].tolist(), maxlen=window)
    taus = np.empty(n); heap = []
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            err = 1.0 if s[j] < taus[j] else 0.0
            a = float(np.clip(a + gamma * (alpha - err), *clip))
            recent.append(s[j])
        taus[i] = TAU_MIN if a <= 0 else conformal_tau(np.fromiter(recent, float), a)
        hit = s[i] >= taus[i]
        if push(i, hit):
            heapq.heappush(heap, (th[i] if hit else tm[i], i))
    return taus


def aci_groups_lab(s, t_exit, th, tm, G_test, s_cal, G_cal, alpha, push, gamma=ACI_GAMMA, window=ACI_WINDOW,
                   clip=ACI_CLIP):
    """posthoc_review_methods.aci_groups_taus (smallest tau_G over the hop's groups) with the label rule."""
    n, K = G_test.shape
    a_t = np.full(K, alpha)
    recent = []
    for g in range(K):
        cs = s_cal[G_cal[:, g]] if G_cal[:, g].sum() >= 50 else s_cal
        recent.append(deque(cs[-window:].tolist(), maxlen=window))
    tau_g = np.full(K, np.nan); dirty = np.ones(K, bool)
    taus = np.empty(n); heap = []
    gl = [np.flatnonzero(G_test[i]) for i in range(n)]
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            err = 1.0 if s[j] < taus[j] else 0.0
            for g in gl[j]:
                a_t[g] = float(np.clip(a_t[g] + gamma * (alpha - err), *clip))
                recent[g].append(s[j]); dirty[g] = True
        for g in gl[i]:
            if dirty[g]:
                tau_g[g] = TAU_MIN if a_t[g] <= 0 else conformal_tau(np.fromiter(recent[g], float), a_t[g])
                dirty[g] = False
        taus[i] = tau_g[gl[i]].min()
        hit = s[i] >= taus[i]
        if push(i, hit):
            heapq.heappush(heap, (th[i] if hit else tm[i], i))
    return taus


def mvp_lab(s, t_exit, th, tm, G_test, s_cal, cal_t, G_cal, alpha, push, m=40, r=1000, eta="theory", eps=1.0, seed=0,
            scale="quantile", a_min=0.002):
    """multigroup.mvp_taus (warm start on the calibration stream unchanged) with the label rule."""
    mvp = MVP(s_cal, G_test.shape[1], alpha, m, r, eta, eps, seed, scale, a_min, None)
    for i in np.argsort(cal_t, kind="stable"):
        g = np.flatnonzero(G_cal[i])
        q = mvp.choose(g)
        mvp.update(g, q, s_cal[i] >= mvp.q_to_tau(q))
    n = len(s); taus = np.empty(n); qs = np.empty(n); heap = []
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            mvp.update(np.flatnonzero(G_test[j]), qs[j], s[j] >= taus[j])
        g = np.flatnonzero(G_test[i])
        q = mvp.choose(g)
        qs[i] = q; taus[i] = mvp.q_to_tau(q)
        hit = s[i] >= taus[i]
        if push(i, hit):
            heapq.heappush(heap, (th[i] if hit else tm[i], i))
    return taus


def qr_ogd_lab(base_tau, s, t_exit, th, tm, G_test, alpha, push, gamma=0.005, clip=3.0, track=None):
    """multigroup.qr_ogd_taus with the label rule. track (dict, rev 5): receives the largest |theta_G| per group."""
    logb = np.log(np.maximum(base_tau, 1e-300))
    theta = np.zeros(G_test.shape[1])
    n = len(s); taus = np.empty(n); heap = []
    for i in np.argsort(t_exit, kind="stable"):
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            err = 1.0 if s[j] < taus[j] else 0.0
            g = G_test[j]
            theta[g] = np.clip(theta[g] - gamma * (err - alpha), -clip, clip)
            if track is not None:
                track["max_abs_theta"] = np.maximum(track.get("max_abs_theta", 0.0), np.abs(theta))
        taus[i] = np.exp(logb[i] + theta[G_test[i]].sum())
        hit = s[i] >= taus[i]
        if push(i, hit):
            heapq.heappush(heap, (th[i] if hit else tm[i], i))
    return taus


def applied_updates(tau, s, t_exit, th, tm, labelled, G_test):
    """label updates applied per group: labelled hops whose resolution time is reached by a later hop's exit
    (the heap is emptied only when a hop with t_exit >= resolution time is processed)."""
    res = np.where(s >= tau, th, tm)
    done = labelled & (res <= t_exit.max())
    return np.asarray(G_test[done].sum(0)).ravel()


TAU_CAP = 1.5     # above every probability (<= 1): cost 0, as VisibilityModel.cost gives for any tau > max p


def hop_cost(lk, tau):
    """CostLookup.cost_per_hop with tau capped at TAU_CAP (REVIEW deviation R3). The lookup stores key i's sorted
    probabilities offset by 2i in one array, so a threshold above 2 (tau = inf from MVP.q_to_tau(q <= 0), or qr_ogd's
    exp(log tau_QR + sum theta) > 2) reached into later keys and gave negative counts. Unchanged for tau <= 2."""
    return lk.cost_per_hop(np.minimum(np.asarray(tau, float), TAU_CAP))


def run(block, t, s):
    T0 = time.time(); tim = {}
    cfg = C.run_cfg(block, t, s); ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    cal = C.load_cal(block); H = C.load_hits(block, t, s); n = len(H)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    cols = ["t_exit"] + C.DIMS
    (G_cal, G_test), _ = group_matrix([cal, H[cols]], mg["dims"])
    v = next(v for v in mg["mvp_variants"] if v["name"] == "mvp_log"); o = mg["qr_ogd"]
    P = C.PRIMARY; s_cal = cal[f"score|{P}"].to_numpy(); st = H[f"score|{P}"].to_numpy()
    audit = audit_mask(s, n, fb); none = np.zeros(n, bool)
    lk = lookups(block)[P]
    base = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))[0]
    kw = dict(m=v.get("m", 40), r=v.get("r", 1000), eta=v.get("eta", "theory"), eps=v.get("eps", 1.0),
              seed=ex.get("seed", 0), scale=v.get("scale", "quantile"), a_min=v.get("a_min", 0.002))
    meth = {
        "aci": lambda pu: aci_lab(st, t_exit, th, tm, s_cal, alpha, pu),
        "aci_groups": lambda pu: aci_groups_lab(st, t_exit, th, tm, G_test, s_cal, G_cal, alpha, pu),
        "mvp_log": lambda pu: mvp_lab(st, t_exit, th, tm, G_test, s_cal, cal["t_exit"].to_numpy(), G_cal, alpha, pu, **kw),
        "qr_ogd": lambda pu: qr_ogd_lab(base, st, t_exit, th, tm, G_test, alpha, pu, o.get("gamma", 0.005), o.get("clip", 3.0)),
    }
    stored = {"aci": H[f"hit|{P}|aci_g0005"].to_numpy(), "mvp_log": H[f"hit|{P}|mvp_log"].to_numpy(),
              "qr_ogd": H[f"hit|{P}|qr_ogd"].to_numpy()}
    cache = C.CACHE / "runs" / f"{block}_t{int(round(t * 1000)):04d}_s{s}.parquet"
    if cache.exists():
        stored["aci_groups"] = pd.read_parquet(cache, columns=["hit|A2_aci_groups"]).iloc[:, 0].to_numpy()
    out = {}
    for name, f in meth.items():
        t1 = time.time()
        full = (st >= f(pusher(fb, none, "full"))).astype(np.int8)
        tim[f"copy_bitwise|{name}"] = bool(np.array_equal(full, stored[name])) if name in stored else "no stored reference"
        for lab, aud in (("iii", none), ("iv", audit)):
            tau = f(pusher(fb, aud, "label"))
            out[f"hit|{lab}_{name}"] = (st >= tau).astype(np.int8)
            out[f"cost|{lab}_{name}"] = hop_cost(lk, tau).astype(np.float32)
        tim[f"seconds|{name}"] = round(time.time() - t1, 1)
    tim["n_feedback"] = int(fb.sum()); tim["n_audit"] = int(audit.sum())
    tag = f"{block}_t{int(round(t * 1000)):04d}_s{s}"
    (C.CACHE / "runs").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out).to_parquet(C.CACHE / "runs" / f"{tag}__labels.parquet")
    tim["seconds_total"] = round(time.time() - T0, 1)
    C.write_json(tim, C.OUT / "timing" / f"labels_{tag}.json")
    print(tag, tim, flush=True)


def run_v(block, t, s):
    """REVIEW_PLAN rev 5, label set (v): group-wise ACI, mvp_log, qr_ogd updated on audited hops only."""
    T0 = time.time(); tim = {}
    cfg = C.run_cfg(block, t, s); ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    cal = C.load_cal(block); H = C.load_hits(block, t, s); n = len(H)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    cols = ["t_exit"] + C.DIMS
    (G_cal, G_test), names = group_matrix([cal, H[cols]], mg["dims"])
    v = next(v for v in mg["mvp_variants"] if v["name"] == "mvp_log"); o = mg["qr_ogd"]
    P = C.PRIMARY; s_cal = cal[f"score|{P}"].to_numpy(); st = H[f"score|{P}"].to_numpy()
    audit = audit_mask(s, n, fb); none = np.zeros(n, bool)
    lk = lookups(block)[P]
    base = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))[0]
    kw = dict(m=v.get("m", 40), r=v.get("r", 1000), eta=v.get("eta", "theory"), eps=v.get("eps", 1.0),
              seed=ex.get("seed", 0), scale=v.get("scale", "quantile"), a_min=v.get("a_min", 0.002))
    track = {}
    meth = {
        "aci_groups": lambda pu, tr=None: aci_groups_lab(st, t_exit, th, tm, G_test, s_cal, G_cal, alpha, pu),
        "mvp_log": lambda pu, tr=None: mvp_lab(st, t_exit, th, tm, G_test, s_cal, cal["t_exit"].to_numpy(), G_cal, alpha,
                                               pu, **kw),
        "qr_ogd": lambda pu, tr=None: qr_ogd_lab(base, st, t_exit, th, tm, G_test, alpha, pu, o.get("gamma", 0.005),
                                                 o.get("clip", 3.0), track=tr),
    }
    stored = {"mvp_log": H[f"hit|{P}|mvp_log"].to_numpy(), "qr_ogd": H[f"hit|{P}|qr_ogd"].to_numpy()}
    cache = C.CACHE / "runs" / f"{block}_t{int(round(t * 1000)):04d}_s{s}.parquet"
    if cache.exists():
        stored["aci_groups"] = pd.read_parquet(cache, columns=["hit|A2_aci_groups"]).iloc[:, 0].to_numpy()
    out, upd = {}, {"group": [str(x) for x in names]}
    for name, f in meth.items():
        t1 = time.time()
        full = (st >= f(pusher(fb, none, "full"))).astype(np.int8)
        tim[f"copy_bitwise|{name}"] = bool(np.array_equal(full, stored[name])) if name in stored else "no stored reference"
        tau = f(pusher(fb, audit, "v"), track if name == "qr_ogd" else None)
        out[f"hit|v_{name}"] = (st >= tau).astype(np.int8)
        out[f"cost|v_{name}"] = hop_cost(lk, tau).astype(np.float32)
        upd[f"n_updates|{name}"] = applied_updates(tau, st, t_exit, th, tm, audit, G_test)
        tim[f"seconds|{name}"] = round(time.time() - t1, 1)
    upd["max_abs_theta|qr_ogd"] = track.get("max_abs_theta", np.zeros(G_test.shape[1]))
    tim["n_feedback"] = int(fb.sum()); tim["n_audit"] = int(audit.sum())
    tag = f"{block}_t{int(round(t * 1000)):04d}_s{s}"
    (C.CACHE / "runs").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out).to_parquet(C.CACHE / "runs" / f"{tag}__labels_v.parquet")
    (C.OUT / "v_updates").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(upd).to_csv(C.OUT / "v_updates" / f"{tag}.csv", index=False)
    tim["seconds_total"] = round(time.time() - T0, 1)
    C.write_json(tim, C.OUT / "timing" / f"labels_v_{tag}.json")
    print(tag, tim, flush=True)


def check_a2(block, t, s):
    cfg = C.run_cfg(block, t, s); ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    cal = C.load_cal(block); H = C.load_hits(block, t, s); n = len(H)
    fb = H["feedback"].to_numpy().astype(bool)
    (G_cal, G_test), _ = group_matrix([cal, H[["t_exit"] + C.DIMS]], mg["dims"])
    P = C.PRIMARY; st = H[f"score|{P}"].to_numpy()
    tau = aci_groups_lab(st, H["t_exit"].to_numpy(), H["t_res_hit"].to_numpy(), H["t_res_miss"].to_numpy(), G_test,
                         cal[f"score|{P}"].to_numpy(), G_cal, alpha, pusher(fb, np.zeros(n, bool), "full"))
    tag = f"{block}_t{int(round(t * 1000)):04d}_s{s}"
    ref = pd.read_parquet(C.CACHE / "runs" / f"{tag}.parquet", columns=["hit|A2_aci_groups"]).iloc[:, 0].to_numpy()
    ok = bool(np.array_equal((st >= tau).astype(np.int8), ref))
    f = C.OUT / "timing" / f"labels_{tag}.json"
    import json
    d = json.load(open(f)); d["copy_bitwise|aci_groups"] = ok; d["copy_bitwise|aci_groups_checked_later"] = True
    C.write_json(d, f)
    print(tag, "aci_groups copy bitwise:", ok, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs=3)
    ap.add_argument("--check-a2", nargs=3)
    ap.add_argument("--run-v", nargs=3)
    a = ap.parse_args()
    if a.run:
        run(a.run[0], float(a.run[1]), int(a.run[2]))
    if a.run_v:
        run_v(a.run_v[0], float(a.run_v[1]), int(a.run_v[2]))
    if a.check_a2:
        check_a2(a.check_a2[0], float(a.check_a2[1]), int(a.check_a2[2]))


if __name__ == "__main__":
    main()
