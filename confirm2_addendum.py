"""Write LOCK_confirm2_addendum.txt (camera-hash mismatch, DEVIATIONS.md D4). LOCK_confirm2.txt is not changed.

    python confirm2_addendum.py

Corrected content hash frame_sha256_v2 (definition below) recomputed for the camera table, the trip table and the hop
tables per block; the trip and hop tables must equal the lock values (frame_sha256 of the lock is correct for numeric
columns, and v2 is identical to it for numeric columns). File sha256 of the camera files and of the CCTV source, and the
column-wise comparison of the camera tables (176 sites). Exit code 1 if a trip or hop table differs from the lock.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from ccpilot.evaluate import _period_mask  # noqa: E402

DEFINITION = (
    "frame_sha256_v2(df): one sha256 over the columns in order; for each column: the UTF-8 column name, the dtype "
    "string, then the values. Numeric and boolean columns: the numpy values' bytes (C order), exactly as frame_sha256 "
    "of the lock. Object/string columns: for each value in row order, an 8-byte little-endian length followed by the "
    "UTF-8 bytes of str(value); a missing value is the length 0xFFFFFFFFFFFFFFFF with no bytes.")


def frame_sha256_v2(df):
    h = hashlib.sha256()
    for c in df.columns:
        s = df[c]
        h.update(str(c).encode("utf-8")); h.update(str(s.dtype).encode("utf-8"))
        if s.dtype.kind in "biufcM" and not isinstance(s.dtype, pd.StringDtype):
            h.update(np.ascontiguousarray(s.to_numpy()).tobytes())
        else:
            for v in s.to_numpy(dtype=object):
                if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
                    h.update((2 ** 64 - 1).to_bytes(8, "little"))
                else:
                    b = str(v).encode("utf-8")
                    h.update(len(b).to_bytes(8, "little")); h.update(b)
    return h.hexdigest()


def file_sha256(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def main():
    lock = json.load(open(ROOT / "results/porto_cctv_confirm2/lock_data_hashes.json"))
    A = yaml.safe_load(open(ROOT / "configs/confirm2_analysis.yaml"))
    w = ROOT / "work/porto_cctv_confirm2"
    cam_lock_src, cam_exec = "work/porto_cctv_confirm/cameras.csv", "work/porto_cctv_confirm2/cameras.csv"
    a, b = pd.read_csv(ROOT / cam_lock_src), pd.read_csv(ROOT / cam_exec)
    colcmp = {c: bool(c in b and a[c].equals(b[c])) for c in a.columns}
    traj = pd.read_parquet(w / "trajectories.parquet"); tr = pd.read_parquet(w / "transitions.parquet")
    res = {"trip_table": frame_sha256_v2(traj), "hop_table_all": frame_sha256_v2(tr)}
    t = tr.t_exit.to_numpy()
    for bname, B in A["blocks"].items():
        m = _period_mask(t, [B["train"][0], B["eval"][1]], "Europe/Lisbon")
        res[f"hop_table_{bname}"] = frame_sha256_v2(tr[m].reset_index(drop=True))
    same = {k: res[k] == lock[k]["sha256"] for k in res}
    L = ["# LOCK_confirm2_addendum.txt -- addendum to LOCK_confirm2.txt (DEVIATIONS.md D4); LOCK_confirm2.txt is unchanged",
         "", "## corrected content hash", DEFINITION, "",
         "## recomputed with frame_sha256_v2 (execution work directory work/porto_cctv_confirm2)",
         f"cameras (lock source {cam_lock_src}) {frame_sha256_v2(a)}",
         f"cameras (execution {cam_exec}) {frame_sha256_v2(b)}",
         f"cameras v2 equal: {frame_sha256_v2(a) == frame_sha256_v2(b)}"]
    for k in ("trip_table", "hop_table_all", "hop_table_block1", "hop_table_block2"):
        L.append(f"{k} {res[k]} | lock {lock[k]['sha256']} | {'EQUAL' if same[k] else 'DIFFERENT'}")
    L += ["", "## file sha256",
          f"{file_sha256(cam_lock_src)}  {cam_lock_src}", f"{file_sha256(cam_exec)}  {cam_exec}",
          f"{file_sha256('data/porto/porto_cctv.json')}  data/porto/porto_cctv.json",
          f"camera files byte-identical: {file_sha256(cam_lock_src) == file_sha256(cam_exec)}", "",
          f"## camera table, column-wise value equality ({len(a)} sites lock source, {len(b)} execution)"]
    L += [f"{c}: {'equal' if ok else 'DIFFERENT'}" for c, ok in colcmp.items()]
    L += ["", "## lock value for the cameras (not reproducible; kept as recorded): "
          f"{lock['cameras']['sha256']} (frame_sha256 hashed the pointer bytes of the string column cctv_ids)"]
    (ROOT / "LOCK_confirm2_addendum.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    if not all(same.values()) or not all(colcmp.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
