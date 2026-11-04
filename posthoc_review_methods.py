"""POST HOC (external review): per-run thresholds of the new methods (REVIEW_PLAN.md parts A, B without refits, C).

    python posthoc_review_methods.py --run BLOCK T SEED [--parts A,B,C]   # one stored confirm2 run
    python posthoc_review_methods.py --cells                              # A(1) cell table (calibration counts, merges)

Inputs (read only): the stored run (hits.parquet: evaluation scores, groups, feedback, resolution times) and the P0 cache
(work/review_cache/<block>/cal.parquet, cost lookups). Output: work/review_cache/runs/<block>_tXXXX_sK.parquet with
hit|<label> (int8) and cost|<label> (float32) per new method, and a timing json in review/timing/.
Labels:
  A1_mondrian_small, A2_aci_groups, A3_qr_groups_inter                         (primary predictor)
  Bi_aci, Bii_aci, Bii_mvp_log, Bii_qr_ogd                                     (primary predictor)
  C_<predictor>_<method> for predictor in src, src_zone, src_zone_hour; method in qr_groups, mvp_log, qr_ogd
"""
import argparse
import heapq
import time
from collections import deque

import numpy as np
import pandas as pd

import posthoc_review_common as C

C.threads(1)
from scipy import sparse  # noqa: E402
from scipy.optimize import linprog  # noqa: E402

from ccpilot.calibration import aci_taus, conformal_tau, mondrian_taus  # noqa: E402
from ccpilot.evaluate import _group_ids  # noqa: E402
from ccpilot.multigroup import _design, group_matrix, mvp_taus, qr_group_taus, qr_ogd_taus  # noqa: E402
from ccpilot.predictors import TAU_MIN  # noqa: E402
from confirm2_analysis import INTER, CostLookup  # noqa: E402

AUDIT_FRACTION = 0.05
ACI_GAMMA, ACI_WINDOW, ACI_CLIP = 0.0005, 2000, (-0.5, 1.0)        # aci_g0005 settings


