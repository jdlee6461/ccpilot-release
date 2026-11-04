"""POST-HOC seed repetition (not pre-registered; report as post hoc).

    python posthoc_seeds.py --config configs/porto_cctv_confirm.yaml --seeds 0 1 2 3 4

The seed drives (i) which background transitions provide feedback, (ii) MVP's randomised
threshold choice and (iii) the QR subsample. Seed 0 reproduces the pre-registered run.
Also evaluates the CityTrac-style and Spatula-style baselines (deterministic).
Output: <out_dir>_posthoc/seeds/seed_k/summary.csv and seeds_summary.csv (mean/sd/min/max)
plus, for the candidate methods, how many seeds satisfy the pre-registered C1 and C2.
"""
import argparse
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot import evaluate
from ccpilot.posthoc import add_cost_over_oracle, load_config, load_work, reduce_cfg, set_display

PREREG_25 = ["grp_all", "hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
KEEP = ["static", "mondrian_hour_hop_speed", "aci_g0005", "mvp_log", "mvp_global", "qr_groups",
        "qr_ogd", "oracle(post-hoc)", "target095", "target099", "fixed"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--seeds", nargs="*", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--groups", choices=["as_run", "prereg_25"], default="as_run",
                    help="group set for n_groups_sig_below_bar / worst group (prereg_25 -> seeds_prereg25/, hits saved)")
    ap.add_argument("--combine", action="store_true", help="read seed_k/summary.csv of earlier (parallel) runs")
    a = ap.parse_args()
    base = load_config(a.config)
    trans, truth, cams, n_bins = load_work(base)
    root = Path(base["out_dir"] + "_posthoc") / ("seeds" if a.groups == "as_run" else "seeds_prereg25")
    allres = []
    for sd in a.seeds:
        cfg = reduce_cfg(copy.deepcopy(base), a.predictor)
        cfg["eval"]["seed"] = sd
        if a.groups == "prereg_25":      # judge on the pre-registered 25 groups (D1); config file not edited
            cfg["eval"]["strata"] = PREREG_25
            cfg["eval"]["save_hits"] = True
        print(f"\n########## seed {sd}")
        if a.combine:
            res = pd.read_csv(root / f"seed_{sd}" / "summary.csv")
        else:
            res, _, _ = evaluate.run(cfg, trans, truth, cams, n_bins, root / f"seed_{sd}")
        res.insert(0, "seed", sd)
        allres.append(res)
    df = pd.concat(allres, ignore_index=True)
    df = df[df["method"].isin(KEEP)].copy()
    add_cost_over_oracle(df, "seed")
    df["label"] = np.where(df["predictor"] == a.predictor, df["method"], df["predictor"] + "/" + df["method"])
    root.mkdir(parents=True, exist_ok=True)
    df.to_csv(root / "seeds_all.csv", index=False)
    metrics = ["coverage", "worst_group_cov", "n_groups_sig_below_bar", "cost_mean_cam_s", "cost_over_oracle"]
    agg = df.groupby(["label", "segment"])[metrics].agg(["mean", "std", "min", "max"])
    agg.to_csv(root / "seeds_summary.csv")
    # pre-registered criteria per seed (C1: no group significantly below bar in each segment;
    # C2: mean over segments of cost/oracle <= 1.20)
    rows = []
    for (lab, sd), g in df.groupby(["label", "seed"]):
        rows.append({"label": lab, "seed": sd, "C1": bool((g["n_groups_sig_below_bar"] == 0).all()),
                     "C2": bool(g["cost_over_oracle"].mean() <= 1.20),
                     "min_worst_group": g["worst_group_cov"].min(), "mean_cost_ratio": g["cost_over_oracle"].mean()})
    crit = pd.DataFrame(rows)
    crit.to_csv(root / "seeds_criteria.csv", index=False)
    set_display()
    print("\n================ POST-HOC SEED REPETITION (not pre-registered) ================")
    show = df.groupby(["label", "segment"]).agg(
        coverage=("coverage", "mean"), worst_mean=("worst_group_cov", "mean"), worst_min=("worst_group_cov", "min"),
        worst_sd=("worst_group_cov", "std"), nsig_mean=("n_groups_sig_below_bar", "mean"),
        nsig_max=("n_groups_sig_below_bar", "max"), cost_ratio=("cost_over_oracle", "mean"),
        cost_ratio_sd=("cost_over_oracle", "std")).round(4)
    print(show.to_string())
    print("\n[pre-registered criteria per seed: number of seeds passing]")
    print(crit.groupby("label")[["C1", "C2"]].sum().astype(int).assign(n_seeds=crit.groupby("label").size()).to_string())
    print(f"\n-> {root}")


if __name__ == "__main__":
    main()
