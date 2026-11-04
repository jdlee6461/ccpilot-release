"""POST-HOC: what is tau_min? (not pre-registered; report as post hoc)

    python posthoc_taumin_nature.py --config configs/porto_cctv_confirm.yaml

tau_min = mvp_log threshold at q = 1 = the a_min quantile of calibration scores (a_min 0.002).
Is it effectively the boundary of (camera, bin) pairs NEVER observed in training at any level
of the predictor's hierarchy (src, +zone, +hour group, +speed)? For every test query the matrix
it uses is taken (deepest available key, as in VisibilityModel); pairs are its (camera, bin) cells,
weighted by the number of test queries using that matrix.
  A = Pr[zero counts at all levels | P < tau_min]     B = Pr[P < tau_min | zero counts at all levels]
Raw counts are before the Gaussian bin smoothing (smoothing spreads counts to neighbouring bins,
so 'zero' here means no training visit in that exact bin). Also at hop level: among test hops with
score < tau_min, the share whose truth cells all have zero counts. Scenarios: no outage and
rand10 (seed 7, start of segment B). Output: <out_dir>_posthoc/taumin_nature/.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import load_config, load_work, offline_sites, outage_events, set_display
from ccpilot.predictors import VisibilityModel, _truth_by_tr, candidate_sets


def raw_counts(vm, tr, truth_map):
    depth = len(vm.levels)
    counts = [dict() for _ in range(depth)]
    tr = tr.loc[~tr["is_exit"]]
    for tid, kf in zip(tr["tr_id"].to_numpy(), tr[vm.levels].to_numpy()):
        src = int(kf[0]); rows = vm.row[src]
        keys = [tuple(int(v) for v in kf[:d + 1]) for d in range(depth)]
        for d, key in enumerate(keys):
            if key not in counts[d]:
                counts[d][key] = np.zeros((len(vm.cand[src]), vm.B), np.float32)
        for c, b0, b1 in truth_map.get(tid, []):
            r = rows.get(int(c))
            if r is not None:
                for d, key in enumerate(keys):
                    counts[d][key][r, b0:b1 + 1] += 1.0
    return counts


def zero_mask(vm, counts, kf):
    """(C x B) True where every level up to the matrix actually used has zero raw counts."""
    src = int(kf[0])
    z = np.ones((len(vm.cand[src]), vm.B), bool)
    for d in range(len(vm.levels)):
        key = tuple(int(v) for v in kf[:d + 1])
        if key not in vm.P[d]:
            break
        z &= counts[d].get(key, np.zeros_like(z, dtype=np.float32)) == 0
    return z


def analyse(cfg, trans, truth, cams, pred, offline, t_start, label):
    tz = cfg["timezone"]; ex = cfg["eval"]; sp = ex["splits"]
    t = trans["t_exit"].to_numpy()
    m_train = _period_mask(t, sp["train"], tz); m_cal = _period_mask(t, sp["cal"], tz)
    m_test = np.zeros(len(t), bool)
    for s in sp["test"]:
        m_test |= _period_mask(t, s["range"], tz)
    trans = _add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    trans = _add_spatial(trans, m_train, cams, ex.get("n_spatial_bins", 4))
    ok = ~trans["is_exit"].to_numpy()
    tr_train = trans[m_train]; tr_cal = trans[m_cal & ok]; tr_test = trans[m_test & ok]
    if t_start is not None:
        tr_test = tr_test[tr_test["t_exit"] >= t_start]
    tm = _truth_by_tr(truth)
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    vm = VisibilityModel(ex["predictors"][pred], cand, cfg_nbins(cfg), **ex["model"]).fit(tr_train, tm)
    s_cal, _, _ = vm.score(tr_cal, tm)
    cs = np.sort(s_cal)
    taus = {a: max(float(cs[int(np.floor(a * len(cs)))]), 1e-12) for a in (0.001, 0.002, 0.005)}
    counts = raw_counts(vm, tr_train, tm)
    out_mask = None
    if offline:
        vm.set_offline(offline); out_mask = np.ones(len(tr_test), bool)
    s_test, kid, _ = vm.score(tr_test, tm, out_mask)
    keys = tr_test[vm.levels].to_numpy()
    # cell level, weighted by queries per matrix
    per_key = {}
    for k, kf in zip(kid, keys):
        per_key.setdefault(int(k), [kf, 0])[1] += 1
    rows = []
    for a_min, tau in taus.items():
        n_low = n_low_zero = n_zero = n_all = 0.0
        for k, (kf, w) in per_key.items():
            M, _ = vm._matrix_for(kf, offline is not None and len(offline) > 0)
            z = zero_mask(vm, counts, kf)
            if offline:
                offr = [r for c, r in vm.row[int(kf[0])].items() if c in vm.offline]
                z[offr, :] = False            # offline cells are not candidates
                valid = np.ones_like(z); valid[offr, :] = False
            else:
                valid = np.ones_like(z)
            low = (M < tau) & valid
            n_all += w * valid.sum(); n_low += w * low.sum(); n_zero += w * z.sum(); n_low_zero += w * (low & z).sum()
        # hop level
        miss = s_test < tau
        allzero = []
        for tid, kf, msd in zip(tr_test["tr_id"].to_numpy(), keys, miss):
            if not msd:
                continue
            z = zero_mask(vm, counts, kf); rws = vm.row[int(kf[0])]
            cells = [(rws.get(int(c)), b0, b1) for c, b0, b1 in tm.get(tid, [])]
            cells = [x for x in cells if x[0] is not None]
            allzero.append(all(z[r, b0:b1 + 1].all() for r, b0, b1 in cells))   # no cell in candidates -> True
        rows.append({"scenario": label, "a_min": a_min, "tau_min": tau, "cells_below_share": n_low / n_all,
                     "A_zero_given_below": n_low_zero / n_low, "B_below_given_zero": n_low_zero / n_zero,
                     "zero_cells_share": n_zero / n_all, "test_hops": len(s_test), "hops_below": int(miss.sum()),
                     "hops_below_share": miss.mean(), "hops_below_all_truth_zero": float(np.mean(allzero)) if allzero else np.nan})
        print(rows[-1])
    return rows


def cfg_nbins(cfg):
    return int(np.ceil(cfg["events"]["t_max_s"] / cfg["events"]["bin_s"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    a = ap.parse_args()
    base = load_config(a.config)
    trans, truth, cams, _ = load_work(base)
    rows = analyse(base, trans, truth, cams, a.predictor, [], None, "none")
    tests = base["eval"]["splits"]["test"]
    t_start = date_to_unix(tests[1]["range"][0], base["timezone"])
    off = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams, trans, base)["rand10"]
    tr2, tru2, _, _ = outage_events(pd.read_parquet(Path(base["work_dir"]) / "sightings.parquet"), base, off, t_start)
    rows += analyse(base, tr2, tru2, cams, a.predictor, off, t_start, "rand10_s7_after_start")
    out = Path(base["out_dir"] + "_posthoc") / "taumin_nature"; out.mkdir(parents=True, exist_ok=True)
    R = pd.DataFrame(rows); R.to_csv(out / "taumin_nature.csv", index=False)
    set_display(); print(R.round(4).to_string(index=False)); print(f"-> {out}")


if __name__ == "__main__":
    main()
