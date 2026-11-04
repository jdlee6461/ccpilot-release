"""POST HOC (external review, instruction 03 §1): diagnosis of the negative cost ratios of label set (iii).

    python posthoc_review_diag03.py

Scope (instruction 03 §1): label-set replay outputs in work/review_cache/runs/*__labels.parquet, the replay script
(posthoc_review_labels.py, 13303f6) and the cost lookup it calls; one replay unit (block1, t 0.95, seed 0) is
recomputed to dump the method state. No other results are read.
Writes review/diag03/:
  lookup_domain.csv     cost of CostLookup.cost_per_hop vs the per-key definition of VisibilityModel.cost
                        (len(v) - searchsorted(v, max(tau, TAU_MIN))) * delta on a grid of thresholds
  state_first100.csv    (iii) mvp_log q and tau, (iii) qr_ogd log tau, for the first 100 hops in t_exit order
  state_summary.csv     first hop (t_exit order) with tau = inf / tau > 1 / tau > 2, counts, replay hit = stored hit
  cost_sign_by_run.csv  per run x (iii)/(iv) method: hops, negative / zero / NaN cost counts, mean cost
"""
import numpy as np
import pandas as pd

import posthoc_review_common as C

C.threads(1)
import posthoc_review_labels as L  # noqa: E402
from ccpilot.multigroup import MVP, group_matrix, qr_group_taus  # noqa: E402
from ccpilot.predictors import TAU_MIN  # noqa: E402
from posthoc_review_methods import audit_mask, lookups  # noqa: E402

OUT = C.OUT / "diag03"
METHODS = [f"{a}_{m}" for a in ("iii", "iv") for m in ("aci", "aci_groups", "mvp_log", "qr_ogd")]


