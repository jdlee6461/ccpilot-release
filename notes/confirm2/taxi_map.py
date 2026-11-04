"""Map trip_id -> TAXI_ID for an existing (already analysed) period by replaying porto.load's filters.

    python notes/confirm2/taxi_map.py --config configs/porto_cctv_confirm.yaml     # read only
    python notes/confirm2/taxi_map.py --candidate      # confirm2 candidate period (work/confirm2_hops); counts only

porto.load numbers kept trips 0,1,2,... and drops TAXI_ID. This replays the same filters on the same CSV, keeps TAXI_ID
and the trip start time, and checks the trip count and the start time of every trip against
<work_dir>/trajectories.parquet. Writes <work_dir>/taxi_map.parquet (git-ignored). No outcome is computed.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ccpilot.geo import date_to_unix, lonlat_to_xy  # noqa: E402
from ccpilot.posthoc import load_config  # noqa: E402


def main(cfg):
    p = cfg["porto"]; tz = cfg["timezone"]
    t_start = date_to_unix(p["start_date"], tz); t_end = date_to_unix(p["end_date"], tz)
    lon0, lat0 = p["proj_center"]; step = p["gps_interval_s"]; vmax = p["max_speed_mps"]; bbox = p.get("bbox")
    taxi, t0, key = [], [], []
    for chunk in pd.read_csv(p["csv_path"], usecols=["TRIP_ID", "TAXI_ID", "TIMESTAMP", "MISSING_DATA", "POLYLINE"], dtype={"TRIP_ID": str},
                             chunksize=p.get("chunksize", 100_000)):
        miss = chunk["MISSING_DATA"].astype(str).str.lower().isin(["true", "1"])
        chunk = chunk[(~miss) & (chunk["TIMESTAMP"] >= t_start) & (chunk["TIMESTAMP"] < t_end)]
        for tk, tx, ts0, poly in zip(chunk["TRIP_ID"].to_numpy(), chunk["TAXI_ID"].to_numpy(), chunk["TIMESTAMP"].to_numpy(),
                                     chunk["POLYLINE"].to_numpy()):
            arr = np.asarray(json.loads(poly), dtype=float)
            if len(arr) < 3:
                continue
            if bbox is not None and not ((arr[:, 0] >= bbox[0]) & (arr[:, 0] <= bbox[2]) &
                                         (arr[:, 1] >= bbox[1]) & (arr[:, 1] <= bbox[3])).any():
                continue
            x, y = lonlat_to_xy(arr[:, 0], arr[:, 1], lon0, lat0)
            if np.any(np.hypot(np.diff(x), np.diff(y)) / step > vmax):
                continue
            taxi.append(int(tx)); t0.append(float(ts0)); key.append(tk)
    assert not p.get("max_trips")
    m = pd.DataFrame({"trip_id": np.arange(len(taxi)), "taxi_id": taxi, "t0": t0, "trip_key": key})
    ref = pd.read_parquet(Path(cfg["work_dir"]) / "trajectories.parquet", columns=["trip_id", "t"]).groupby("trip_id").t.min()
    assert len(ref) == len(m) and np.array_equal(ref.to_numpy(), m.t0.to_numpy()), "replay does not match trajectories"
    m.to_parquet(Path(cfg["work_dir"]) / "taxi_map.parquet")
    print(f"[taxi_map] {cfg['work_dir']}: trips={len(m)} taxis={m.taxi_id.nunique()} (start times identical)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--config"); ap.add_argument("--candidate", action="store_true")
    a = ap.parse_args()
    if a.candidate:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from count_hops import candidate_cfg
        main(candidate_cfg())
    else:
        main(load_config(a.config))
