"""confirm2 / re-analysis evaluation run: one (configuration, target, evaluation seed).

    python confirm2_run.py --config configs/porto_cctv.yaml --target 0.95 --seed 0 --out work/trial_expl1/t095_s0
    python confirm2_run.py --config configs/porto_cctv_heldout_reanalysis.yaml --target 0.95 --seed 0 --out ...

The base configuration is read and copied in memory (never written); the target recall, the evaluation seed and the
run options of configs/confirm2_analysis.yaml (qr_groups_refit, qr_groups_refit7, per-hop outputs) are added, and the
evaluation stage of run_pilot.py is run on the base configuration's existing work directory.

GUARD: a configuration whose Porto data range overlaps the candidate period 2013-07-01 .. 2013-11-03 is refused unless
(i) it is one of the generated run files configs/confirm2/*.yaml, (ii) the tag confirm2-plan exists and the file is
byte-identical to its version at that tag, and (iii) --execute-confirm2 is given (the run is instructed separately).
The output directory must not be the frozen results/porto_cctv_confirm/.
"""
import argparse
import copy
import json
import subprocess
import time
from pathlib import Path

import pandas as pd
import yaml

from ccpilot import evaluate
from ccpilot.posthoc import load_config

ANALYSIS = "configs/confirm2_analysis.yaml"
NEW_PERIOD = ("2013-07-01", "2013-11-04")
FROZEN_OUT = Path("results/porto_cctv_confirm").resolve()


def locked_ok(base):
    rel = Path(base).resolve().relative_to(Path.cwd().resolve()).as_posix()
    if not rel.startswith("configs/confirm2/"):
        return False, "not a generated confirm2 run file"
    if subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/tags/confirm2-plan"], capture_output=True).returncode:
        return False, "tag confirm2-plan does not exist"
    tagged = subprocess.run(["git", "show", f"confirm2-plan:{rel}"], capture_output=True)
    if tagged.returncode or tagged.stdout != Path(base).read_bytes():
        return False, "file differs from its version at tag confirm2-plan"
    return True, ""


def build_cfg(base, target, seed, out, execute=False):
    cfg = copy.deepcopy(load_config(base))
    p = cfg["porto"]
    if not (p["end_date"] <= NEW_PERIOD[0] or p["start_date"] >= NEW_PERIOD[1]):
        ok, why = locked_ok(base)
        if not (ok and execute):
            raise SystemExit(f"refused: {base} overlaps the confirm2 candidate period {NEW_PERIOD}: "
                             f"{why or 'execution needs --execute-confirm2'}")
        if abs(float(cfg["eval"]["target_recall"]) - float(target)) > 1e-12:
            raise SystemExit("refused: --target differs from the run file's target")
    if Path(out).resolve() == FROZEN_OUT or FROZEN_OUT in Path(out).resolve().parents:
        raise SystemExit("refused: output inside the frozen results/porto_cctv_confirm/")
    ro = yaml.safe_load(open(ANALYSIS))["run_options"]
    ex = cfg["eval"]
    ex["target_recall"] = float(target)
    ex["seed"] = int(seed)
    ex["multigroup"]["qr_refit"] = copy.deepcopy(ro["multigroup_qr_refit"])
    ex["citytrac"] = copy.deepcopy(ro["citytrac"])
    for k in ["save_hits", "save_scores", "save_feedback_mask", "save_cost_lookup", "save_detect_time"]:
        ex[k] = copy.deepcopy(ro[k])
    cfg["out_dir"] = str(out)
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--target", type=float, required=True)
    ap.add_argument("--seed", type=int, required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--execute-confirm2", action="store_true", help="run a locked confirm2 run file (separate instruction)")
    a = ap.parse_args()
    cfg = build_cfg(a.config, a.target, a.seed, a.out, a.execute_confirm2)
    w = Path(cfg["work_dir"])
    trans = pd.read_parquet(w / "transitions.parquet"); truth = pd.read_parquet(w / "truth.parquet")
    cams = pd.read_csv(w / "cameras.csv"); n_bins = json.load(open(w / "meta.json"))["n_bins"]
    t0 = time.time()
    evaluate.run(cfg, trans, truth, cams, n_bins, cfg["out_dir"])
    el = time.time() - t0
    Path(cfg["out_dir"]).mkdir(parents=True, exist_ok=True)
    yaml.safe_dump(cfg, open(Path(cfg["out_dir"]) / "run_config.yaml", "w"), sort_keys=False)
    json.dump({"config": a.config, "target": a.target, "seed": a.seed, "eval_seconds": el,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0))},
              open(Path(cfg["out_dir"]) / "run_info.json", "w"), indent=1)
    print(f"[confirm2_run] {a.config} target={a.target} seed={a.seed}: {el:.0f}s -> {cfg['out_dir']}")


if __name__ == "__main__":
    main()
