"""confirm2 analysis (plan rev 61): deficits, cluster bootstrap, comparisons, §10.8 judgement, hindsight references,
costs, dominance, alternative partitions, block comparison, seed ranges. Figures: confirm2_figures.py; macros:
confirm2_numbers.py (both read the CSV files written here).

    python confirm2_analysis.py \
        --block expl1 work/trial_expl1/t0900_s0 work/trial_expl1/t0900_s1 ... \
        --taxi-map expl1 work/porto_cctv/taxi_map.parquet --attr expl1 work/porto_cctv/attr_expl1.parquet \
        --out results/precheck_confirm2/trial_expl1/analysis --trial --reachable

A block is given by its name and all of its runs (every target x seed, confirm2_run.py outputs); every run of a block
holds the same evaluation hops in the same order. Several blocks are combined (plan §2: the main estimate is the two
blocks together; block estimates are reported too). Settings: configs/confirm2_analysis.yaml.

Definitions (plan rev 61; § = plan section)
  R_G^s(t)   share of group G's evaluation hops detected (method m, evaluation seed s, target t)
  d_G^s(t) = t - R_G^s(t) (not truncated); D^s(t) = max over judged groups (n >= 200 in the scope) of d_G^s(t) (§5.1)
  seed mean: d_G = mean_s d_G^s, D = mean_s D^s (computed per seed, then averaged; also inside every replicate)
  (a) reacq_deficit_diff  = d_reacq(C) - d_reacq(P);  (b) isoq4_deficit_diff = d_isoQ4(C) - d_isoQ4(P);
  (c) worst_deficit_diff  = D(C) - D(P).  Positive = improvement of the proposed method P over comparator C (§5.5).
  Intervals: percentile cluster bootstrap; taxi = recorded TAXI_ID resampled jointly over the blocks; day = local
  date of the hop's exit, resampled within each block (§5.2). Conservative bounds: lower = min, upper = max of the two.
  Main comparisons: 99% (Bonferroni over 5 targets), B = 10,000; everything else 95%, B = 2,000.
  Class (§10.1): improvement if lower > 0, worsening if upper < 0, else undetermined.
  Hindsight references fitted per block on the block's hops (true scores), costs summed over blocks (§6.3):
  H1 single tau with recall >= t; H2 single tau with recall >= the method's realised recall in the block (per method
  and seed); H3 hindsight group QR (level 1 - t, all hops, highs-ipm), threshold FIXED at the full-sample fit (interval
  does not reflect threshold uncertainty); H4 group-minimum rule. H1, H2, H4 refitted in every replicate.
  Dominance (§10.5): point (A, t1) dominates (B, t2) if cost_hi(A) < cost_lo(B) and worst-recall_lo(A) > worst_hi(B).
"""
import argparse
import json
import os
import time
from pathlib import Path

THREADS = "8"      # plan §11.1-6 (rev 72): thread-count limit, set before numpy is imported
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = THREADS

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from ccpilot.multigroup import qr_group_taus  # noqa: E402
from ccpilot.predictors import TAU_MIN  # noqa: E402

