"""confirm2 precheck A2/A3: COUNT hops in the candidate period 2013-07-01 .. 2013-11-03 (no outcomes).

    python notes/confirm2/count_hops.py --verify      # check that the hop-only builder equals events.build_transitions
                                                      # on the existing confirmation-period sightings (no new period read)
    python notes/confirm2/count_hops.py --build       # trajectories -> sightings -> hops for the candidate period
    python notes/confirm2/count_hops.py --count       # weekly / daily / per-split group counts -> notes/confirm2/*.csv

Rule 0 of notes/instructions/2026-10-02_confirm2_precheck.md: in the candidate period no predictor is trained, no
score is computed and no calibration method is run. This script builds hops and counts them. It does NOT build the
visibility sets ("truth"): the hop-only builder below is events.build_transitions without the truth part.
No configuration file is written: the confirmation configuration is read and copied in memory with new dates.
Intermediate files go to work/confirm2_hops/ (git-ignored); counts go to notes/confirm2/.
"""
import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ccpilot import events, porto  # noqa: E402
from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask  # noqa: E402
from ccpilot.events import hour_group, local_hour_dow  # noqa: E402
from ccpilot.posthoc import load_config  # noqa: E402

BASE = "configs/porto_cctv_confirm.yaml"          # read only
START, END = "2013-07-01", "2013-11-04"           # [start, end): 2013-07-01 .. 2013-11-03
WORK = Path("work/confirm2_hops")
OUT = Path("notes/confirm2")
SPLITS = {"C1": {"train": ["2013-07-01", "2013-07-29"], "cal": ["2013-07-29", "2013-08-05"], "eval": ["2013-08-05", "2013-11-04"]},
          "C2": {"train": ["2013-08-05", "2013-09-02"], "cal": ["2013-09-02", "2013-09-09"], "eval": ["2013-09-09", "2013-11-04"]},
          "C3": {"train": ["2013-07-29", "2013-08-26"], "cal": ["2013-08-26", "2013-09-02"], "eval": ["2013-09-02", "2013-11-04"]}}
ATTRS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]


def candidate_cfg():
    cfg = copy.deepcopy(load_config(BASE))
    cfg["porto"]["start_date"], cfg["porto"]["end_date"] = START, END
    cfg["work_dir"] = str(WORK)
    return cfg


def build_hops(sight, cfg):
    """events.build_transitions without the visibility sets (same episodes, exits, chains and hop numbers)."""
    ev = cfg["events"]
    step = ev["interp_step_s"]; t_max = ev["t_max_s"]
    trip = sight["trip_id"].to_numpy(); cam = sight["cam"].to_numpy()
    tin = sight["t_in"].to_numpy(); tout = sight["t_out"].to_numpy()
    zone = sight["zone"].to_numpy(); spd = sight["speed_out"].to_numpy()
    bnd = np.flatnonzero(np.diff(trip)) + 1
    starts = np.r_[0, bnd]; ends = np.r_[bnd, len(trip)]
    rec = {k: [] for k in ["trip_id", "src", "t_exit", "zone", "speed_out", "is_exit", "t_arrive", "first_cam", "chain", "hop"]}
    for s, e in zip(starts, ends):
        eps = []; cur = [s]; cur_end = tout[s]
        for i in range(s + 1, e):
            if tin[i] <= cur_end + 1.5 * step:
                cur.append(i); cur_end = max(cur_end, tout[i])
            else:
                eps.append(cur); cur = [i]; cur_end = tout[i]
        eps.append(cur)
        chain = 0; hop = 0
        for k, members in enumerate(eps):
            m = np.asarray(members); j_src = m[np.argmax(tout[m])]; t_exit = tout[j_src]
            is_exit = True; t_arr = np.nan; fcam = -1
            if k + 1 < len(eps):
                nxt = np.asarray(eps[k + 1]); t_arr = tin[nxt].min()
                if t_arr - t_exit <= t_max:
                    is_exit = False; fcam = cam[nxt[np.argmin(tin[nxt])]]
            for key, val in [("trip_id", trip[s]), ("src", cam[j_src]), ("t_exit", t_exit), ("zone", zone[j_src]),
                             ("speed_out", spd[j_src]), ("is_exit", is_exit), ("t_arrive", t_arr), ("first_cam", fcam),
                             ("chain", chain), ("hop", hop)]:
                rec[key].append(val)
            if is_exit:
                chain += 1; hop = 0
            else:
                hop += 1
    trans = pd.DataFrame(rec)
    trans.insert(0, "tr_id", np.arange(len(trans)))
    hours, dow = local_hour_dow(trans["t_exit"].to_numpy(), cfg["timezone"])
    trans["hour"] = hours; trans["dow"] = dow
    trans["hgroup"] = hour_group(hours, np.asarray(ev["hour_group_edges"]))
    return trans


def verify():
    cfg = load_config(BASE)
    sig = pd.read_parquet(Path(cfg["work_dir"]) / "sightings.parquet")
    ref = pd.read_parquet(Path(cfg["work_dir"]) / "transitions.parquet")
    new = build_hops(sig, cfg)
    same = ref.columns.tolist() == new.columns.tolist() and all(
        np.array_equal(ref[c].to_numpy(), new[c].to_numpy(), equal_nan=True) for c in ref.columns)
    print(f"[verify] confirmation period: {len(ref)} transitions; hop-only builder identical: {same}")
    assert same


