"""POST HOC (external review): estimates and cluster-bootstrap intervals for any set of per-hop method outcomes.

Estimands (REVIEW_PLAN.md, confirm2 definitions): D (worst deficit over the judged 25 groups), re-acquisition deficit d
(hopkind=2), isolation-Q4 deficit (nn_bin=3), mean cost, cost relative to H2 (single threshold on the same predictor's
scores with overall recall >= the method's realised recall, per block, method and seed); every estimand per seed, then
mean over seeds. Intervals: 95%, B = 2,000, clusters taxi (joint over blocks) and day (within block), conservative
combination; weights drawn exactly as in confirm2_analysis.py (bootstrap seed 20261013; the B = 10,000 main draws are
generated first and discarded, so the B = 2,000 weights are the ones the confirm2 analysis used for its 95% intervals).
Descriptive differences Delta = D_comparator - D_reference (reference in {mvp_log, qr_ogd} or as given).
No §10.8 judgement wording (no classes).
"""
import numpy as np
import pandas as pd

import posthoc_review_common as C
from confirm2_analysis import CostLookup, INTER, TZ, pct, single_tau
from ccpilot.predictors import TAU_MIN

DIMS25 = ["grp_all"] + C.DIMS
B_MAIN, B_OTHER, LEVEL, BOOT_SEED, MIN_N = 10000, 2000, 0.95, 20261013, 200


def cost_per_key_many(lk, taus):
    """CostLookup.cost_per_key for several thresholds at once (keys x thresholds); same arithmetic per element."""
    t = np.maximum(np.asarray(taus, float), TAU_MIN)
    q = 2.0 * lk.ukid[:, None] + t[None, :]
    return (lk.end[lk.ukid][:, None] - np.searchsorted(lk.glob, q.ravel(), side="left").reshape(q.shape)) * lk.delta


class Base:
    """hops of both blocks (order of the stored hits.parquet), cells (25 groups + I1-I6), clusters, bootstrap weights."""

    def __init__(self, taxi_map="work/porto_cctv_confirm2/taxi_map.parquet", blocks=None):
        self.blocks = list(blocks or C.BLOCKS)     # a subset (e.g. block1 only) for the seed-0 left-censored trial
        tm = pd.read_parquet(taxi_map).set_index("trip_id").taxi_id
        self.H0, taxi, day, bid = [], [], [], []
        for i, b in enumerate(self.blocks):
            H = C.load_hits(b, 0.95, 0, columns=["tr_id", "trip_id", "t_exit"] + DIMS25)
            self.H0.append(H)
            tx = tm.reindex(H.trip_id).to_numpy(); assert not pd.isna(tx).any()
            taxi.append(tx)
            d = pd.to_datetime(H.t_exit, unit="s", utc=True).dt.tz_convert(TZ).dt.date.astype(str).to_numpy()
            day.append(np.array([f"{b}:{x}" for x in d])); bid.append(np.full(len(H), i))
        self.nb = [len(h) for h in self.H0]; self.off = np.r_[0, np.cumsum(self.nb)]
        self.bid = np.concatenate(bid)
        Hc = pd.concat(self.H0, ignore_index=True)
        cells = []
        for d in DIMS25:
            for v in sorted(Hc[d].unique()):
                cells.append((f"{d}={int(v)}", Hc[d].to_numpy() == v))
        self.n25 = len(cells)
        for nm, cond in INTER.items():
            m = np.ones(len(Hc), bool)
            for d, v in cond:
                m &= Hc[d].to_numpy() == v
            cells.append((nm, m))
        self.cname = [c for c, _ in cells]
        self.CM = np.column_stack([m for _, m in cells]).astype(np.float64)
        self.reacq = self.cname.index("hopkind=2"); self.isoq4 = self.cname.index("nn_bin=3")
        self.codes = {"taxi": pd.factorize(np.concatenate(taxi))[0], "day": pd.factorize(np.concatenate(day))[0]}
        day_block = np.zeros(self.codes["day"].max() + 1, int); day_block[self.codes["day"]] = self.bid
        rng = np.random.default_rng(BOOT_SEED)

        def weights(c, B):
            Cn = self.codes[c].max() + 1
            if c == "taxi":
                return rng.multinomial(Cn, np.full(Cn, 1 / Cn), size=B).astype(np.float64)
            W = np.zeros((B, Cn))
            for bi in range(len(self.blocks)):
                idx = np.flatnonzero(day_block == bi)
                W[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=B)
            return W
        _ = {c: weights(c, B_MAIN) for c in self.codes}          # main draws (discarded), as in confirm2_analysis
        self.W = {c: weights(c, B_OTHER) for c in self.codes}
        self.scopes = {"combined": np.ones(len(self.bid), bool)}
        self.scopes.update({b: self.bid == i for i, b in enumerate(self.blocks)})
        self._pred = {}

    def predictor(self, p):
        """per block: scores (descending order) and cost lookup of predictor p."""
        if p not in self._pred:
            out = []
            for i, b in enumerate(self.blocks):
                s = C.load_hits(b, 0.95, 0, columns=[f"score|{p}"])[f"score|{p}"].to_numpy()
                if p == C.PRIMARY:
                    kid = C.load_hits(b, 0.95, 0, columns=[f"kid|{p}"])[f"kid|{p}"].to_numpy()
                    lk = CostLookup(C.run_dir(b, 0.95, 0) / f"cost_lookup_{p}.npz", kid)
                else:
                    lk = CostLookup(C.CACHE / b / f"cost_lookup_{p}.npz", np.load(C.CACHE / b / f"kid_{p}.npy"))
                o = np.argsort(-s, kind="stable")
                out.append({"score": s, "o": o, "sd": s[o], "lk": lk})
            self._pred[p] = out
        return self._pred[p]


