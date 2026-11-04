"""TAXI_ID per trip for the confirm2 work directory (DEVIATIONS.md D5). Reads the raw CSV only; no outcome.

    python confirm2_taxi_map.py

notes/confirm2/taxi_map.py (locked) replays porto.load without the duplicate-TRIP_ID rule, so its trip numbering does not
match work/porto_cctv_confirm2. This replays porto.load's filters AND the rule (records whose TRIP_ID occurs more than once
in the period removed; trips renumbered 0, 1, ...), keeps TAXI_ID, and checks the trip count and every trip's start time
against work/porto_cctv_confirm2/trajectories.parquet. Writes work/porto_cctv_confirm2/taxi_map.parquet.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from ccpilot.geo import date_to_unix, lonlat_to_xy  # noqa: E402
from ccpilot.posthoc import load_config  # noqa: E402


def main():
    cfg = load_config("configs/porto_cctv_confirm2.yaml"); p = cfg["porto"]; tz = cfg["timezone"]
    assert p.get("drop_duplicate_trip_id") == "both"
    t_start = date_to_unix(p["start_date"], tz); t_end = date_to_unix(p["end_date"], tz)
    lon0, lat0 = p["proj_center"]; step = p["gps_interval_s"]; vmax = p["max_speed_mps"]; bbox = p.get("bbox")
    taxi, t0, key, seen = [], [], [], {}
    for chunk in pd.read_csv(ROOT / p["csv_path"], usecols=["TRIP_ID", "TAXI_ID", "TIMESTAMP", "MISSING_DATA", "POLYLINE"],
                             dtype={"TRIP_ID": str}, chunksize=p.get("chunksize", 100_000)):
        miss = chunk["MISSING_DATA"].astype(str).str.lower().isin(["true", "1"])
        chunk = chunk[(~miss) & (chunk["TIMESTAMP"] >= t_start) & (chunk["TIMESTAMP"] < t_end)]
        for tk, tx, ts0, poly in zip(chunk["TRIP_ID"].to_numpy(), chunk["TAXI_ID"].to_numpy(), chunk["TIMESTAMP"].to_numpy(),
                                     chunk["POLYLINE"].to_numpy()):
            seen[tk] = seen.get(tk, 0) + 1
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
    keep = [i for i, k in enumerate(key) if seen[k] == 1]
    m = pd.DataFrame({"trip_id": np.arange(len(keep)), "taxi_id": np.array(taxi)[keep], "t0": np.array(t0)[keep],
                      "trip_key": np.array(key, dtype=object)[keep]})
    ref = pd.read_parquet(ROOT / "work/porto_cctv_confirm2/trajectories.parquet", columns=["trip_id", "t"]).groupby("trip_id").t.min()
    assert len(ref) == len(m) and np.array_equal(ref.to_numpy(), m.t0.to_numpy()), "replay does not match trajectories"
    m.to_parquet(ROOT / "work/porto_cctv_confirm2/taxi_map.parquet")
    print(f"[confirm2_taxi_map] trips={len(m)} taxis={m.taxi_id.nunique()} (start times identical); "
          f"duplicate TRIP_IDs removed: {sum(1 for c in seen.values() if c > 1)}")


if __name__ == "__main__":
    main()