# ---------------------------------------------------------------- A(1) small Mondrian
def small_mondrian_cells(cal, min_n=200):
    """original cell key = 4*hopkind + 2*[entropy_bin = 3] + [nn_bin = 3]; returns (key -> final cell, table)."""
    key = 4 * cal["hopkind"].to_numpy() + 2 * (cal["entropy_bin"].to_numpy() == 3) + (cal["nn_bin"].to_numpy() == 3)
    n = {k: int((key == k).sum()) for k in range(12)}
    cell = {}
    for hk in (0, 1, 2):
        ks = [4 * hk + j for j in range(4)]
        if hk == 2:                                       # re-acquired: always one cell
            for k in ks:
                cell[k] = f"hk2"
            continue
        small = [k for k in ks if n[k] < min_n]
        for k in ks:
            cell[k] = f"hk{hk}_{k % 4}"
        if small:
            ms = sum(n[k] for k in small)
            if ms < min_n:                                # still small: merge into the largest cell of the track state
                big = max((k for k in ks if k not in small), key=lambda k: n[k])
                for k in small:
                    cell[k] = cell[big]
            else:
                for k in small:
                    cell[k] = f"hk{hk}_merged"
    T = pd.DataFrame({"key": range(12), "hopkind": [k // 4 for k in range(12)],
                      "branching_q4": [(k % 4) // 2 for k in range(12)], "isolation_q4": [k % 2 for k in range(12)],
                      "n_cal": [n[k] for k in range(12)], "cell": [cell[k] for k in range(12)]})
    T["n_cal_cell"] = T.groupby("cell").n_cal.transform("sum")
    T["global_fallback"] = T.n_cal_cell < min_n
    return cell, T


def cell_ids(df, cell):
    key = 4 * df["hopkind"].to_numpy() + 2 * (df["entropy_bin"].to_numpy() == 3) + (df["nn_bin"].to_numpy() == 3)
    names = sorted(set(cell.values()))
    return np.array([names.index(cell[int(k)]) for k in key])


# ---------------------------------------------------------------- A(2) group-wise ACI
def aci_groups_taus(s_test, t_exit, th, tm, G_test, s_cal, G_cal, alpha, gamma, window, fb, clip=ACI_CLIP):
    """one ACI state per group (alpha_t, window of `window` scores); applied threshold = min tau_G over the hop's groups;
    at resolution every group of the hop updates alpha_t with err = 1{score < applied tau} and appends the score."""
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
            err = 1.0 if s_test[j] < taus[j] else 0.0
            for g in gl[j]:
                a_t[g] = float(np.clip(a_t[g] + gamma * (alpha - err), *clip))
                recent[g].append(s_test[j]); dirty[g] = True
        for g in gl[i]:
            if dirty[g]:
                tau_g[g] = TAU_MIN if a_t[g] <= 0 else conformal_tau(np.fromiter(recent[g], float), a_t[g])
                dirty[g] = False
        taus[i] = tau_g[gl[i]].min()
        if fb[i]:
            heapq.heappush(heap, (th[i] if s_test[i] >= taus[i] else tm[i], i))
    return taus


# ---------------------------------------------------------------- A(3) qr_groups + intersections
def inter_cols(df):
    out = []
    for nm, cond in INTER.items():
        m = np.ones(len(df), bool)
        for d, v in cond:
            m &= df[d].to_numpy() == v
        out.append(m.astype(float))
    return np.column_stack(out)


def qr_inter_taus(cal_df, cal_scores, test_df, dims, alpha, max_n=80000, seed=0, floor=1e-8, lp_method="highs"):
    """post-hoc copy of multigroup.qr_group_taus with the indicators of I1-I6 added to the design."""
    Xc, Xt = _design([cal_df, test_df], dims)
    Xc = np.column_stack([Xc, inter_cols(cal_df)]); Xt = np.column_stack([Xt, inter_cols(test_df)])
    y = np.log(np.maximum(np.asarray(cal_scores, float), floor))
    if len(y) > max_n:
        idx = np.random.default_rng(seed).choice(len(y), max_n, replace=False)
        Xc, y = Xc[idx], y[idx]
    n, p = Xc.shape
    c = np.r_[np.zeros(p), np.full(n, alpha), np.full(n, 1 - alpha)]
    A = sparse.hstack([sparse.csr_matrix(Xc), sparse.identity(n, format="csr"), -sparse.identity(n, format="csr")],
                      format="csr")
    res = linprog(c, A_eq=A, b_eq=y, bounds=[(None, None)] * p + [(0, None)] * (2 * n), method=lp_method)
    if not res.success:
        raise RuntimeError(f"quantile regression failed: {res.message}")
    return np.maximum(np.exp(Xt @ res.x[:p]), TAU_MIN)


# ---------------------------------------------------------------- B: censored ACI
def aci_censored_taus(s_test, t_exit, th, tm, g_test, s_cal, g_cal, alpha, gamma, window, fb, reveal_all, clip=ACI_CLIP):
    """post-hoc copy of calibration.aci_taus where a resolved feedback hop appends its score to the window only if it is
    revealed: detected (score >= tau) or reveal_all[j] (audited). alpha_t uses the miss indicator of every feedback hop.
    With reveal_all = True everywhere this is aci_taus."""
    n = len(s_test)
    order = np.argsort(t_exit, kind="stable")
    groups = np.unique(np.r_[g_test, g_cal])
    a_t = {g: alpha for g in groups}
    recent = {}
    for g in groups:
        cs = s_cal[g_cal == g] if (g_cal == g).sum() >= 50 else s_cal
        recent[g] = deque(cs[-window:].tolist(), maxlen=window)
    taus = np.empty(n); heap = []
    for i in order:
        t = t_exit[i]
        while heap and heap[0][0] <= t:
            _, j = heapq.heappop(heap)
            g = g_test[j]
            hit = s_test[j] >= taus[j]
            a_t[g] = float(np.clip(a_t[g] + gamma * (alpha - (0.0 if hit else 1.0)), *clip))
            if hit or reveal_all[j]:
                recent[g].append(s_test[j])
        g = g_test[i]; a = a_t[g]
        taus[i] = TAU_MIN if a <= 0 else conformal_tau(np.fromiter(recent[g], float), a)
        if fb[i]:
            heapq.heappush(heap, (th[i] if s_test[i] >= taus[i] else tm[i], i))
    return taus


def audit_mask(seed, n, fb_stored):
    rng = np.random.default_rng(seed)
    fb = rng.random(n) < 0.3                          # first draw = the stored feedback mask (checked)
    assert np.array_equal(fb, fb_stored), "feedback mask not reproduced from the evaluation seed"
    return rng.random(n) < AUDIT_FRACTION             # second draw


# ---------------------------------------------------------------- per run
def lookups(block):
    out = {}
    for p in C.PREDICTORS:
        if p == C.PRIMARY:
            kid = C.load_hits(block, 0.95, 0, columns=[f"kid|{p}"])[f"kid|{p}"].to_numpy()
            out[p] = CostLookup(C.run_dir(block, 0.95, 0) / f"cost_lookup_{p}.npz", kid)
        else:
            out[p] = CostLookup(C.CACHE / block / f"cost_lookup_{p}.npz", np.load(C.CACHE / block / f"kid_{p}.npy"))
    return out


def run(block, t, s, parts):
    T0 = time.time(); tim = {}
    cfg = C.run_cfg(block, t, s); ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    assert ex["seed"] == s and abs(ex["target_recall"] - t) < 1e-9
    cal = C.load_cal(block)
    H = C.load_hits(block, t, s)
    n = len(H)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    cols = ["t_exit"] + C.DIMS
    (G_cal, G_test), _ = group_matrix([cal, H[cols]], mg["dims"])
    v = next(v for v in mg["mvp_variants"] if v["name"] == "mvp_log")
    o = mg["qr_ogd"]
    lk = lookups(block)
    out = {}

    def put(label, pred, tau, s_test):
        out[f"hit|{label}"] = (s_test >= tau).astype(np.int8)
        out[f"cost|{label}"] = lk[pred].cost_per_hop(tau).astype(np.float32)

    def mvp(s_test, s_cal, fbm):
        return mvp_taus(s_test, t_exit, th, tm, G_test, s_cal, cal["t_exit"].to_numpy(), G_cal, alpha, fbm,
                        m=v.get("m", 40), r=v.get("r", 1000), eta=v.get("eta", "theory"), eps=v.get("eps", 1.0),
                        seed=ex.get("seed", 0), scale=v.get("scale", "quantile"), a_min=v.get("a_min", 0.002))[0]

    P = C.PRIMARY
    s_cal = cal[f"score|{P}"].to_numpy(); s_test = H[f"score|{P}"].to_numpy()
    if "A" in parts:
        t1 = time.time()
        cell, _ = small_mondrian_cells(cal)
        put("A1_mondrian_small", P, mondrian_taus(s_cal, cell_ids(cal, cell), cell_ids(H, cell), alpha, 200), s_test)
        tim["A1"] = time.time() - t1; t1 = time.time()
        put("A2_aci_groups", P, aci_groups_taus(s_test, t_exit, th, tm, G_test, s_cal, G_cal, alpha, ACI_GAMMA,
                                                ACI_WINDOW, fb), s_test)
        tim["A2"] = time.time() - t1; t1 = time.time()
        put("A3_qr_groups_inter", P, qr_inter_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000),
                                                   ex.get("seed", 0)), s_test)
        tim["A3"] = time.time() - t1
    if "B" in parts:
        t1 = time.time()
        audit = audit_mask(s, n, fb)
        g0c, g0t = np.zeros(len(cal), int), np.zeros(n, int)
        # copy check: with every hop revealed the copy is aci_g0005
        tau_full = aci_censored_taus(s_test, t_exit, th, tm, g0t, s_cal, g0c, alpha, ACI_GAMMA, ACI_WINDOW, fb,
                                     np.ones(n, bool))
        tim["B_aci_copy_bitwise"] = bool(np.array_equal((s_test >= tau_full).astype(np.int8),
                                                        H[f"hit|{P}|aci_g0005"].to_numpy()))
        put("Bi_aci", P, aci_censored_taus(s_test, t_exit, th, tm, g0t, s_cal, g0c, alpha, ACI_GAMMA, ACI_WINDOW, fb,
                                           np.zeros(n, bool)), s_test)
        fb2 = fb | audit
        put("Bii_aci", P, aci_censored_taus(s_test, t_exit, th, tm, g0t, s_cal, g0c, alpha, ACI_GAMMA, ACI_WINDOW, fb2,
                                            audit), s_test)
        tim["B_aci"] = time.time() - t1; t1 = time.time()
        put("Bii_mvp_log", P, mvp(s_test, s_cal, fb2), s_test)
        base = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))[0]
        put("Bii_qr_ogd", P, qr_ogd_taus(base, s_test, t_exit, th, tm, G_test, alpha, fb2, o.get("gamma", 0.005),
                                         o.get("clip", 3.0)), s_test)
        tim["B_online"] = time.time() - t1
        tim["n_audit"] = int(audit.sum()); tim["n_audit_outside_fb"] = int((audit & ~fb).sum())
    if "C" in parts:
        for p in ("src", "src_zone", "src_zone_hour"):
            t1 = time.time()
            sc = cal[f"score|{p}"].to_numpy(); st = H[f"score|{p}"].to_numpy()
            base = qr_group_taus(cal, sc, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))[0]
            put(f"C_{p}_qr_groups", p, base, st)
            put(f"C_{p}_mvp_log", p, mvp(st, sc, fb), st)
            put(f"C_{p}_qr_ogd", p, qr_ogd_taus(base, st, t_exit, th, tm, G_test, alpha, fb, o.get("gamma", 0.005),
                                                o.get("clip", 3.0)), st)
            tim[f"C_{p}"] = time.time() - t1
        # copy check for the C path: src_zone_speed qr_ogd recomputed = stored
        p = "src_zone_speed"; sc = cal[f"score|{p}"].to_numpy(); st = H[f"score|{p}"].to_numpy()
        base = qr_group_taus(cal, sc, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))[0]
        q = qr_ogd_taus(base, st, t_exit, th, tm, G_test, alpha, fb, o.get("gamma", 0.005), o.get("clip", 3.0))
        tim["C_qr_ogd_copy_bitwise"] = bool(np.array_equal((st >= q).astype(np.int8), H[f"hit|{p}|qr_ogd"].to_numpy()))
    # lookup check: cost from the lookup at the static threshold = stored cost column (float32), every predictor
    for p in C.PREDICTORS:
        tau_static = np.full(n, conformal_tau(cal[f"score|{p}"].to_numpy(), alpha))
        tim[f"cost_lookup_static_bitwise|{p}"] = bool(np.array_equal(
            lk[p].cost_per_hop(tau_static).astype(np.float32), H[f"cost|{p}|static"].to_numpy()))
    tag = f"{block}_t{int(round(t * 1000)):04d}_s{s}"
    (C.CACHE / "runs").mkdir(parents=True, exist_ok=True)
    f = C.CACHE / "runs" / f"{tag}.parquet"
    old = pd.read_parquet(f) if f.exists() else pd.DataFrame(index=range(n))
    for k, x in out.items():
        old[k] = x
    old.to_parquet(f)
    tim["seconds_total"] = time.time() - T0
    C.write_json(tim, C.OUT / "timing" / f"methods_{tag}_{''.join(sorted(parts))}.json")
    print(tag, {k: (round(x, 1) if isinstance(x, float) else x) for k, x in tim.items()}, flush=True)


def cells():
    rows = []
    for b in C.BLOCKS:
        _, T = small_mondrian_cells(C.load_cal(b))
        T.insert(0, "block", b); rows.append(T)
    D = pd.concat(rows, ignore_index=True)
    D.to_csv(C.OUT / "A1_mondrian_cells.csv", index=False)
    print(D.to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs=3)
    ap.add_argument("--parts", default="A,B,C")
    ap.add_argument("--cells", action="store_true")
    a = ap.parse_args()
    if a.cells:
        cells()
    if a.run:
        run(a.run[0], float(a.run[1]), int(a.run[2]), set(a.parts.split(",")))


if __name__ == "__main__":
    main()