def summarize(base, predictor, get, methods, targets, seeds=C.SEEDS, refs=("mvp_log", "qr_ogd"), label=""):
    """get(method, block, t, s) -> (hit, cost) arrays over the block's hops (stored order).
    Returns (estimates, differences, cells) data frames."""
    P = base.predictor(predictor)
    est, dif, cel = [], [], []
    for t in targets:
        M = list(methods); S = len(seeds)
        hit = np.zeros((len(base.bid), len(M), S)); cost = np.zeros_like(hit)
        for mi, m in enumerate(M):
            for si, s in enumerate(seeds):
                for i, b in enumerate(base.blocks):
                    h, c = get(m, b, t, s)
                    hit[base.off[i]:base.off[i + 1], mi, si] = h; cost[base.off[i]:base.off[i + 1], mi, si] = c
        # H2 per block, method, seed: point and bootstrap totals
        h2pt = np.zeros((len(base.blocks), len(M), S))
        for i in range(len(base.blocks)):
            pb = P[i]; sl = slice(base.off[i], base.off[i + 1])
            cw = np.cumsum(np.ones(base.nb[i])) / base.nb[i]
            for mi in range(len(M)):
                for si in range(S):
                    h2pt[i, mi, si] = pb["lk"].cost_per_hop(single_tau(pb["sd"], cw, hit[sl, mi, si].mean())).sum()
        boot = {}
        for c, W in base.W.items():
            cc = base.codes[c]
            Q = {"mcs": np.zeros((len(base.blocks), B_OTHER, len(M), S)), "h2": np.zeros((len(base.blocks), B_OTHER, len(M), S)),
                 "ws": np.zeros((len(base.blocks), B_OTHER))}
            for i in range(len(base.blocks)):
                pb = P[i]; sl = slice(base.off[i], base.off[i + 1])
                hs_, cs_ = hit[sl].reshape(base.nb[i], -1), cost[sl].reshape(base.nb[i], -1)
                for b0 in range(0, B_OTHER, 100):                           # replicate chunks (memory)
                    Wi = W[b0:b0 + 100, cc[sl]]                              # chunk x n_block (hop weights)
                    ws = Wi.sum(1)
                    Q["ws"][i, b0:b0 + 100] = ws
                    Q["mcs"][i, b0:b0 + 100] = (Wi @ cs_).reshape(len(Wi), len(M), S)
                    lev = (Wi @ hs_) / ws[:, None]
                    for k, w in enumerate(Wi):
                        cwb = np.cumsum(w[pb["o"]]); cwb = cwb / cwb[-1]
                        kw = np.bincount(pb["lk"].kinv, weights=w, minlength=len(pb["lk"].ukid))
                        taus = single_tau(pb["sd"], cwb, lev[k])
                        cm = np.ascontiguousarray(cost_per_key_many(pb["lk"], taus).T)     # thresholds x keys
                        Q["h2"][i, b0 + k] = np.array([kw @ c_ for c_ in cm]).reshape(len(M), S)
            boot[c] = Q
        for sc, sm in base.scopes.items():
            bl = [i for i, b in enumerate(base.blocks) if sc in ("combined", b)]
            CMs = base.CM[sm]; nC = CMs.sum(0); judged = nC >= MIN_N
            jg = np.flatnonzero(judged[:base.n25])
            rec = np.einsum("nc,nms->cms", CMs, hit[sm]) / nC[:, None, None]
            d = t - rec
            pts = {"D": d[jg].max(0), "reacq_d": d[base.reacq], "isoq4_d": d[base.isoq4],
                   "cost_mean": cost[sm].mean(0),
                   "cost_ratio_H2": cost[sm].mean(0) / (h2pt[bl].sum(0) / sm.sum())}
            bpts = {}
            for c, Q in boot.items():
                cc = base.codes[c][sm]; Cn = base.codes[c].max() + 1
                Nc = np.zeros((Cn, CMs.shape[1])); np.add.at(Nc, cc, CMs)
                Kc = np.zeros((Cn, CMs.shape[1], len(M), S))
                hs = hit[sm]
                for ci in range(CMs.shape[1]):
                    sel = CMs[:, ci] > 0
                    np.add.at(Kc[:, ci], cc[sel], hs[sel])
                W = base.W[c]
                db = t - np.einsum("bc,cgms->bgms", W, Kc) / (W @ Nc)[:, :, None, None]       # B, cells, M, S
                ws = Q["ws"][bl].sum(0)
                mc = Q["mcs"][bl].sum(0) / ws[:, None, None]
                bpts[c] = {"D": db[:, jg].max(1), "reacq_d": db[:, base.reacq], "isoq4_d": db[:, base.isoq4],
                           "cost_mean": mc, "cost_ratio_H2": mc / (Q["h2"][bl].sum(0) / ws[:, None, None]), "cells": db}
            for mi, m in enumerate(M):
                for k, v in pts.items():
                    r = {"label": label, "predictor": predictor, "scope": sc, "target": t, "method": m, "estimand": k,
                         "point": float(v[mi].mean()), "seed_min": float(v[mi].min()), "seed_max": float(v[mi].max()),
                         "level": LEVEL, "B": B_OTHER}
                    for c in boot:
                        lo, hi = pct(bpts[c][k][:, mi].mean(-1), LEVEL); r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                    r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                    est.append(r)
                for ci in range(len(base.cname)):
                    r = {"label": label, "predictor": predictor, "scope": sc, "target": t, "method": m,
                         "cell": base.cname[ci], "family": "g25" if ci < base.n25 else "intersection",
                         "n": int(nC[ci]), "judged": bool(judged[ci]), "deficit": float(d[ci, mi].mean())}
                    for c in boot:
                        lo, hi = pct(bpts[c]["cells"][:, ci, mi].mean(-1), LEVEL); r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                    r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                    cel.append(r)
            for ref in refs:
                if ref not in M:
                    continue
                ri = M.index(ref)
                for mi, m in enumerate(M):
                    if mi == ri:
                        continue
                    for k in ("D", "reacq_d", "isoq4_d", "cost_ratio_H2"):   # cost: paired difference of the ratios
                        dseed = pts[k][mi] - pts[k][ri]
                        r = {"label": label, "predictor": predictor, "scope": sc, "target": t, "reference": ref,
                             "comparator": m, "estimand": f"{k}_diff", "point": float(dseed.mean()),
                             "seed_min": float(dseed.min()), "seed_max": float(dseed.max()), "level": LEVEL, "B": B_OTHER,
                             "sign": "Delta = D_comparator - D_reference (positive = reference better)"}
                        for c in boot:
                            lo, hi = pct((bpts[c][k][:, mi] - bpts[c][k][:, ri]).mean(-1), LEVEL)
                            r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                        r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                        dif.append(r)
        print(f"[summary] {label} {predictor} t={t} done", flush=True)
    return pd.DataFrame(est), pd.DataFrame(dif), pd.DataFrame(cel)


def stored_get(predictor):
    """outcome getter for stored methods of the confirm2 runs."""
    def get(m, b, t, s):
        H = C.load_hits(b, t, s, columns=[f"hit|{predictor}|{m}", f"cost|{predictor}|{m}"])
        return H.iloc[:, 0].to_numpy(np.float64), H.iloc[:, 1].to_numpy(np.float64)
    return get