class RecMVP(MVP):
    """MVP that records every chosen q (test stream only after reset_log)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.log = None

    def choose(self, gidx):
        q = super().choose(gidx)
        if self.log is not None:
            self.log.append(q)
        return q


def lookup_domain(lk, idx):
    """idx: indices into the sorted key positions present in the block's hops"""
    z = []
    taus = np.r_[0.0, 1e-6, 0.002, 0.1, 0.5, 0.9, 0.999, 1.0, 1.5, 2.0, 2.5, 3.0, 10.0, 1e3, np.inf]
    pos = np.unique(lk.kpos)[idx]
    for p in pos:
        v = lk.glob[lk.start[p]:lk.end[p]] - 2.0 * p                      # the key's sorted probabilities
        hop = int(np.flatnonzero(lk.kpos == p)[0])
        for t in taus:
            ref = (len(v) - np.searchsorted(v, max(t, TAU_MIN), side="left")) * lk.delta
            tt = np.full(lk.kpos.shape, t)
            got = lk.cost_per_hop(tt)[hop]
            z.append({"key_position": int(p), "n_values": len(v), "v_min": float(v.min()), "v_max": float(v.max()),
                      "tau": t, "cost_definition": ref, "cost_lookup": float(got), "equal": bool(ref == got)})
    return pd.DataFrame(z)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, t, s = "block1", 0.95, 0
    lk = lookups(b)[C.PRIMARY]
    allv = lk.glob - 2.0 * np.repeat(np.arange(len(lk.start)), lk.end - lk.start)
    print("lookup values: min", allv.min(), "max", allv.max())
    D = lookup_domain(lk, np.linspace(0, len(np.unique(lk.kpos)) - 1, 5).astype(int))
    D.to_csv(OUT / "lookup_domain.csv", index=False)
    print(D.groupby("tau").equal.all().to_string())

    # ---- replay of one unit, (iii) = no audit, label only for a detected feedback hop (posthoc_review_labels.run)
    cfg = C.run_cfg(b, t, s); ex = cfg["eval"]; mg = ex["multigroup"]; alpha = C.alpha_of(cfg)
    cal = C.load_cal(b); H = C.load_hits(b, t, s); n = len(H)
    fb = H["feedback"].to_numpy().astype(bool)
    t_exit = H["t_exit"].to_numpy(); th = H["t_res_hit"].to_numpy(); tm = H["t_res_miss"].to_numpy()
    cols = ["t_exit"] + C.DIMS
    (G_cal, G_test), _ = group_matrix([cal, H[cols]], mg["dims"])
    v = next(v for v in mg["mvp_variants"] if v["name"] == "mvp_log"); o = mg["qr_ogd"]
    st = H[f"score|{C.PRIMARY}"].to_numpy(); s_cal = cal[f"score|{C.PRIMARY}"].to_numpy()
    none = np.zeros(n, bool); push = L.pusher(fb, none, "label")
    kw = dict(m=v.get("m", 40), r=v.get("r", 1000), eta=v.get("eta", "theory"), eps=v.get("eps", 1.0),
              seed=ex.get("seed", 0), scale=v.get("scale", "quantile"), a_min=v.get("a_min", 0.002))
    rec = {}
    orig = L.MVP

    class Hook(RecMVP):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); rec["mvp"] = self
    L.MVP = Hook
    try:
        # warm start choices are not logged: switch the log on at the first test-stream choice
        def mvp_run():
            m = rec
            orig_choose = Hook.choose
            calls = {"n": 0}
            n_cal = len(s_cal)

            def choose(self, gidx):
                calls["n"] += 1
                if calls["n"] == n_cal + 1:
                    self.log = []
                return orig_choose(self, gidx)
            Hook.choose = choose
            tau = L.mvp_lab(st, t_exit, th, tm, G_test, s_cal, cal["t_exit"].to_numpy(), G_cal, alpha, push, **kw)
            Hook.choose = orig_choose
            return tau, np.array(m["mvp"].log)
        tau_m, q_seq = mvp_run()
    finally:
        L.MVP = orig
    base = qr_group_taus(cal, s_cal, H[cols], mg["dims"], alpha, mg.get("qr_max_n", 80000), ex.get("seed", 0))[0]
    tau_o = L.qr_ogd_lab(base, st, t_exit, th, tm, G_test, alpha, push, o.get("gamma", 0.005), o.get("clip", 3.0))
    order = np.argsort(t_exit, kind="stable")
    assert len(q_seq) == n
    stored = pd.read_parquet(C.CACHE / "runs" / f"{b}_t0950_s{s}__labels.parquet")
    F = pd.DataFrame({"rank": np.arange(100), "hop": order[:100], "t_exit": t_exit[order[:100]],
                      "feedback": fb[order[:100]], "score": st[order[:100]],
                      "iii_mvp_log_q": q_seq[:100], "iii_mvp_log_tau": tau_m[order[:100]],
                      "iii_qr_ogd_log_tau": np.log(tau_o[order[:100]]), "iii_qr_ogd_log_base": np.log(base[order[:100]])})
    F.to_csv(OUT / "state_first100.csv", index=False)
    S = []
    for name, tau in (("iii_mvp_log", tau_m), ("iii_qr_ogd", tau_o)):
        to = tau[order]
        first = lambda m: (int(np.argmax(m)) if m.any() else None)   # noqa: E731
        c = lk.cost_per_hop(tau)
        S.append({"run": f"{b}_t0950_s{s}", "method": name, "hops": n,
                  "replay_hit_equals_stored": bool(np.array_equal((st >= tau).astype(np.int8), stored[f"hit|{name}"].to_numpy())),
                  "replay_cost_equals_stored": bool(np.array_equal(c.astype(np.float32), stored[f"cost|{name}"].to_numpy())),
                  "first_rank_tau_inf": first(np.isinf(to)), "first_rank_tau_gt1": first(to > 1),
                  "first_rank_tau_gt2": first(to > 2), "n_tau_inf": int(np.isinf(tau).sum()), "n_tau_gt1": int((tau > 1).sum()),
                  "n_tau_gt2": int((tau > 2).sum()), "n_cost_neg": int((c < 0).sum()),
                  "neg_cost_iff_tau_gt2": bool(np.array_equal(c < 0, tau > 2)),
                  "first_t_exit_tau_gt1": float(to[first(to > 1)]) if (to > 1).any() else None,
                  "t_exit_first": float(t_exit[order[0]]), "t_exit_last": float(t_exit[order[-1]]),
                  "max_log_tau": float(np.log(tau[np.isfinite(tau)]).max())})
    pd.DataFrame(S).to_csv(OUT / "state_summary.csv", index=False)
    print(pd.DataFrame(S).T.to_string())

    R = []
    for f in sorted((C.CACHE / "runs").glob("*__labels.parquet")):
        tag = f.name.split("__")[0]; bb, tt, ss = tag.split("_")
        X = pd.read_parquet(f, columns=[f"cost|{m}" for m in METHODS])
        for m in METHODS:
            c = X[f"cost|{m}"].to_numpy(np.float64)
            R.append({"block": bb, "target": int(tt[1:]) / 1000, "seed": int(ss[1:]), "method": m, "hops": len(c),
                      "n_neg": int((c < 0).sum()), "n_zero": int((c == 0).sum()), "n_nan": int(np.isnan(c).sum()),
                      "cost_mean": float(c.mean()), "cost_min": float(c.min())})
    R = pd.DataFrame(R); R.to_csv(OUT / "cost_sign_by_run.csv", index=False)
    print(R.assign(any_neg=R.n_neg > 0).groupby(["method", "target"]).agg(runs_with_neg=("any_neg", "sum"),
                                                                          n_neg=("n_neg", "sum")).to_string())


if __name__ == "__main__":
    main()
