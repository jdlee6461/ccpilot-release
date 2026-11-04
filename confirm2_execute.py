"""Execute confirmation experiment 2 (plan notes/instructions/PLAN_confirm2.md §11.3): data, events, 50 runs.

    nohup python confirm2_execute.py > results/porto_cctv_confirm2/execute.out 2>&1 &

1. Data and events of the candidate period with the base configuration (run_pilot.py --stage data / events on
   configs/porto_cctv_confirm2.yaml, work/porto_cctv_confirm2), unless already present. Checked against the lock: trip
   table and transitions (= hop table without visibility sets) by content hash; cameras by file bytes, column values and
   the corrected content hash of LOCK_confirm2_addendum.txt (DEVIATIONS.md D4). Any difference stops the execution.
2. 50 runs: 5 targets x 2 blocks x evaluation seeds 0-4, `confirm2_run.py --execute-confirm2` on the generated run files,
   at most 6 at a time. Output: results/porto_cctv_confirm2/runs/<block>/t<target>/s<seed>/. A run whose run_info.json
   exists is complete and is skipped (rerun after an interruption = the same command).
Every step is appended to results/porto_cctv_confirm2/run_log.txt: command, start and end time, exit code, code commit,
sha256 of the run file. Nothing is summarised or aggregated here.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/porto_cctv_confirm2"
LOG = OUT / "run_log.txt"
BASE = "configs/porto_cctv_confirm2.yaml"
MAX_PAR = 6


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(msg):
    with open(LOG, "a") as fh:
        fh.write(msg + "\n")


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def run_step(cmd, label):
    t0 = now()
    log(f"START {t0} {label} | cmd: {' '.join(cmd)} | commit {commit()}")
    r = subprocess.run(cmd, cwd=ROOT, stdout=open(OUT / f"{label}.log", "a"), stderr=subprocess.STDOUT)
    log(f"END   {now()} {label} | exit {r.returncode}")
    if r.returncode:
        log(f"STOP  {now()} {label} failed"); sys.exit(1)


def check_data():
    """Data check against the lock. Trip table and transitions: content hash (numeric columns) = LOCK values.
    Cameras (DEVIATIONS.md D4; the lock's camera content hash is not reproducible): (i) the file is byte-identical to the
    file read at the lock (work/porto_cctv_confirm/cameras.csv), (ii) every column has equal values, (iii) the corrected
    content hash frame_sha256_v2 equals LOCK_confirm2_addendum.txt."""
    sys.path.insert(0, str(ROOT))
    import pandas as pd
    from confirm2_addendum import frame_sha256_v2
    lock = json.load(open(OUT / "lock_data_hashes.json"))
    w = ROOT / "work/porto_cctv_confirm2"
    res = {"trip_table": frame_sha256_v2(pd.read_parquet(w / "trajectories.parquet")),
           "hop_table_all": frame_sha256_v2(pd.read_parquet(w / "transitions.parquet"))}
    ok = True
    for k in res:
        same = res[k] == lock[k]["sha256"]; ok &= same
        log(f"CHECK {now()} {k} sha256(content) {res[k]} lock {lock[k]['sha256']} {'OK' if same else 'DIFFERENT'}")
    src, cur = "work/porto_cctv_confirm/cameras.csv", "work/porto_cctv_confirm2/cameras.csv"
    f_ok = sha(src) == sha(cur)
    a, b = pd.read_csv(ROOT / src), pd.read_csv(ROOT / cur)
    c_ok = list(a.columns) == list(b.columns) and all(a[c].equals(b[c]) for c in a.columns)
    add = [ln for ln in (ROOT / "LOCK_confirm2_addendum.txt").read_text().splitlines() if ln.startswith("cameras (lock source")]
    v2 = frame_sha256_v2(b); h_ok = len(add) == 1 and add[0].split()[-1] == v2
    log(f"CHECK {now()} cameras file sha256 {sha(cur)} vs {src} {sha(src)} {'OK' if f_ok else 'DIFFERENT'}")
    log(f"CHECK {now()} cameras column-wise values ({len(b)} sites) {'OK' if c_ok else 'DIFFERENT'}")
    log(f"CHECK {now()} cameras sha256_v2(content) {v2} addendum {add[0].split()[-1] if add else 'missing'} {'OK' if h_ok else 'DIFFERENT'}")
    if not (ok and f_ok and c_ok and h_ok):
        log(f"STOP  {now()} data differ from the lock"); sys.exit(1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"# confirm2 execution {now()} | commit {commit()} | base {BASE} sha256 {sha(BASE)}")
    w = ROOT / "work/porto_cctv_confirm2"
    if not (w / "trajectories.parquet").exists() or not (w / "cameras.csv").exists():
        run_step([sys.executable, "-u", "run_pilot.py", "--config", BASE, "--stage", "data"], "stage_data")
    if not (w / "transitions.parquet").exists() or not (w / "truth.parquet").exists():
        run_step([sys.executable, "-u", "run_pilot.py", "--config", BASE, "--stage", "events"], "stage_events")
    check_data()
    A = yaml.safe_load(open(ROOT / "configs/confirm2_analysis.yaml"))
    queue = []
    for bname in A["blocks"]:
        for t in A["targets"]:
            tag = f"t{int(round(t * 1000)):04d}"
            cfg = f"configs/confirm2/porto_cctv_confirm2_{bname}_{tag}.yaml"
            for s in A["seeds"]["method"]:
                out = OUT / "runs" / bname / tag / f"s{s}"
                queue.append((cfg, t, s, out, f"{bname}_{tag}_s{s}"))
    running = []
    while queue or running:
        for p in list(running):
            if p[0].poll() is not None:
                running.remove(p)
                log(f"END   {now()} {p[1]} | exit {p[0].returncode}")
        while queue and len(running) < MAX_PAR:
            cfg, t, s, out, label = queue.pop(0)
            if (out / "run_info.json").exists():
                log(f"SKIP  {now()} {label} (complete: run_info.json exists)"); continue
            cmd = [sys.executable, "-u", "confirm2_run.py", "--config", cfg, "--target", str(t), "--seed", str(s),
                   "--out", str(out.relative_to(ROOT)), "--execute-confirm2"]
            out.parent.mkdir(parents=True, exist_ok=True)
            fh = open(out.parent / f"s{s}.log", "a")
            log(f"START {now()} {label} | cmd: {' '.join(cmd[1:])} | commit {commit()} | config sha256 {sha(cfg)}")
            running.append((subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT), label))
        time.sleep(30)
    log(f"# all queued runs finished {now()}")


if __name__ == "__main__":
    main()
