"""POST-HOC sensitivity analyses (not part of the pre-registration; report as post hoc).

    python posthoc_sensitivity.py --config configs/porto_cctv_confirm.yaml
    python posthoc_sensitivity.py --config configs/porto_cctv_confirm.yaml --scenarios fb010 fb100 det090

Re-uses the events already computed for the config (work_dir). For speed, only the
primary predictor and a reduced method set are evaluated.

Scenarios
  feedback  : fraction of background transitions that give feedback, and whether it is
              delayed (realistic: arrival time / t_exit + T_max) or immediate (theory setting)
  detection : each camera visit of the target is detected with probability p_det.
              Training, calibration and feedback only see DETECTED visits (the system
              cannot tell 'searched the right place but missed it' from 'wrong place');
              'coverage' = the search set contained the target's true visit,
              'coverage_detected' = ... and the target was also detected there.
              adjust=true calibrates observed coverage to (1-alpha)*p_det, assuming p_det
              is known from detector validation.
"""
import argparse
import copy
from pathlib import Path

import pandas as pd

from ccpilot import evaluate
from ccpilot.posthoc import add_cost_over_oracle, load_config, load_work, reduce_cfg, set_display

SCENARIOS = {
    "fb010":        {"feedback_fraction": 0.1},
    "fb030":        {"feedback_fraction": 0.3},                    # = pre-registered setting
    "fb100":        {"feedback_fraction": 1.0},
    "fb100_nodelay": {"feedback_fraction": 1.0, "feedback_delay": "none"},   # MVP theory setting
    "det095":       {"p_det": 0.95},
    "det090":       {"p_det": 0.90},
    "det095_adj":   {"p_det": 0.95, "adjust_target": True},
    "det090_adj":   {"p_det": 0.90, "adjust_target": True},
}
METHODS = ["static", "mondrian_hour_hop_speed", "aci_g0005", "mvp_log", "mvp_global",
           "qr_groups", "qr_ogd", "oracle(post-hoc)", "target095", "target099", "fixed"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    a = ap.parse_args()
    base = load_config(a.config)
    trans, truth, cams, n_bins = load_work(base)
    root = Path(base["out_dir"] + "_posthoc")
    allres = []
    for sc in a.scenarios:
        spec = SCENARIOS[sc]
        cfg = reduce_cfg(copy.deepcopy(base), a.predictor)
        ex = cfg["eval"]
        if "feedback_fraction" in spec:
            ex["aci"]["feedback_fraction"] = spec["feedback_fraction"]
        if "feedback_delay" in spec:
            ex["aci"]["feedback_delay"] = spec["feedback_delay"]
        if "p_det" in spec:
            ex["detection"] = {"p_det": spec["p_det"], "adjust_target": spec.get("adjust_target", False),
                               "train_on_detected": True, "seed": 1}
        print(f"\n########## scenario {sc}: {spec}")
        res, _, _ = evaluate.run(cfg, trans, truth, cams, n_bins, root / sc)
        res.insert(0, "scenario", sc)
        allres.append(res)
    df = pd.concat(allres, ignore_index=True)
    df = df[df["method"].isin(METHODS)]
    add_cost_over_oracle(df, "scenario")
    root.mkdir(parents=True, exist_ok=True)
    df.to_csv(root / "sensitivity_summary.csv", index=False)
    cols = ["scenario", "method", "segment", "target_used", "coverage", "coverage_detected",
            "worst_group_cov", "n_groups_sig_below_bar", "cost_mean_cam_s", "cost_over_oracle"]
    set_display()
    print("\n================ POST-HOC SENSITIVITY (not pre-registered) ================")
    print(df[cols].round(3).to_string(index=False))
    print(f"\n-> {root / 'sensitivity_summary.csv'}")


if __name__ == "__main__":
    main()
