"""confirm2 precheck (2026-10-13): counts only on the candidate period, precision from exploratory period 1.

    python notes/confirm2/precheck2.py

Rule: on the candidate period 2013-07-01 .. 2013-11-03 no method is run (no predictor, score, calibration, oracle).
Only hop extraction (work/confirm2_hops, notes/confirm2/count_hops.py), group attributes and counts.
Inputs:
  work/confirm2_hops/{trajectories,sightings,hops}.parquet, cameras.csv, taxi_map.parquet   (candidate period)
  work/porto_cctv/taxi_map.parquet, results/porto_cctv_regrade/hits.parquet                 (exploratory period 1)
  configs/*.yaml (read only)
Outputs: results/precheck_confirm2/*.csv
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "notes/confirm2")); sys.path.insert(0, str(ROOT / "paper/scripts"))
from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask  # noqa: E402
from count_hops import candidate_cfg  # noqa: E402

W = ROOT / "work/confirm2_hops"
OUT = ROOT / "results/precheck_confirm2"
TZ = "Europe/Lisbon"
BLOCKS = {"block1": {"train": ["2013-07-01", "2013-07-29"], "cal": ["2013-07-29", "2013-08-05"], "eval": ["2013-08-05", "2013-09-02"]},
          "block2": {"train": ["2013-09-02", "2013-09-30"], "cal": ["2013-09-30", "2013-10-07"], "eval": ["2013-10-07", "2013-11-04"]}}
DIMS25 = ["grp_all", "hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
INTER = {"I1 re-acquired x isolation Q4": [("hopkind", 2), ("nn_bin", 3)],
         "I2 re-acquired x branching Q4": [("hopkind", 2), ("entropy_bin", 3)],
         "I3 re-acquired x speed Q4": [("hopkind", 2), ("speed_bin", 3)],
         "I4 initiated x isolation Q4": [("hopkind", 1), ("nn_bin", 3)],
         "I5 speed Q4 x isolation Q4": [("speed_bin", 3), ("nn_bin", 3)],
         "I6 00-06h x re-acquired": [("hgroup", 0), ("hopkind", 2)]}
MIN_N = 200


def local(t):
    return pd.to_datetime(t, unit="s", utc=True).dt.tz_convert(TZ)


# ------------------------------------------------------------------ 1. contamination and date checks
def date_checks():
    rows = []
    for f in sorted(glob.glob(str(ROOT / "configs/*.yaml"))):
        c = yaml.safe_load(open(f))
        p = c.get("porto") or {}
        if not p.get("start_date"):
            continue
        s, e = p["start_date"], p["end_date"]
        ov = not (e <= "2013-07-01" or s >= "2013-11-04")
        rows.append({"config": Path(f).name, "data_start": s, "data_end_excl": e, "overlaps_candidate": ov})
    C = pd.DataFrame(rows); C.to_csv(OUT / "config_periods.csv", index=False)

    tm = pd.read_parquet(W / "taxi_map.parquet")
    tm["date"] = local(tm.t0).dt.date
    D = tm.groupby("date").agg(trips=("trip_id", "size"), taxis=("taxi_id", "nunique")).reset_index()
    full = pd.date_range("2013-07-01", "2013-11-03").date
    missing = sorted(set(full) - set(D.date))
    H = tm.assign(hour=pd.to_datetime(tm.t0, unit="s", utc=True).dt.floor("h").dt.tz_convert(TZ)).groupby("hour").size()
    allh = pd.date_range(pd.Timestamp("2013-07-01", tz=TZ), pd.Timestamp("2013-11-04", tz=TZ), freq="h", inclusive="left")
    zero_h = [str(h) for h in allh if h not in H.index]
    med = D.trips.median()
    D["below_half_median"] = D.trips < 0.5 * med
    D["above_1.5x_median"] = D.trips > 1.5 * med
    D["z_vs_weekday_median"] = D.trips / D.groupby(pd.to_datetime(D.date).dt.weekday).trips.transform("median")
    D.to_csv(OUT / "daily_trips_taxis.csv", index=False)
    dup_key = int(tm.trip_key.duplicated().sum())
    dup_taxi_t0 = int(tm.duplicated(["taxi_id", "t0"]).sum())
    S = pd.DataFrame([{"days_expected": len(full), "days_present": D.date.nunique(), "days_missing": ";".join(map(str, missing)),
                       "hours_without_trip_start": len(zero_h), "hours_without_trip_start_list": ";".join(zero_h[:50]),
                       "days_below_half_median": ";".join(map(str, D.date[D.below_half_median])),
                       "days_above_1.5x_median": ";".join(map(str, D.date[D["above_1.5x_median"]])),
                       "weekday_ratio_min": D.z_vs_weekday_median.min(), "weekday_ratio_min_date": str(D.date[D.z_vs_weekday_median.idxmin()]),
                       "weekday_ratio_max": D.z_vs_weekday_median.max(), "weekday_ratio_max_date": str(D.date[D.z_vs_weekday_median.idxmax()]),
                       "dup_trip_id_kept": dup_key, "dup_taxi_and_start_kept": dup_taxi_t0, "trips_kept": len(tm)}])
    S.to_csv(OUT / "date_checks.csv", index=False)
    return C, S


# ------------------------------------------------------------------ exit direction (8 sectors), recomputed from trajectories
def exit_rel(sig):
    """Angle of the exit point relative to the camera centre, as in events.extract_sightings (rel); zone is recomputed
    from it and must equal the stored 4-sector zone."""
    traj = pd.read_parquet(W / "trajectories.parquet").sort_values(["trip_id", "t"], kind="stable")
    cams = pd.read_csv(W / "cameras.csv")
    tr = traj.trip_id.to_numpy(); t = traj.t.to_numpy(); x = traj.x.to_numpy(); y = traj.y.to_numpy()
    bnd = np.flatnonzero(np.diff(tr)) + 1; st = np.r_[0, bnd]; en = np.r_[bnd, len(tr)]
    pos = dict(zip(tr[st], zip(st, en)))
    sig = sig.sort_values("trip_id", kind="stable")
    xe = np.empty(len(sig)); ye = np.empty(len(sig))
    sid = sig.trip_id.to_numpy(); tout = sig.t_out.to_numpy()
    b = np.flatnonzero(np.diff(sid)) + 1; ss = np.r_[0, b]; ee = np.r_[b, len(sid)]
    for a, z in zip(ss, ee):
        s, e = pos[sid[a]]
        xe[a:z] = np.interp(tout[a:z], t[s:e], x[s:e]); ye[a:z] = np.interp(tout[a:z], t[s:e], y[s:e])
    cx = cams.x.to_numpy()[sig.cam.to_numpy()]; cy = cams.y.to_numpy()[sig.cam.to_numpy()]
    rel = np.arctan2(ye - cy, xe - cx)
    z4 = (np.floor(np.mod(rel + np.pi / 4, 2 * np.pi) / (np.pi / 2)).astype(int)) % 4
    agree = float((z4 == sig.zone.to_numpy()).mean())
    sig = sig.assign(zone8=(np.floor(np.mod(rel + np.pi / 8, 2 * np.pi) / (np.pi / 4)).astype(int)) % 8)
    return sig, agree


# ------------------------------------------------------------------ 2-4. block counts
def block_counts():
    cfg = candidate_cfg()
    hops = pd.read_parquet(W / "hops.parquet"); cams = pd.read_csv(W / "cameras.csv")
    sig = pd.read_parquet(W / "sightings.parquet")
    sig, agree = exit_rel(sig)
    key = sig[["trip_id", "cam", "t_out", "zone8"]].rename(columns={"cam": "src", "t_out": "t_exit"})
    assert not key.duplicated(["trip_id", "src", "t_exit"]).any()
    n0 = len(hops)
    hops = hops.merge(key, on=["trip_id", "src", "t_exit"], how="left", validate="one_to_one")
    assert len(hops) == n0 and hops.zone8.notna().all()
    hops["zone8"] = hops.zone8.astype(int)
    tm = pd.read_parquet(W / "taxi_map.parquet").set_index("trip_id").taxi_id
    hops["taxi"] = tm.reindex(hops.trip_id).to_numpy()
    assert hops.taxi.notna().all()
    t = hops.t_exit.to_numpy()
    rows, tx = [], []
    for bname, B in BLOCKS.items():
        m_tr = _period_mask(t, B["train"], TZ)
        h4 = _add_spatial(_add_strata(hops, hops[m_tr], 4), m_tr, cams, 4)
        h5 = _add_spatial(_add_strata(hops, hops[m_tr], 5), m_tr, cams, 5)
        h4["hopkind"] = np.where(h4.hop > 0, 0, np.where(h4.chain == 0, 1, 2))
        m_ev = _period_mask(t, B["eval"], TZ) & ~hops.is_exit.to_numpy()
        m_cal = _period_mask(t, B["cal"], TZ) & ~hops.is_exit.to_numpy()
        E4, E5 = h4[m_ev], h5[m_ev]

        def add(family, name, mask_or_n, split="eval"):
            n = int(mask_or_n) if np.isscalar(mask_or_n) else int(np.asarray(mask_or_n).sum())
            rows.append({"block": bname, "split": split, "family": family, "group": name, "hops": n, "below_200": n < MIN_N})
        add("total", "all non-exit hops", len(E4))
        add("total", "all non-exit hops", int(m_cal.sum()), "cal")
        add("total", "all non-exit hops", int((m_tr & ~hops.is_exit.to_numpy()).sum()), "train")
        add("total", "transitions incl. exits", int(_period_mask(t, B["eval"], TZ).sum()))
        for d in DIMS25:
            for v in sorted(E4[d].unique()):
                add("25 groups", f"{d}={int(v)}", E4[d] == v)
        assert sum(r["block"] == bname and r["family"] == "25 groups" for r in rows) == 25
        for name, conds in INTER.items():
            m = np.ones(len(E4), bool)
            for d, v in conds:
                m &= (E4[d] == v).to_numpy()
            add("intersections", name, m)
        for v in range(24):
            add("hour (24 bins)", f"hour={v:02d}", E4.hour == v)
        for v in range(8):
            add("3-hour (8 bins)", f"hour3={3 * v:02d}-{3 * v + 3:02d}", (E4.hour // 3) == v)
        for v in range(8):
            add("exit direction (8 sectors)", f"zone8={v}", E4.zone8 == v)
        for d in ["speed_bin", "entropy_bin", "nn_bin"]:
            for v in range(5):
                add(f"{d} quintiles", f"{d}5={v}", E5[d] == v)
        # taxis
        per = E4.groupby("taxi").size()
        per_r = E4[E4.hopkind == 2].groupby("taxi").size()
        tx.append({"block": bname, "taxis_eval": int(per.size), "hops_per_taxi_median": float(per.median()),
                   "hops_per_taxi_max": int(per.max()), "hops_per_taxi_min": int(per.min()),
                   "taxis_with_reacq": int(per_r.size), "reacq_per_taxi_median": float(per_r.median()),
                   "reacq_per_taxi_max": int(per_r.max()),
                   "taxis_block_all_splits": int(hops.loc[_period_mask(t, [B["train"][0], B["eval"][1]], TZ), "taxi"].nunique())})
    R = pd.DataFrame(rows)
    comb = R[R.split == "eval"].groupby(["family", "group"], sort=False).hops.sum().reset_index()
    comb["block"] = "combined"; comb["split"] = "eval"; comb["below_200"] = comb.hops < MIN_N
    R = pd.concat([R, comb[R.columns]], ignore_index=True)
    R.to_csv(OUT / "block_counts.csv", index=False)
    T = pd.DataFrame(tx); T.to_csv(OUT / "block_taxis.csv", index=False)
    return R, T, agree


# ------------------------------------------------------------------ 5. precision from exploratory period 1 (static, 0.95)
def precision(R):
    import ch6lib as L  # noqa: F401  (wilson helper not needed)
    sys.path.insert(0, str(ROOT))
    from posthoc_cluster import boot
    H = pd.read_parquet(ROOT / "results/porto_cctv_regrade/hits.parquet",
                        columns=["trip_id", "segment", "hopkind", "hit|src_zone_hour_speed|static"])
    tm = pd.read_parquet(ROOT / "work/porto_cctv/taxi_map.parquet").set_index("trip_id").taxi_id
    H["taxi"] = tm.reindex(H.trip_id).to_numpy(); assert H.taxi.notna().all()
    rng = np.random.default_rng(20261013)
    de = []
    for seg in sorted(H.segment.unique()):
        h = H[(H.segment == seg)]
        M = (h.hopkind.to_numpy() == 2)[:, None]
        Y = h[["hit|src_zone_hour_speed|static"]].to_numpy().astype(float)
        codes = pd.factorize(h.taxi)[0]
        Rb = boot(codes, M, Y, rng)[:, 0, 0]
        n = int(M.sum()); p = Y[M[:, 0], 0].mean()
        de.append({"period": "exploratory 1", "segment": seg, "method": "static (target 0.95)", "group": "re-acquired",
                   "n": n, "recall": p, "taxis": int(h.loc[M[:, 0], "taxi"].nunique()),
                   "var_boot": Rb.var(ddof=1), "var_binom": p * (1 - p) / n, "de_taxi": Rb.var(ddof=1) / (p * (1 - p) / n)})
    DE = pd.DataFrame(de); DE.to_csv(OUT / "design_effect_expl1.csv", index=False)
    re = R[(R.family == "25 groups") & (R.group == "hopkind=2") & (R.split == "eval")].set_index("block").hops
    out = []
    for de_name, dval in [("DE = 1 (independent)", 1.0), ("DE = mean of segments", DE.de_taxi.mean()),
                          ("DE = max of segments", DE.de_taxi.max())]:
        for blk in ["block1", "block2", "combined"]:
            for p in (0.90, 0.95, 0.98):
                n = int(re[blk])
                out.append({"de": de_name, "de_value": dval, "block": blk, "n_reacq": n, "p": p,
                            "half_width_95": 1.96 * np.sqrt(dval * p * (1 - p) / n)})
        for p in (0.90, 0.95, 0.98):
            out.append({"de": de_name, "de_value": dval, "block": "n = 1500", "n_reacq": 1500, "p": p,
                        "half_width_95": 1.96 * np.sqrt(dval * p * (1 - p) / 1500)})
    P = pd.DataFrame(out); P.to_csv(OUT / "precision.csv", index=False)
    return DE, P


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    C, S = date_checks()
    R, T, agree = block_counts()
    pd.DataFrame([{"zone_recomputed_agreement": agree}]).to_csv(OUT / "zone_check.csv", index=False)
    DE, P = precision(R)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    print(C.to_string()); print(S.T.to_string()); print("zone agreement", agree)
    print(R[R.split == "eval"].pivot_table(index=["family", "group"], columns="block", values="hops", sort=False).to_string())
    print(R[R.split != "eval"].to_string()); print(T.T.to_string()); print(DE.to_string())
    print(P.pivot_table(index=["de", "block"], columns="p", values="half_width_95", sort=False).round(4).to_string())


if __name__ == "__main__":
    main()
