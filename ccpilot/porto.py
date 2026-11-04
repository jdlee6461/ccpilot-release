"""Loader for the ECML/PKDD 2015 Porto taxi dataset (train.csv).

Expected columns: TRIP_ID, CALL_TYPE, ORIGIN_CALL, ORIGIN_STAND, TAXI_ID,
TIMESTAMP, DAY_TYPE, MISSING_DATA, POLYLINE. POLYLINE is a JSON list of
[lon, lat] pairs sampled every 15 s starting at TIMESTAMP (unix seconds).
Please verify these assumptions against your downloaded copy.
"""
import json

import numpy as np
import pandas as pd
from tqdm import tqdm

from .geo import date_to_unix, lonlat_to_xy


def load(cfg):
    p = cfg["porto"]
    tz = cfg["timezone"]
    t_start = date_to_unix(p["start_date"], tz)
    t_end = date_to_unix(p["end_date"], tz)
    lon0, lat0 = p["proj_center"]
    step = p["gps_interval_s"]
    vmax = p["max_speed_mps"]
    bbox = p.get("bbox")  # [lon_min, lat_min, lon_max, lat_max] or None

    tids, ts, xs, ys = [], [], [], []
    keys, seen = [], {}       # TRIP_ID of kept trips; count of every record passing the date / missing-data filter
    trip_id = 0
    n_read = n_bad_speed = n_short = 0
    reader = pd.read_csv(
        p["csv_path"],
        usecols=["TRIP_ID", "TAXI_ID", "TIMESTAMP", "MISSING_DATA", "POLYLINE"], dtype={"TRIP_ID": str},
        chunksize=p.get("chunksize", 100_000),
    )
    for chunk in tqdm(reader, desc="reading Porto CSV"):
        miss = chunk["MISSING_DATA"].astype(str).str.lower().isin(["true", "1"])
        chunk = chunk[(~miss) & (chunk["TIMESTAMP"] >= t_start) & (chunk["TIMESTAMP"] < t_end)]
        for tk, ts0, poly in zip(chunk["TRIP_ID"].to_numpy(), chunk["TIMESTAMP"].to_numpy(), chunk["POLYLINE"].to_numpy()):
            n_read += 1
            seen[tk] = seen.get(tk, 0) + 1
            pts = json.loads(poly)
            if len(pts) < 3:
                n_short += 1
                continue
            arr = np.asarray(pts, dtype=float)
            if bbox is not None:
                inside = ((arr[:, 0] >= bbox[0]) & (arr[:, 0] <= bbox[2]) &
                          (arr[:, 1] >= bbox[1]) & (arr[:, 1] <= bbox[3]))
                if not inside.any():
                    continue
            x, y = lonlat_to_xy(arr[:, 0], arr[:, 1], lon0, lat0)
            v = np.hypot(np.diff(x), np.diff(y)) / step
            if np.any(v > vmax):          # GPS jump -> drop whole trip (simple, conservative)
                n_bad_speed += 1
                continue
            tids.append(np.full(len(x), trip_id, dtype=np.int64))
            ts.append(ts0 + step * np.arange(len(x), dtype=float))
            xs.append(x); ys.append(y); keys.append(tk)
            trip_id += 1
            if p.get("max_trips") and trip_id >= p["max_trips"]:
                break
        if p.get("max_trips") and trip_id >= p["max_trips"]:
            break
    print(f"[porto] trips read={n_read}, kept={trip_id}, "
          f"dropped(short)={n_short}, dropped(speed>{vmax}m/s)={n_bad_speed}")
    if p.get("drop_duplicate_trip_id") == "both":   # confirm2 candidate period (2026-10-14); default: keep (frozen behaviour)
        dup = {k for k, c in seen.items() if c > 1}
        keep = [i for i, k in enumerate(keys) if k not in dup]
        print(f"[porto] duplicate TRIP_IDs in range: {sorted(dup)}; kept trips removed: {len(keys) - len(keep)}")
        tids = [np.full(len(tids[i]), j, dtype=np.int64) for j, i in enumerate(keep)]
        ts = [ts[i] for i in keep]; xs = [xs[i] for i in keep]; ys = [ys[i] for i in keep]
    return pd.DataFrame({
        "trip_id": np.concatenate(tids), "t": np.concatenate(ts),
        "x": np.concatenate(xs), "y": np.concatenate(ys),
    })
