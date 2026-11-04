"""POST-HOC cost-matched comparison (not pre-registered; report as post hoc).

    python posthoc_frontier.py --config configs/porto_cctv_confirm.yaml

Traces worst-group recall vs search cost for static, CityTrac-style and mvp_log at several
targets, and reports (i) each method's worst group at the cost mvp_log spends at target
0.95 and (ii) the smallest cost at which each method has no group significantly below
the 0.94 bar. Output: <out_dir>_posthoc/frontier/.
"""
import argparse
import copy
from pathlib import Path

from ccpilot import frontier
from ccpilot.posthoc import load_config, load_work, set_display

PREREG_25 = ["grp_all", "hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
TARGETS = {
    "static":   [0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99],
    "citytrac": [0.70, 0.75, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.99],
    "mvp_log":  [0.93, 0.94, 0.95, 0.96, 0.97],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--groups", choices=["as_run", "prereg_25"], default="as_run",
                    help="group set for worst group / n_sig (prereg_25 -> frontier_prereg25/)")
    a = ap.parse_args()
    cfg = copy.deepcopy(load_config(a.config))
    cfg["eval"].setdefault("citytrac", {"window_q": 0.98, "min_n": 30})
    trans, truth, cams, n_bins = load_work(cfg)
    if a.groups == "prereg_25":      # judge on the pre-registered 25 groups (D1); config file not edited
        cfg["eval"]["strata"] = PREREG_25
    out = Path(cfg["out_dir"] + "_posthoc") / ("frontier" if a.groups == "as_run" else "frontier_prereg25")
    df, summ = frontier.run(cfg, trans, truth, cams, n_bins, out, a.predictor, TARGETS)
    set_display(300)
    print("\n================ POST-HOC FRONTIER (not pre-registered) ================")
    print(df[["method", "target", "segment", "coverage", "worst_group_cov", "worst_group",
              "n_groups_sig_below_bar", "cost_over_oracle"]].round(3).to_string(index=False))
    print("\n[cost-matched comparison]")
    print(summ.round(3).to_string(index=False))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
