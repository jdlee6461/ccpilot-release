"""confirm2 alternative-partition attributes per hop (plan §8.1); evaluation-only, no method is run.

    python confirm2_attributes.py --work work/porto_cctv --train 2013-11-04 2013-12-02 --out work/porto_cctv/attr_expl1.parquet

From the work directory's trajectories, sightings, transitions and cameras (all hops, keyed by tr_id):
  hour        local hour of the exit (Europe/Lisbon), 24 cells
  hour3       hour // 3, 8 cells (0-3-6-...-24 h)
  zone8       exit-point angle relative to the camera centre (as events.extract_sightings: 0 = east, counter-clockwise),
              45-degree sectors with boundaries -45, 0, 45, ... degrees, nested in the 4 exit zones (plan §8.1):
              zone8 = floor(mod(rel + pi/4, 2 pi) / (pi/4)), so zone8 // 2 == zone (checked)
  speed_bin5, entropy_bin5, nn_bin5   quintiles, same code path as the quartiles (evaluate._add_strata / _add_spatial,
              k = 5) with boundaries from the block's training interval
The exit angle is not stored by events.py; it is recomputed from the trajectory at the sighting's exit time (the same
interpolation as extract_sightings), and the 4-zone recomputed from it must equal the stored zone for every hop.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask
from ccpilot.posthoc import load_config

TZ = "Europe/Lisbon"


def exit_angle(work, sig):
    traj = pd.read_parquet(work / "trajectories.parquet").sort_values(["trip_id", "t"], kind="stable")
    cams = pd.read_csv(work / "cameras.csv")
    tr = traj.trip_id.to_numpy(); t = traj.t.to_numpy(); x = traj.x.to_numpy(); y = traj.y.to_numpy()
    bnd = np.flatnonzero(np.diff(tr)) + 1; st = np.r_[0, bnd]; en = np.r_[bnd, len(tr)]
    pos = dict(zip(tr[st], zip(st, en)))
    sig = sig.sort_values("trip_id", kind="stable").reset_index(drop=True)
    xe = np.empty(len(sig)); ye = np.empty(len(sig))
    sid = sig.trip_id.to_numpy(); tout = sig.t_out.to_numpy()
    b = np.flatnonzero(np.diff(sid)) + 1; ss = np.r_[0, b]; ee = np.r_[b, len(sid)]
    for a, z in zip(ss, ee):
        s, e = pos[sid[a]]
        xe[a:z] = np.interp(tout[a:z], t[s:e], x[s:e]); ye[a:z] = np.interp(tout[a:z], t[s:e], y[s:e])
    cx = cams.x.to_numpy()[sig.cam.to_numpy()]; cy = cams.y.to_numpy()[sig.cam.to_numpy()]
    return sig.assign(rel=np.arctan2(ye - cy, xe - cx))


def build(work, train, cfg_tz=TZ):
    work = Path(work)
    trans = pd.read_parquet(work / "transitions.parquet"); cams = pd.read_csv(work / "cameras.csv")
    sig = exit_angle(work, pd.read_parquet(work / "sightings.parquet"))
    key = sig[["trip_id", "cam", "t_out", "rel"]].rename(columns={"cam": "src", "t_out": "t_exit"})
    assert not key.duplicated(["trip_id", "src", "t_exit"]).any()
    n0 = len(trans)
    trans = trans.merge(key, on=["trip_id", "src", "t_exit"], how="left", validate="one_to_one")
    assert len(trans) == n0 and trans.rel.notna().all()
    rel = trans.rel.to_numpy()
    z4 = (np.floor(np.mod(rel + np.pi / 4, 2 * np.pi) / (np.pi / 2)).astype(int)) % 4
    assert np.array_equal(z4, trans.zone.to_numpy()), "recomputed exit zone differs from the stored zone"
    zone8 = (np.floor(np.mod(rel + np.pi / 4, 2 * np.pi) / (np.pi / 4)).astype(int)) % 8
    assert np.array_equal(zone8 // 2, trans.zone.to_numpy())
    m_tr = _period_mask(trans.t_exit.to_numpy(), train, cfg_tz)
    h5 = _add_spatial(_add_strata(trans, trans[m_tr], 5), m_tr, cams, 5)
    out = pd.DataFrame({"tr_id": trans.tr_id.to_numpy(), "hour": trans.hour.to_numpy(), "hour3": trans.hour.to_numpy() // 3,
                        "zone8": zone8, "speed_bin5": h5.speed_bin.to_numpy(), "entropy_bin5": h5.entropy_bin.to_numpy(),
                        "nn_bin5": h5.nn_bin.to_numpy()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--train", nargs=2, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = build(a.work, a.train)
    out.to_parquet(a.out)
    print(f"[attributes] {a.work}: {len(out)} hops -> {a.out}")


if __name__ == "__main__":
    main()