ANALYSIS = "configs/confirm2_analysis.yaml"
TZ = "Europe/Lisbon"
DIMS25 = ["grp_all", "hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
ATTRS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
ALT = {"hour24": ("hour", 24), "hour3": ("hour3", 8), "zone8": ("zone8", 8),
       "speed5": ("speed_bin5", 5), "entropy5": ("entropy_bin5", 5), "isolation5": ("nn_bin5", 5)}
INTER = {"I1": [("hopkind", 2), ("nn_bin", 3)], "I2": [("hopkind", 2), ("entropy_bin", 3)],
         "I3": [("hopkind", 2), ("speed_bin", 3)], "I4": [("hopkind", 1), ("nn_bin", 3)],
         "I5": [("speed_bin", 3), ("nn_bin", 3)], "I6": [("hgroup", 0), ("hopkind", 2)]}
SIGN = "Delta = D_comparator - D_method (positive = improvement)"
H3NOTE = "H3 임계값 고정, 구간에 임계값 불확실성 미반영 (H3 threshold fixed; interval does not reflect threshold uncertainty)"


# ====================================================================== inputs
def hitcol(m, pred, t):
    if m == "citytrac_nominal":
        return f"hit|citytrac_rule|target{int(round(t * 100)):03d}"
    return f"hit|{m}" if "|" in m else f"hit|{pred}|{m}"


class CostLookup:
    """cost of hop i at threshold tau = (cells of the hop's key with p >= max(tau, TAU_MIN)) * delta (VisibilityModel.cost)."""

    def __init__(self, npz, kid):
        z = np.load(npz)
        self.delta = float(z["delta"])
        keys = z["kid"]
        pos = {int(k): i for i, k in enumerate(keys)}
        arrs = [z[f"v{int(k)}"].astype(np.float64) for k in keys]
        lens = np.array([len(a) for a in arrs])
        self.start = np.r_[0, np.cumsum(lens)[:-1]]; self.end = self.start + lens
        self.glob = np.concatenate([2.0 * i + a for i, a in enumerate(arrs)])
        self.kpos = np.array([pos[int(k)] for k in kid])
        self.ukid, self.kinv = np.unique(self.kpos, return_inverse=True)

    def cost_per_hop(self, tau):
        tau = np.maximum(np.broadcast_to(np.asarray(tau, float), self.kpos.shape), TAU_MIN)
        return (self.end[self.kpos] - np.searchsorted(self.glob, 2.0 * self.kpos + tau, side="left")) * self.delta

    def cost_per_key(self, tau):
        t = max(float(tau), TAU_MIN)
        return (self.end[self.ukid] - np.searchsorted(self.glob, 2.0 * self.ukid + t, side="left")) * self.delta


def load_block(name, dirs, taxi_map, attr, pred, methods):
    runs, H0 = {}, None
    for d in dirs:
        d = Path(d)
        info = json.load(open(d / "run_info.json"))
        t, s = round(float(info["target"]), 6), int(info["seed"])
        H = pd.read_parquet(d / "hits.parquet")
        if H0 is None:
            H0 = H[["tr_id", "trip_id", "t_exit", "segment"] + DIMS25 +
                   [f"score|{pred}", f"kid|{pred}", f"taumin0.002|{pred}"]].copy()
        else:
            assert np.array_equal(H.tr_id.to_numpy(), H0.tr_id.to_numpy()), f"{d}: different hops"
            assert np.array_equal(H[f"score|{pred}"].to_numpy(), H0[f"score|{pred}"].to_numpy()), f"{d}: scores differ"
        r = {"dir": str(d), "feedback": H["feedback"].to_numpy() if "feedback" in H else None, "hit": {}, "cost": {}}
        for m in methods:
            c = hitcol(m, pred, t)
            if c not in H:
                raise SystemExit(f"{d}: column {c} missing")
            r["hit"][m] = H[c].to_numpy().astype(np.float64)
            r["cost"][m] = H[c.replace("hit|", "cost|")].to_numpy().astype(np.float64)
        assert (t, s) not in runs, f"duplicate run {(t, s)}"
        runs[(t, s)] = r
    tm = pd.read_parquet(taxi_map).set_index("trip_id").taxi_id
    taxi = tm.reindex(H0.trip_id).to_numpy(); assert not pd.isna(taxi).any(), "trip without taxi id"
    day = pd.to_datetime(H0.t_exit, unit="s", utc=True).dt.tz_convert(TZ).dt.date.astype(str).to_numpy()
    if attr is not None:
        AT = pd.read_parquet(attr).set_index("tr_id").reindex(H0.tr_id)
        assert AT.notna().all().all(), "hop without alternative-partition attributes"
        for c in AT.columns:
            H0[c] = AT[c].to_numpy().astype(int)
    lk = CostLookup(Path(dirs[0]) / f"cost_lookup_{pred}.npz", H0[f"kid|{pred}"].to_numpy())
    return {"name": name, "H0": H0, "runs": runs, "taxi": taxi, "day": np.array([f"{name}:{x}" for x in day]),
            "score": H0[f"score|{pred}"].to_numpy(), "lk": lk, "taumin": float(H0[f"taumin0.002|{pred}"].iloc[0])}


# ====================================================================== helpers
def pct(x, level, axis=0):
    a = (1 - level) / 2
    return np.nanpercentile(x, 100 * a, axis=axis), np.nanpercentile(x, 100 * (1 - a), axis=axis)


def single_tau(sd, cw, level):
    """largest tau with weighted recall >= level; sd scores descending, cw cumulative weight share."""
    k = np.minimum(np.searchsorted(cw, np.asarray(level) - 1e-12, side="left"), len(sd) - 1)
    return sd[k]


class HStruct:
    """per-block precomputation for the hindsight references H1, H2, H4."""

    def __init__(self, b, G, dims_idx):
        s = b["score"]
        self.o = np.argsort(-s, kind="stable"); self.sd = s[self.o]
        self.Gf = G.astype(float)
        self.gidx = [np.flatnonzero(G[:, g])[np.argsort(-s[G[:, g]], kind="stable")] for g in range(G.shape[1])]
        self.gsd = [s[i] for i in self.gidx]
        self.dstack = np.stack(dims_idx, 1)             # hops x 7: index of the hop's group in each dimension
        self.lk = b["lk"]; self.score = s; self.nk = len(self.lk.ukid)

    def h1(self, w, t):
        cw = np.cumsum(w[self.o]); cw = cw / cw[-1]
        return single_tau(self.sd, cw, t), cw

    def h4(self, w, t):
        tg = np.empty(len(self.gidx))
        for g, (ix, sd) in enumerate(zip(self.gidx, self.gsd)):
            cw = np.cumsum(w[ix]); tot = cw[-1]
            tg[g] = single_tau(sd, cw / tot, t) if tot > 0 else np.inf
        cand = tg[self.dstack]                             # hops x 7
        j = np.argmin(cand, 1)
        gsel = self.dstack[np.arange(len(j)), j]
        return tg[gsel], tg, gsel

    def cost_h4(self, w, tg, gsel):
        key = gsel * self.nk + self.lk.kinv
        sums = np.bincount(key, weights=w, minlength=len(tg) * self.nk).reshape(len(tg), self.nk)
        return float(sum(sums[g] @ self.lk.cost_per_key(tg[g]) for g in range(len(tg)) if sums[g].any()))

    def kw(self, w):
        return np.bincount(self.lk.kinv, weights=w, minlength=self.nk)


# ====================================================================== analysis
def analyse(a):
    A = yaml.safe_load(open(ANALYSIS))
    if not a.trial and "FROM_PLAN" in json.dumps({k: v for k, v in A.items() if k != "version"}):
        raise SystemExit(f"refused: FROM_PLAN values left in {ANALYSIS}")
    pred = A["predictor"]; P = A["proposed"]; Cm = A["comparators_main"]; Co = A.get("comparators_other", [])
    methods = P + Cm + Co
    MI = {m: i for i, m in enumerate(methods)}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tmaps = dict(a.taxi_map); attrs = dict(a.attr)
    blocks = [load_block(spec[0], spec[1:], tmaps[spec[0]], attrs[spec[0]], pred, methods) for spec in a.block]
    keys = sorted(blocks[0]["runs"])
    for b in blocks:
        assert sorted(b["runs"]) == keys, f"block {b['name']}: runs {sorted(b['runs'])} != {keys}"
    targets = sorted({t for t, _ in keys}); seeds = sorted({s for _, s in keys})
    for t in targets:
        assert sorted(s for tt, s in keys if tt == t) == seeds, f"target {t}: unbalanced seeds"
    nb_ = [len(b["H0"]) for b in blocks]; off = np.r_[0, np.cumsum(nb_)]
    bid = np.concatenate([np.full(k, i) for i, k in enumerate(nb_)])
    H = pd.concat([b["H0"] for b in blocks], ignore_index=True)
    n = len(H); S = len(seeds); M = len(methods)
    score = np.concatenate([b["score"] for b in blocks])

    # ---- cells: 25 groups, alternative partitions (§8.1), intersections (§8.2)
    cells, fam = [], []
    for d in DIMS25:
        for v in sorted(H[d].unique()):
            cells.append((f"{d}={int(v)}", H[d].to_numpy() == v)); fam.append("g25")
    for f_, (col, k) in ALT.items():
        for v in range(k):
            cells.append((f"{col}={v}", H[col].to_numpy() == v)); fam.append(f_)
    for nm, cond in INTER.items():
        m_ = np.ones(n, bool)
        for d, v in cond:
            m_ &= H[d].to_numpy() == v
        cells.append((nm, m_)); fam.append("intersection")
    cname = [c for c, _ in cells]; fam = np.array(fam)
    CM = np.column_stack([m_ for _, m_ in cells]).astype(np.float64)       # n x cells
    g25 = np.flatnonzero(fam == "g25")
    assert np.array_equal(g25, np.arange(len(g25)))          # the 25 groups are the first cells
    gi = {k: cname.index(v) for k, v in A["group_keys"].items()}
    gall = cname.index("grp_all=0")
    scopes = {"combined": np.ones(n, bool)}
    if len(blocks) > 1:
        scopes.update({b["name"]: bid == i for i, b in enumerate(blocks)})

    # ---- clusters (taxi joint over blocks; day within block) and bootstrap weights
    codes = {"taxi": pd.factorize(np.concatenate([b["taxi"] for b in blocks]))[0],
             "day": pd.factorize(np.concatenate([b["day"] for b in blocks]))[0]}
    day_block = np.zeros(codes["day"].max() + 1, int); day_block[codes["day"]] = bid
    rng = np.random.default_rng(A["seeds"]["bootstrap"])
    Bm, Lm = A["bootstrap"]["main"]["B"], A["bootstrap"]["main"]["level"]
    Bo, Lo = A["bootstrap"]["other"]["B"], A["bootstrap"]["other"]["level"]
    Bm = a.B_main or Bm; Bo = a.B_other or Bo

    def weights(c, B):
        C = codes[c].max() + 1
        if c == "taxi":
            return rng.multinomial(C, np.full(C, 1 / C), size=B).astype(np.float64)
        W = np.zeros((B, C))
        for bi in range(len(blocks)):                     # stratified: days resampled within their block
            idx = np.flatnonzero(day_block == bi)
            W[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=B)
        return W
    W_main = {c: weights(c, Bm) for c in codes}
    W_oth = {c: weights(c, Bo) for c in codes}
    log = {"blocks": {b["name"]: len(b["H0"]) for b in blocks}, "targets": targets, "seeds": seeds,
           "B_main": Bm, "B_other": Bo, "clusters": {c: int(v.max() + 1) for c, v in codes.items()},
           "sign_convention": SIGN, "threads": THREADS, "timing": {}}
    T0 = time.time()

    def csum(c, vals, mask):
        """per-cluster sums of vals (n x ...) over the hops in mask -> (C x ...)."""
        out_ = np.zeros((codes[c].max() + 1,) + vals.shape[1:])
        np.add.at(out_, codes[c][mask], vals[mask])
        return out_

    def cons(r, a_, b_):
        r[a_] = min(r[f"{a_}_taxi"], r[f"{a_}_day"]); r[b_] = max(r[f"{b_}_taxi"], r[f"{b_}_day"])

    rows_gr, rows_def, rows_est, rows_cost, rows_seed, rows_alt, rows_inter, rows_gcr, rows_de, rows_cnt = ([] for _ in range(10))
    pts, boot_D = {}, {}
    for sc, smask in scopes.items():
        nC = CM[smask].sum(0)
        judged = nC >= A["min_group_n"]
        jg = g25[judged[g25]]
        for t in targets:
            Hm = np.stack([np.stack([np.concatenate([b["runs"][(t, s)]["hit"][m] for b in blocks]) for s in seeds], -1)
                           for m in methods], 1)[smask]                                     # n_s, M, S
            Cs = np.stack([np.stack([np.concatenate([b["runs"][(t, s)]["cost"][m] for b in blocks]) for s in seeds], -1)
                           for m in methods], 1)[smask]
            CMs = CM[smask]
            rec = np.einsum("nc,nms->cms", CMs, Hm) / nC[:, None, None]                     # cells, M, S
            d = t - rec
            Dseed = d[jg].max(0)                                                             # M, S
            for g in g25:
                for mi, m in enumerate(methods):
                    for si, s in enumerate(seeds):
                        rows_gr.append({"scope": sc, "target": t, "method": m, "seed": s, "group": cname[g], "n": int(nC[g]),
                                        "recall": rec[g, mi, si], "deficit": d[g, mi, si], "judged": bool(judged[g])})
            cost_seed = Cs.mean(0)                                                           # M, S
            for mi, m in enumerate(methods):
                rows_seed.append({"scope": sc, "target": t, "method": m, "D_seed_min": Dseed[mi].min(), "D_seed_max": Dseed[mi].max(),
                                  "cost_seed_min": cost_seed[mi].min(), "cost_seed_max": cost_seed[mi].max()})
            Nc, Kc = {}, {}
            for c in codes:
                cc = codes[c][smask]; C = codes[c].max() + 1
                Nc[c] = np.zeros((C, len(cname))); np.add.at(Nc[c], cc, CMs)
                Kc[c] = np.zeros((C, len(cname), M, S))
                for ci_ in range(len(cname)):
                    sel = CMs[:, ci_] > 0
                    np.add.at(Kc[c][:, ci_], cc[sel], Hm[sel])
            # ---- main comparisons (99%, B main): (a), (b), (c)
            fns = {"reacq_deficit_diff": lambda D_: D_[..., gi["reacquired"], :, :],
                   "isoq4_deficit_diff": lambda D_: D_[..., gi["isolation_q4"], :, :],
                   "worst_deficit_diff": lambda D_: D_[..., jg, :, :].max(axis=-3)}
            bdef = {}
            for c in codes:                              # 25 groups only (cells 0..24)
                W = W_main[c]
                nb = W @ Nc[c][:, :len(g25)]
                kb = np.einsum("bc,cgms->bgms", W, Kc[c][:, :len(g25)])
                bdef[c] = t - kb / nb[:, :, None, None]
            for pm in P:
                for cm in Cm:
                    pi_, ci2 = MI[pm], MI[cm]
                    for est, fn in fns.items():
                        pt_s = fn(d)
                        dseed = pt_s[ci2] - pt_s[pi_]
                        r = {"scope": sc, "target": t, "estimand": est, "proposed": pm, "comparator": cm,
                             "point": dseed.mean(), "level": Lm, "B": Bm}
                        for c in codes:
                            bb = fn(bdef[c])
                            lo, hi = pct((bb[:, ci2] - bb[:, pi_]).mean(-1), Lm)
                            r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                        r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                        r["class"] = "improvement" if r["lo"] > 0 else ("worsening" if r["hi"] < 0 else "undetermined")
                        imp, wor = int((dseed > 0).sum()), int((dseed < 0).sum())
                        r["seeds_improving"] = f"{imp}/{S}"; r["seeds_worsening"] = f"{wor}/{S}"
                        r["seed_agreement"] = (f"{imp}/{S}" if r["class"] == "improvement" else
                                               f"{wor}/{S}" if r["class"] == "worsening" else "")
                        r["sign_convention"] = SIGN
                        rows_est.append(r)
            del bdef
            # ---- other intervals (95%, B other)
            ob = {}
            for c in codes:
                W = W_oth[c]
                ob[c] = t - np.einsum("bc,cgms->bgms", W, Kc[c]) / (W @ Nc[c])[:, :, None, None]   # B, cells, M, S
                boot_D[(sc, t, c)] = ob[c][:, jg].max(1).mean(-1)                                 # B, M
            for mi, m in enumerate(methods):
                below = 0
                for ci_ in range(len(cname)):
                    r = {"scope": sc, "target": t, "method": m, "cell": cname[ci_], "family": fam[ci_],
                         "n": int(nC[ci_]), "deficit": d[ci_, mi].mean(), "recall": rec[ci_, mi].mean()}
                    for c in codes:
                        x = ob[c][:, ci_, mi].mean(-1)
                        lo, hi = pct(x, Lo); r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                        r[f"rup_{c}"] = float(np.nanpercentile(t - x, 95))                     # one-sided 95% upper, recall
                    r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                    r["recall_upper_1s"] = max(r["rup_taxi"], r["rup_day"])
                    if fam[ci_] == "g25":
                        rows_def.append(r)
                        below += int(r["recall_upper_1s"] < t and judged[ci_])
                    elif fam[ci_] == "intersection":
                        rows_inter.append(r)
                    else:
                        rows_alt.append(r)
                rows_cnt.append({"scope": sc, "target": t, "method": m, "groups_clearly_below_target": below})
                rD = {"scope": sc, "target": t, "method": m, "cell": "WORST", "family": "g25", "n": np.nan,
                      "deficit": Dseed[mi].mean(), "recall": t - Dseed[mi].mean()}
                for c in codes:
                    lo, hi = pct(boot_D[(sc, t, c)][:, mi], Lo); rD[f"lo_{c}"], rD[f"hi_{c}"] = float(lo), float(hi)
                rD["lo"] = min(rD["lo_taxi"], rD["lo_day"]); rD["hi"] = max(rD["hi_taxi"], rD["hi_day"])
                arg = jg[np.argmax(ob["taxi"][:, jg, mi, :], axis=1)]
                vc = pd.Series(arg.ravel()).value_counts(normalize=True)
                rD["worst_group_mode"] = cname[int(vc.index[0])]; rD["worst_group_mode_share"] = float(vc.iloc[0])
                rD["worst_group_mode_n"] = int(nC[int(vc.index[0])])
                rD["worst_group_point"] = ";".join(sorted({cname[jg[i]] for i in np.argmax(d[jg, mi, :], 0)}))
                rows_def.append(rD)
                for f_ in ALT:
                    idx = np.flatnonzero((fam == f_) & (nC >= A["min_group_n"]))
                    small = [cname[i] for i in np.flatnonzero((fam == f_) & (nC < A["min_group_n"]))]
                    ptmax = d[idx, mi].max(0).mean()
                    r = {"scope": sc, "target": t, "method": m, "cell": "SUMMARY", "family": f_, "cells": int((fam == f_).sum()),
                         "smallest_cell_n": int(nC[fam == f_].min()), "cells_below_200": ";".join(small),
                         "deficit": ptmax, "diff_vs_D": ptmax - Dseed[mi].mean()}
                    for c in codes:
                        bm = ob[c][:, idx, mi, :].max(1).mean(-1)
                        lo, hi = pct(bm, Lo); r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                        lo, hi = pct(bm - boot_D[(sc, t, c)][:, mi], Lo); r[f"dlo_{c}"], r[f"dhi_{c}"] = float(lo), float(hi)
                    r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                    r["diff_lo"] = min(r["dlo_taxi"], r["dlo_day"]); r["diff_hi"] = max(r["dhi_taxi"], r["dhi_day"])
                    r["reading"] = ("not distinguishable from the 25 groups" if r["diff_lo"] <= 0 <= r["diff_hi"] else
                                    "larger than the 25 groups" if r["diff_lo"] > 0 else "smaller than the 25 groups")
                    rows_alt.append(r)
            # ---- costs (§6.1); group costs; group cost ratio to static (S1 mechanism)
            cnt = {c: np.bincount(codes[c][smask], minlength=codes[c].max() + 1).astype(float) for c in codes}
            CCc = {}
            for c in codes:
                CCc[c] = np.zeros((codes[c].max() + 1, M, S)); np.add.at(CCc[c], codes[c][smask], Cs)
            GCc = {}
            for c in codes:
                GCc[c] = np.zeros((codes[c].max() + 1, 2, M, S))
                for gk, k in enumerate(("reacquired", "isolation_q4")):
                    sel = CMs[:, gi[k]] > 0
                    np.add.at(GCc[c][:, gk], codes[c][smask][sel], Cs[sel])
            for mi, m in enumerate(methods):
                hc = Cs[:, mi, :]
                r = {"scope": sc, "target": t, "method": m, "cost_mean": hc.mean(0).mean(),
                     "cost_median": np.median(hc, 0).mean(), "cost_p90": np.percentile(hc, 90, 0).mean(),
                     "recall_all": rec[gall, mi].mean(), "D": Dseed[mi].mean(), "worst_recall": t - Dseed[mi].mean()}
                for g in g25:
                    r[f"cost|{cname[g]}"] = hc[CMs[:, g] > 0].mean()
                for c in codes:
                    W = W_oth[c]
                    cb = ((W @ CCc[c][:, mi, :]) / (W @ cnt[c])[:, None]).mean(-1)
                    lo, hi = pct(cb, Lo); r[f"cost_lo_{c}"], r[f"cost_hi_{c}"] = float(lo), float(hi)
                    lo, hi = pct(t - boot_D[(sc, t, c)][:, mi], Lo); r[f"worst_lo_{c}"], r[f"worst_hi_{c}"] = float(lo), float(hi)
                r["cost_lo"] = min(r["cost_lo_taxi"], r["cost_lo_day"]); r["cost_hi"] = max(r["cost_hi_taxi"], r["cost_hi_day"])
                r["worst_lo"] = min(r["worst_lo_taxi"], r["worst_lo_day"]); r["worst_hi"] = max(r["worst_hi_taxi"], r["worst_hi_day"])
                rows_cost.append(r); pts[(sc, m, t)] = r
                if m != "static":
                    for gk, k in enumerate(("reacquired", "isolation_q4")):
                        sel = CMs[:, gi[k]] > 0
                        ratio_pt = np.mean([Cs[sel][:, mi, si].mean() / Cs[sel][:, MI["static"], si].mean() for si in range(S)])
                        rr = {"scope": sc, "target": t, "method": m, "group": k, "cost_ratio_to_static": ratio_pt}
                        for c in codes:
                            W = W_oth[c]
                            lo, hi = pct(((W @ GCc[c][:, gk, mi, :]) / (W @ GCc[c][:, gk, MI["static"], :])).mean(-1), Lo)
                            rr[f"lo_{c}"], rr[f"hi_{c}"] = float(lo), float(hi)
                        rr["lo"] = min(rr["lo_taxi"], rr["lo_day"]); rr["hi"] = max(rr["hi_taxi"], rr["hi_day"])
                        rows_gcr.append(rr)
                if m in P:                                    # design effects (C3)
                    for k in ("reacquired", "isolation_q4", "all"):
                        g = gall if k == "all" else gi[k]
                        for si, s in enumerate(seeds):
                            p_ = rec[g, mi, si]
                            for c in codes:
                                rows_de.append({"scope": sc, "target": t, "method": m, "seed": s, "group": cname[g], "cluster": c,
                                                "n": int(nC[g]), "recall": p_,
                                                "design_effect": np.nanvar(ob[c][:, g, mi, si], ddof=1) / (p_ * (1 - p_) / nC[g])})
            del ob, Kc
    log["timing"]["deficits_and_comparisons_s"] = time.time() - T0
    E = pd.DataFrame(rows_est); DEF = pd.DataFrame(rows_def); GCR = pd.DataFrame(rows_gcr)
    pd.DataFrame(rows_gr).to_csv(out / "group_recall.csv", index=False)
    E.to_csv(out / "main_estimands.csv", index=False)
    DEF.to_csv(out / "deficits.csv", index=False)
    pd.DataFrame(rows_alt).to_csv(out / "alt_partitions.csv", index=False)
    pd.DataFrame(rows_inter).to_csv(out / "intersections.csv", index=False)
    pd.DataFrame(rows_cnt).to_csv(out / "groups_clearly_below.csv", index=False)
    GCR.to_csv(out / "group_cost_ratio_to_static.csv", index=False)
    pd.DataFrame(rows_de).to_csv(out / "design_effects.csv", index=False)
    SR = pd.DataFrame(rows_seed).merge(DEF[DEF.cell == "WORST"][["scope", "target", "method", "lo", "hi"]],
                                       on=["scope", "target", "method"])
    SR["seed_range_over_ci_width"] = (SR.D_seed_max - SR.D_seed_min) / (SR.hi - SR.lo)
    SR.to_csv(out / "seed_range.csv", index=False)

    # ---- block comparison (§10.4): D(block 1) - D(block 2); taxi paired, day independent (strata); 95%
    if len(blocks) == 2:
        b1, b2 = blocks[0]["name"], blocks[1]["name"]
        rb = []
        for t in targets:
            for m in methods:
                mi = MI[m]
                r = {"target": t, "method": m, "D_block1": pts[(b1, m, t)]["D"], "D_block2": pts[(b2, m, t)]["D"]}
                r["diff"] = r["D_block1"] - r["D_block2"]
                for c in codes:
                    lo, hi = pct(boot_D[(b1, t, c)][:, mi] - boot_D[(b2, t, c)][:, mi], Lo)
                    r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                r["reading"] = "within sampling uncertainty" if r["lo"] <= 0 <= r["hi"] else "differs between blocks"
                rb.append(r)
        pd.DataFrame(rb).to_csv(out / "block_comparison.csv", index=False)

    # ---- hindsight references (§6.2, §6.3) per block, combined by summing; cost ratios; reference points for F2
    T1 = time.time()
    hs = []
    for bi, b in enumerate(blocks):
        Gb = CM[off[bi]:off[bi + 1]][:, g25] > 0
        dims_idx = []
        for d_ in DIMS25:
            cols = [k for k, g in enumerate(g25) if cname[g].split("=")[0] == d_]
            dims_idx.append(np.array(cols)[np.argmax(Gb[:, cols], 1)])
        hs.append(HStruct(b, Gb, dims_idx))
    ref_rows, ratio_rows, hpts = [], [], []
    for t in targets:
        fit = []
        for b, h in zip(blocks, hs):
            nbk = len(b["H0"]); w1 = np.ones(nbk)
            tau1, cw1 = h.h1(w1, t)
            t4, _, _ = h.h4(w1, t)
            th = time.time()
            tau3 = qr_group_taus(b["H0"][ATTRS], b["score"], b["H0"][ATTRS], ATTRS, 1 - t, max_n=nbk + 1, seed=0,
                                 lp_method="highs-ipm")[0]
            log["timing"][f"H3_fit_s_{b['name']}_t{t}"] = time.time() - th
            real = {(m, s): b["runs"][(t, s)]["hit"][m].mean() for m in methods for s in seeds}
            fit.append({"tau1": tau1, "tau3": tau3, "c3h": b["lk"].cost_per_hop(tau3), "t4": t4,
                        "h2tau": {k: single_tau(h.sd, cw1, v) for k, v in real.items()}})
        # per-block replicate quantities (B other), computed once and reused by every scope that contains the block;
        # the taxi weights are the joint resample over both blocks (plan §5.2), the day weights are stratified by block
        ms_keys = [(m, s) for m in methods for s in seeds]
        brep = {}
        for c in codes:
            W = W_oth[c]
            for i, (h, b) in enumerate(zip(hs, blocks)):
                Q = {"tot": {k: np.empty(Bo) for k in ("H1", "H3", "H4")}, "tot2": {k: np.empty(Bo) for k in ms_keys},
                     "mcs": {m: np.empty((Bo, S)) for m in methods},
                     "ghit": {k: np.empty((Bo, len(g25))) for k in ("H1", "H3", "H4")},
                     "gn": np.empty((Bo, len(g25))), "wsum": np.empty(Bo)}
                for bb in range(Bo):
                    w = W[bb, codes[c][off[i]:off[i + 1]]]
                    ws = w.sum(); Q["wsum"][bb] = ws
                    tau1, cw = h.h1(w, t)
                    kw = h.kw(w)
                    Q["tot"]["H1"][bb] = kw @ h.lk.cost_per_key(tau1)
                    t4, tg, gsel = h.h4(w, t)
                    Q["tot"]["H4"][bb] = h.cost_h4(w, tg, gsel)
                    Q["tot"]["H3"][bb] = w @ fit[i]["c3h"]
                    Q["gn"][bb] = w @ h.Gf
                    Q["ghit"]["H1"][bb] = (w * (h.score >= tau1)) @ h.Gf
                    Q["ghit"]["H3"][bb] = (w * (h.score >= fit[i]["tau3"])) @ h.Gf
                    Q["ghit"]["H4"][bb] = (w * (h.score >= t4)) @ h.Gf
                    for m in methods:
                        for si, s in enumerate(seeds):
                            rr_ = b["runs"][(t, s)]
                            Q["mcs"][m][bb, si] = w @ rr_["cost"][m]
                            lev = (w @ rr_["hit"][m]) / ws
                            Q["tot2"][(m, s)][bb] = kw @ h.lk.cost_per_key(single_tau(h.sd, cw, lev))
                brep[(c, i)] = Q
        for sc, smask in scopes.items():
            bl = [i for i in range(len(blocks)) if smask[off[i]:off[i + 1]].all()]
            idx_sc = np.concatenate([np.arange(off[i], off[i + 1]) for i in bl])
            cm_ = CM[idx_sc][:, g25]; nG_ = cm_.sum(0); jgm = nG_ >= A["min_group_n"]

            def ref_point(tb):
                hits = np.concatenate([blocks[i]["score"] >= tb[i] for i in bl]).astype(float)
                cost = np.concatenate([blocks[i]["lk"].cost_per_hop(tb[i]) for i in bl])
                rec_ = (cm_.T @ hits) / nG_
                dd = np.where(jgm, t - rec_, -np.inf)
                return hits.mean(), float(dd.max()), cost.mean(), cname[g25[int(np.argmax(dd))]]
            refs = {"H1": [np.full(nb_[i], fit[i]["tau1"]) for i in range(len(blocks))],
                    "H3": [fit[i]["tau3"] for i in range(len(blocks))], "H4": [fit[i]["t4"] for i in range(len(blocks))]}
            hp = {}
            for nm, tb in refs.items():
                r_, wd, c_, wg = ref_point(tb)
                hp[nm] = c_
                ref_rows.append({"scope": sc, "target": t, "reference": nm, "method": "", "seed": "", "recall_all": r_,
                                 "worst_deficit": wd, "worst_group": wg, "cost_mean": c_, "note": H3NOTE if nm == "H3" else ""})
            h2pt = {}
            for m in methods:
                for s in seeds:
                    r_, wd, c_, wg = ref_point([np.full(nb_[i], fit[i]["h2tau"][(m, s)]) for i in range(len(blocks))])
                    h2pt[(m, s)] = c_
                    ref_rows.append({"scope": sc, "target": t, "reference": "H2", "method": m, "seed": s, "recall_all": r_,
                                     "worst_deficit": wd, "worst_group": wg, "cost_mean": c_, "note": ""})
            # combine the per-block replicate quantities (computed once per block, below the fit loop) in block order,
            # starting from zero: identical floating-point operations to accumulating block by block (plan §11.1-6)
            res = {}
            for c in codes:
                R_ = {"H1": np.empty(Bo), "H3": np.empty(Bo), "H4": np.empty(Bo), "H2": {k: np.empty(Bo) for k in h2pt},
                      "mc": {m: np.empty((Bo, S)) for m in methods}, "wr": {k: np.empty(Bo) for k in ("H1", "H3", "H4")}}
                for bb in range(Bo):
                    tot = dict.fromkeys(("H1", "H3", "H4"), 0.0); tot2 = dict.fromkeys(h2pt, 0.0); wsum = 0.0
                    mcs = {m: np.zeros(S) for m in methods}
                    ghit = {k: np.zeros(len(g25)) for k in ("H1", "H3", "H4")}; gn_ = np.zeros(len(g25))
                    for i in bl:
                        Q = brep[(c, i)]
                        wsum += Q["wsum"][bb]
                        for k in ("H1", "H3", "H4"):
                            tot[k] += Q["tot"][k][bb]
                            ghit[k] += Q["ghit"][k][bb]
                        gn_ += Q["gn"][bb]
                        for m in methods:
                            mcs[m] += Q["mcs"][m][bb]
                        for k in h2pt:
                            tot2[k] += Q["tot2"][k][bb]
                    for k in ("H1", "H3", "H4"):
                        R_[k][bb] = tot[k] / wsum
                        R_["wr"][k][bb] = np.min((ghit[k] / gn_)[gn_ >= A["min_group_n"]])
                    for k in h2pt:
                        R_["H2"][k][bb] = tot2[k] / wsum
                    for m in methods:
                        R_["mc"][m][bb] = mcs[m] / wsum
                res[c] = R_
            for m in methods:
                mpt = [np.concatenate([blocks[i]["runs"][(t, s)]["cost"][m] for i in bl]).mean() for s in seeds]
                for ref in ("H1", "H2", "H3", "H4"):
                    pt_ = (np.mean([mpt[si] / h2pt[(m, s)] for si, s in enumerate(seeds)]) if ref == "H2"
                           else np.mean([x / hp[ref] for x in mpt]))
                    r = {"scope": sc, "target": t, "method": m, "reference": ref, "ratio": pt_, "level": Lo, "B": Bo,
                         "note": H3NOTE if ref == "H3" else ""}
                    for c in codes:
                        R_ = res[c]
                        rb_ = (np.stack([R_["mc"][m][:, si] / R_["H2"][(m, s)] for si, s in enumerate(seeds)], 1).mean(1)
                               if ref == "H2" else (R_["mc"][m] / R_[ref][:, None]).mean(1))
                        lo, hi = pct(rb_, Lo); r[f"lo_{c}"], r[f"hi_{c}"] = float(lo), float(hi)
                    r["lo"] = min(r["lo_taxi"], r["lo_day"]); r["hi"] = max(r["hi_taxi"], r["hi_day"])
                    ratio_rows.append(r)
            for ref in ("H1", "H3", "H4"):
                rr = [x for x in ref_rows if x["scope"] == sc and x["target"] == t and x["reference"] == ref][0]
                r = {"scope": sc, "target": t, "method": ref, "cost_mean": rr["cost_mean"], "recall_all": rr["recall_all"],
                     "D": rr["worst_deficit"], "worst_recall": t - rr["worst_deficit"], "note": H3NOTE if ref == "H3" else ""}
                for c in codes:
                    lo, hi = pct(res[c][ref], Lo); r[f"cost_lo_{c}"], r[f"cost_hi_{c}"] = float(lo), float(hi)
                    lo, hi = pct(res[c]["wr"][ref], Lo); r[f"worst_lo_{c}"], r[f"worst_hi_{c}"] = float(lo), float(hi)
                r["cost_lo"] = min(r["cost_lo_taxi"], r["cost_lo_day"]); r["cost_hi"] = max(r["cost_hi_taxi"], r["cost_hi_day"])
                r["worst_lo"] = min(r["worst_lo_taxi"], r["worst_lo_day"]); r["worst_hi"] = max(r["worst_hi_taxi"], r["worst_hi_day"])
                hpts.append(r)
    log["timing"]["hindsight_s"] = time.time() - T1
    REF = pd.DataFrame(ref_rows); RAT = pd.DataFrame(ratio_rows)
    h2m = REF[REF.reference == "H2"].groupby(["scope", "target", "method"], as_index=False)[["recall_all", "worst_deficit"]].mean()
    k1 = RAT[RAT.reference != "H2"].merge(REF[REF.reference != "H2"][["scope", "target", "reference", "recall_all", "worst_deficit"]],
                                          on=["scope", "target", "reference"], how="left")
    k2 = RAT[RAT.reference == "H2"].merge(h2m, on=["scope", "target", "method"], how="left")
    RAT = pd.concat([k1, k2]).rename(columns={"recall_all": "reference_overall_recall", "worst_deficit": "reference_worst_deficit"})
    REF.to_csv(out / "hindsight.csv", index=False); RAT.to_csv(out / "cost_ratios.csv", index=False)
    pd.DataFrame(rows_cost).to_csv(out / "costs.csv", index=False)
    PTS = pd.concat([pd.DataFrame(rows_cost), pd.DataFrame(hpts)], ignore_index=True)
    PTS.to_csv(out / "method_points.csv", index=False)

    # ---- dominance (§10.5): combined scope, all target points, both directions
    pc = PTS[PTS.scope == "combined"].set_index(["method", "target"])
    drows, dsum = [], []
    for pm in P:
        for cm in Cm + Co + ["H1", "H3", "H4"]:
            nPC = nCP = 0
            for t1 in targets:
                for t2 in targets:
                    A_, B_ = pc.loc[(pm, t1)], pc.loc[(cm, t2)]
                    if A_.cost_hi < B_.cost_lo and A_.worst_lo > B_.worst_hi:
                        nPC += 1; drows.append({"dominant": pm, "t_dominant": t1, "dominated": cm, "t_dominated": t2})
                    if B_.cost_hi < A_.cost_lo and B_.worst_lo > A_.worst_hi:
                        nCP += 1; drows.append({"dominant": cm, "t_dominant": t2, "dominated": pm, "t_dominated": t1})
            dsum.append({"method": pm, "comparator": cm, "method_dominates_pairs": nPC, "comparator_dominates_pairs": nCP,
                         "same_cost_sentence_allowed": bool(nPC > 0 and nCP == 0)})
    pd.DataFrame(drows, columns=["dominant", "t_dominant", "dominated", "t_dominated"]).to_csv(out / "dominance_pairs.csv", index=False)
    pd.DataFrame(dsum).to_csv(out / "dominance.csv", index=False)

    # ---- reachable upper bound U_G (§5.4) and a_min reach (§4); new period only after the lock
    if a.reachable:
        rr = []
        for sc, smask in scopes.items():
            for g in g25:
                m_ = smask & (CM[:, g] > 0)
                rr.append({"scope": sc, "group": cname[g], "n": int(m_.sum()), "U_G": 1 - float((score[m_] <= 0).mean()),
                           "below_mvp_log_min_tau_share": float(np.mean(np.concatenate(
                               [blocks[i]["score"][m_[off[i]:off[i + 1]]] < blocks[i]["taumin"] for i in range(len(blocks))])))})
        pd.DataFrame(rr).to_csv(out / "reachable_bound.csv", index=False)
        am = []
        for t in targets:
            for s in seeds:
                c_mvp = np.concatenate([b["runs"][(t, s)]["cost"]["mvp_log"] for b in blocks])
                c_min = np.concatenate([b["lk"].cost_per_hop(b["taumin"]) for b in blocks])
                am.append({"target": t, "seed": s, "mvp_log_hops_at_a_min_share": float((c_mvp >= c_min).mean()),
                           "note": "proxy: the hop's mvp_log cost equals the cost at the lowest threshold (a_min)"})
        pd.DataFrame(am).to_csv(out / "a_min_reach.csv", index=False)

    judge(A, E[E.scope == "combined"], GCR, RAT, DEF, targets, out)
    fm = []
    for b in blocks:
        for s in seeds:
            ms = [b["runs"][(t, s)]["feedback"] for t in targets]
            fm.append({"block": b["name"], "seed": s, "targets": len(ms), "identical": all(np.array_equal(ms[0], x) for x in ms[1:])})
    pd.DataFrame(fm).to_csv(out / "feedback_mask_check.csv", index=False)
    log["timing"]["total_s"] = time.time() - T0
    json.dump(log, open(out / "analysis_log.json", "w"), indent=1, default=str)
    print(json.dumps(log, indent=1, default=str))


def judge(A, E, GCR, RAT, DEF, targets, out):
    """§10.8 on the combined scope; judgement estimand (a); (c) alongside."""
    maj = A["estimands"]["claim_majority"]; full = len(targets) >= 5
    na = "n/a (fewer than 5 targets)"
    a = E[E.estimand == "reacq_deficit_diff"]; c = E[E.estimand == "worst_deficit_diff"]
    rows = []

    def rng_(g):
        return (f"t = {', '.join(f'{x:g}' for x in g.target)}; difference {g.point.min():.4f} to {g.point.max():.4f}"
                if len(g) else "none")
    for pm in A["proposed"]:
        k = {}
        for cm in A["comparators_main"]:
            g = a[(a.proposed == pm) & (a.comparator == cm)]
            k[cm] = {"imp": g[g["class"] == "improvement"], "wor": g[g["class"] == "worsening"], "all": g.set_index("target"),
                     "c": c[(c.proposed == pm) & (c.comparator == cm)].set_index("target")["class"]}
        s_ok, a_ok = len(k["static"]["imp"]) >= maj, len(k["aci_g0005"]["imp"]) >= maj
        wor = sorted(set(k["static"]["wor"].target) | set(k["aci_g0005"]["wor"].target))
        dis = [f"{cm} t={t:g}: (a) {k[cm]['all'].loc[t, 'class']}, (c) {cl}" for cm in ("static", "aci_g0005")
               for t, cl in k[cm]["c"].items() if cl != k[cm]["all"].loc[t, "class"]]
        rows.append({"method": pm, "statement": "S1 core",
                     "status": ("keep" if s_ok and a_ok else "restrict to static" if s_ok else "not met") if full else na,
                     "detail": f"static improvement: {rng_(k['static']['imp'])} | ACI improvement: {rng_(k['aci_g0005']['imp'])}"
                               + (f" | worsening at t = {wor}" if wor else "") + (f" | (a)/(c) differ: {dis}" if dis else "")})
        g = GCR[(GCR.scope == "combined") & (GCR.method == pm)]
        nmech = int(sum(1 for _, x in g.groupby("target") if len(x) == 2 and (x.lo > 1).all()))
        rows.append({"method": pm, "statement": "S1 mechanism clause", "status": ("keep" if nmech >= maj else "delete") if full else na,
                     "detail": f"targets where the 95% lower bound of (group cost / static group cost) > 1 in both re-acquired and isolation Q4: {nmech}"})
        add = [f"{cm}: {'opposite' if len(k[cm]['wor']) >= maj else 'not distinguishable'}"
               for cm in ("mondrian_hour_hop_speed", "qr_groups") if len(k[cm]["imp"]) < maj]
        rows.append({"method": pm, "statement": "S1 addition (offline group calibration)",
                     "status": ("none" if not add else "add") if full else na,
                     "detail": "; ".join(add) if add else "majority improvement over Mondrian and qr_groups"})
        r1, r7 = k["qr_groups_refit"], k["qr_groups_refit7"]
        s2 = ("나타난다" if len(r1["imp"]) >= maj and len(r7["imp"]) >= maj else
              "반대였다" if len(r1["wor"]) >= maj or len(r7["wor"]) >= maj else "검출되지 않았다")
        rows.append({"method": pm, "statement": "S2", "status": s2 if full else na,
                     "detail": f"refit: improvement {len(r1['imp'])}, worsening {len(r1['wor'])}; refit7: improvement "
                               f"{len(r7['imp'])}, worsening {len(r7['wor'])} (of {len(targets)} targets)"})
        rr = RAT[(RAT.scope == "combined") & (RAT.method == pm) & RAT.reference.isin(["H3", "H2"])].sort_values(["target", "reference"])
        rows.append({"method": pm, "statement": "S3", "status": "always reported (ratios with 95% intervals)",
                     "detail": "; ".join(f"t={x.target:g} {x.reference} {x.ratio:.3f} [{x.lo:.3f}, {x.hi:.3f}]" for x in rr.itertuples())})
        d4 = DEF[(DEF.scope == "combined") & (DEF.method == pm) & (DEF.cell == A["group_keys"]["reacquired"])]
        n4 = int((d4.lo > 0).sum())
        rows.append({"method": pm, "statement": "S4", "status": ("remains" if n4 >= maj else "restrict (previous evaluation ...)") if full else na,
                     "detail": "; ".join(f"t={x.target:g} d {x.deficit:.4f} [{x.lo:.4f}, {x.hi:.4f}]" for x in d4.itertuples())})
    pd.DataFrame(rows).to_csv(out / "claims_10_8.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", nargs="+", action="append", required=True, help="NAME RUN_DIR [RUN_DIR ...]")
    ap.add_argument("--taxi-map", nargs=2, action="append", required=True, help="NAME taxi_map.parquet")
    ap.add_argument("--attr", nargs=2, action="append", required=True, help="NAME attributes.parquet (confirm2_attributes.py)")
    ap.add_argument("--out", required=True); ap.add_argument("--trial", action="store_true")
    ap.add_argument("--reachable", action="store_true")
    ap.add_argument("--B-main", type=int); ap.add_argument("--B-other", type=int)
    analyse(ap.parse_args())


if __name__ == "__main__":
    main()