def build():
    cfg = candidate_cfg()
    WORK.mkdir(parents=True, exist_ok=True)
    traj = porto.load(cfg)                              # trips with a point inside the box, [START, END)
    cams = pd.read_csv(Path(load_config(BASE)["work_dir"]) / "cameras.csv")   # same 176 sites as the confirmation run
    ev = cfg["events"]
    sig = events.extract_sightings(traj, cams, ev["camera_radius_m"], ev["interp_step_s"],
                                   ev.get("max_overlap", 4))
    hops = build_hops(sig, cfg)
    traj.to_parquet(WORK / "trajectories.parquet"); sig.to_parquet(WORK / "sightings.parquet"); hops.to_parquet(WORK / "hops.parquet")
    cams.to_csv(WORK / "cameras.csv", index=False)
    print(f"[build] trips={traj.trip_id.nunique()} sightings={len(sig)} transitions={len(hops)} non-exit={int((~hops.is_exit).sum())}")


def count():
    cfg = candidate_cfg(); tz = cfg["timezone"]
    traj = pd.read_parquet(WORK / "trajectories.parquet", columns=["trip_id", "t"])
    hops = pd.read_parquet(WORK / "hops.parquet"); cams = pd.read_csv(WORK / "cameras.csv")
    t0 = traj.groupby("trip_id").t.min()
    day_trip = pd.to_datetime(t0, unit="s", utc=True).dt.tz_convert(tz).dt.date
    hops["date"] = pd.to_datetime(hops.t_exit, unit="s", utc=True).dt.tz_convert(tz).dt.date
    hops["week"] = (pd.to_datetime(hops["date"]) - pd.to_timedelta(pd.to_datetime(hops["date"]).dt.weekday, unit="D")).dt.date
    hops["hopkind"] = np.where(hops["hop"] > 0, 0, np.where(hops["chain"] == 0, 1, 2))
    trips_week = pd.Series(1, index=t0.index).groupby((pd.to_datetime(day_trip) - pd.to_timedelta(pd.to_datetime(day_trip).dt.weekday, unit="D")).dt.date.values).sum()
    W = hops.groupby("week").agg(transitions=("tr_id", "size"), non_exit=("is_exit", lambda x: int((~x).sum())),
                                 exit_share=("is_exit", "mean"))
    nk = hops[~hops.is_exit].groupby(["week", "hopkind"]).size().unstack(fill_value=0).rename(columns={0: "later", 1: "initiated", 2: "re_acquired"})
    W = W.join(nk); W.insert(0, "trips", trips_week.reindex(W.index).fillna(0).astype(int))
    W.index.name = "week_monday"; W.to_csv(OUT / "weekly_counts.csv")
    D = pd.Series(1, index=t0.index).groupby(day_trip.values).sum().rename("trips").to_frame()
    D.index.name = "date"; med = D.trips.median()
    D["below_half_of_median"] = D.trips < 0.5 * med
    D.to_csv(OUT / "daily_trips.csv")
    rows, wrows = [], []
    t = hops["t_exit"].to_numpy()
    for name, sp in SPLITS.items():
        m_train = _period_mask(t, sp["train"], tz)
        h = _add_strata(hops, hops[m_train], cfg["eval"].get("n_speed_bins", 4))
        h = _add_spatial(h, m_train, cams, cfg["eval"].get("n_spatial_bins", 4))
        m_eval = _period_mask(t, sp["eval"], tz) & ~h["is_exit"].to_numpy()
        E = h[m_eval]
        counts = {"grp_all=0": len(E)}
        for a in ATTRS:
            for lv, n in E.groupby(a).size().items():
                counts[f"{a}={int(lv)}"] = int(n)
        for key, n in counts.items():
            rows.append({"split": name, "group": key, "eval_hops": n})
        for wk, Ew in E.groupby("week"):
            r = {"split": name, "week_monday": wk, "grp_all=0": len(Ew)}
            for a in ATTRS:
                for lv, n in Ew.groupby(a).size().items():
                    r[f"{a}={int(lv)}"] = int(n)
            wrows.append(r)
    G = pd.DataFrame(rows); G.to_csv(OUT / "split_group_counts.csv", index=False)
    pd.DataFrame(wrows).fillna(0).to_csv(OUT / "split_weekly_group_counts.csv", index=False)
    S = G.pivot(index="group", columns="split", values="eval_hops")
    summary = pd.DataFrame({sp: {"eval_non_exit_hops": S.loc["grp_all=0", sp], "re_acquired": S.loc["hopkind=2", sp],
                                 "smallest_group": S[sp].drop("grp_all=0").idxmin(), "smallest_group_hops": S[sp].drop("grp_all=0").min()}
                            for sp in SPLITS}).T
    summary.to_csv(OUT / "split_summary.csv")
    print(W.to_string()); print(summary.to_string()); print("days below half of median trips:", list(D.index[D.below_half_of_median]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true"); ap.add_argument("--build", action="store_true"); ap.add_argument("--count", action="store_true")
    a = ap.parse_args()
    if a.verify: verify()
    if a.build: build()
    if a.count: count()
