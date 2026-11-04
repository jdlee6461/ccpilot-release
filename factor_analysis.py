"""Factor analysis on an EXPLORATORY period.

    python factor_analysis.py --config configs/porto_replication.yaml
    python factor_analysis.py --config configs/porto.yaml --predictor src_zone_hour_speed

Refuses to run on the confirmation config (held-out data must stay unseen).
Requires: scikit-learn, statsmodels  (conda install -c conda-forge scikit-learn statsmodels)
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

from ccpilot import factors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--force", action="store_true", help="allow running on a confirmation config")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    if "confirm" in (a.config + cfg["work_dir"] + cfg["out_dir"]) and not a.force:
        raise SystemExit("Refusing to analyse the held-out confirmation period (use --force only after "
                         "the pre-registered confirmation run is completed).")
    work = Path(cfg["work_dir"]); out = Path(cfg["out_dir"]) / "factors"
    R = factors.run(cfg, a.predictor, work, out)

    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    pd.set_option("display.max_colwidth", 120)
    print("\n[delay spread by exit-speed bin] (0 = slowest)")
    print(R["delay_by_speed"].round(3).to_string())
    for oc in ["miss_static", "miss_qr"]:
        r = R[oc]
        print(f"\n================ {oc}  (overall miss rate = {r['overall']:.4f}) ================")
        print("[factor ranking: max-min miss rate across levels with n>=500]")
        print(r["spread"].round(4).to_string())
        print("\n[univariate: levels with the highest miss rate]")
        u = r["uni"][r["uni"]["n"] >= 500].sort_values("miss_rate", ascending=False).head(12)
        print(u[["factor", "level", "n", "share", "miss_rate", "ci_lo", "ci_hi", "ratio_to_overall"]]
              .round(4).to_string(index=False))
        lg = r["logit"]
        sig = lg[lg["p_value"] < 1e-3].copy()
        sig["abs_log_or"] = abs(pd.Series(sig["odds_ratio"]).apply(lambda v: __import__("math").log(v)))
        print(f"\n[logistic regression, n={r['n_logit']}: p<0.001, sorted by |log OR|; reference = most common level of each factor]")
        print(sig.sort_values("abs_log_or", ascending=False).drop(columns="abs_log_or").head(15)
              .round(3).to_string())
        print("\n[decision tree: leaves with highest miss rate]")
        print(r["leaves"].head(8).round(4).to_string())
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
