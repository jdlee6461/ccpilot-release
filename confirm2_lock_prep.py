"""confirm2 lock preparation (plan §11.2): data hashes and the duplicate-TRIP_ID exclusion counts. No method is run.

    python confirm2_lock_prep.py

Candidate period with the locked preprocessing (configs/porto_cctv_confirm2.yaml, drop_duplicate_trip_id: both):
  - sha256 of the raw CSV (data/porto/train.csv)
  - preprocessed trip table (porto.load) -> work/porto_cctv_confirm2_lockprep/trajectories.parquet and its content hash
  - hops built WITHOUT visibility sets (notes/confirm2/count_hops.build_hops = events.build_transitions minus truth,
    checked identical on the held-out period), per block (t_exit in [train start, eval end)) -> content hash
  - exclusion counts: trips and hops removed by the rule, against the hops counted on 2026-10-02 (work/confirm2_hops)
Content hash (frame_sha256): sha256 over, for every column in order, the column name, its dtype and the values' bytes
(C order, little-endian numpy representation). Independent of parquet encoding.
Writes results/porto_cctv_confirm2/lock_data_hashes.json and lock_exclusions.csv.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "notes/confirm2"))
from count_hops import build_hops  # noqa: E402
from ccpilot import events, porto  # noqa: E402
from ccpilot.evaluate import _period_mask  # noqa: E402
from ccpilot.posthoc import load_config  # noqa: E402
import yaml  # noqa: E402

BASE = "configs/porto_cctv_confirm2.yaml"
W = ROOT / "work/porto_cctv_confirm2_lockprep"
OUT = ROOT / "results/porto_cctv_confirm2"


def file_sha256(p, chunk=1 << 24):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def frame_sha256(df):
    h = hashlib.sha256()
    for c in df.columns:
        v = np.ascontiguousarray(df[c].to_numpy())
        h.update(str(c).encode()); h.update(str(v.dtype).encode()); h.update(v.tobytes())
    return h.hexdigest()


def main():
    cfg = load_config(BASE); tz = cfg["timezone"]
    A = yaml.safe_load(open(ROOT / "configs/confirm2_analysis.yaml"))
    W.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    rec = {"base_config": BASE, "hash_method": "frame_sha256: per column name, dtype, values bytes (numpy, C order)"}
    rec["raw_csv"] = {"path": cfg["porto"]["csv_path"], "sha256": file_sha256(ROOT / cfg["porto"]["csv_path"])}
    traj = porto.load(cfg)
    traj.to_parquet(W / "trajectories.parquet")
    rec["trip_table"] = {"trips": int(traj.trip_id.nunique()), "points": len(traj), "columns": list(traj.columns),
                         "sha256": frame_sha256(traj)}
    cams = pd.read_csv(ROOT / "work/porto_cctv_confirm/cameras.csv")
    cams.to_csv(W / "cameras.csv", index=False)
    rec["cameras"] = {"sites": len(cams), "sha256": frame_sha256(cams)}
    ev = cfg["events"]
    sig = events.extract_sightings(traj, cams, ev["camera_radius_m"], ev["interp_step_s"], ev.get("max_overlap", 4))
    hops = build_hops(sig, cfg)
    hops.to_parquet(W / "hops.parquet")
    rec["hop_table_all"] = {"rows": len(hops), "sha256": frame_sha256(hops)}
    t = hops.t_exit.to_numpy()
    rows = []
    old = pd.read_parquet(ROOT / "work/confirm2_hops/hops.parquet")
    to = old.t_exit.to_numpy()
    for bname, B in A["blocks"].items():
        m = _period_mask(t, [B["train"][0], B["eval"][1]], tz)
        hb = hops[m].reset_index(drop=True)
        rec[f"hop_table_{bname}"] = {"rows": len(hb), "range": [B["train"][0], B["eval"][1]], "sha256": frame_sha256(hb)}
        for split in ("train", "cal", "eval"):
            mn = _period_mask(t, B[split], tz) & ~hops.is_exit.to_numpy()
            mo = _period_mask(to, B[split], tz) & ~old.is_exit.to_numpy()
            hk = np.where(hops.hop > 0, 0, np.where(hops.chain == 0, 1, 2))
            ok = np.where(old.hop > 0, 0, np.where(old.chain == 0, 1, 2))
            rows.append({"block": bname, "split": split, "non_exit_hops_without_rule": int(mo.sum()),
                         "non_exit_hops_with_rule": int(mn.sum()), "removed": int(mo.sum() - mn.sum()),
                         "reacquired_without_rule": int((mo & (ok == 2)).sum()), "reacquired_with_rule": int((mn & (hk == 2)).sum())})
    E = pd.DataFrame(rows)
    rec["exclusion"] = {"trips_without_rule": int(len(pd.read_parquet(ROOT / "work/confirm2_hops/taxi_map.parquet"))), "trips_with_rule": int(traj.trip_id.nunique()),
                        "transitions_without_rule": len(old), "transitions_with_rule": len(hops)}
    E.to_csv(OUT / "lock_exclusions.csv", index=False)
    json.dump(rec, open(OUT / "lock_data_hashes.json", "w"), indent=1)
    print(json.dumps(rec, indent=1)); print(E.to_string(index=False))


if __name__ == "__main__":
    main()
