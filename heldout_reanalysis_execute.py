"""Held-out re-analysis runs (plan notes/instructions/PLAN_confirm2.md §12): 5 targets x evaluation seeds 0-4.

    nohup python heldout_reanalysis_execute.py > results/porto_cctv_heldout_reanalysis/execute.out 2>&1 &

configs/porto_cctv_heldout_reanalysis.yaml (frozen preprocessing; work/porto_cctv_confirm, read only) through
confirm2_run.py, at most 6 at a time. Output: results/porto_cctv_heldout_reanalysis/runs/t<target>/s<seed>/. A run whose
run_info.json exists is skipped. Each step is appended to results/porto_cctv_heldout_reanalysis/run_log.txt (command,
start and end time, exit code, commit, sha256 of the configuration).
"""
import hashlib
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/porto_cctv_heldout_reanalysis"
LOG = OUT / "run_log.txt"
CFG = "configs/porto_cctv_heldout_reanalysis.yaml"
MAX_PAR = 6


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def log(m):
    with open(LOG, "a") as fh:
        fh.write(m + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    sha = hashlib.sha256((ROOT / CFG).read_bytes()).hexdigest()
    A = yaml.safe_load(open(ROOT / CFG))["reanalysis"]
    log(f"# held-out re-analysis {now()} | commit {commit} | {CFG} sha256 {sha}")
    queue = [(t, s) for t in A["targets"] for s in A["seeds"]]
    running = []
    while queue or running:
        for p in list(running):
            if p[0].poll() is not None:
                running.remove(p); log(f"END   {now()} {p[1]} | exit {p[0].returncode}")
        while queue and len(running) < MAX_PAR:
            t, s = queue.pop(0)
            tag = f"t{int(round(t * 1000)):04d}"; label = f"heldout_{tag}_s{s}"
            out = OUT / "runs" / tag / f"s{s}"
            if (out / "run_info.json").exists():
                log(f"SKIP  {now()} {label} (complete)"); continue
            out.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-u", "confirm2_run.py", "--config", CFG, "--target", str(t), "--seed", str(s),
                   "--out", str(out.relative_to(ROOT))]
            log(f"START {now()} {label} | cmd: {' '.join(cmd[1:])} | commit {commit} | config sha256 {sha}")
            running.append((subprocess.Popen(cmd, cwd=ROOT, stdout=open(out.parent / f"s{s}.log", "a"),
                                             stderr=subprocess.STDOUT), label))
        time.sleep(30)
    log(f"# all queued runs finished {now()}")


if __name__ == "__main__":
    main()
