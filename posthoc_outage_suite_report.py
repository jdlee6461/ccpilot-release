"""POST-HOC summary of posthoc_outage_suite.py runs (not pre-registered; report as post hoc).

    python posthoc_outage_suite_report.py --configs configs/porto_cctv.yaml configs/porto_cctv_replication.yaml \\
        configs/porto_cctv_confirm.yaml

Per period x scenario x site seed x predictor x method x segment, from saved per-hop results:
  coverage, worst group / n below the bar on the PRE-REGISTERED 25 groups (Wilson 95 % upper bound),
  mean cost and two cost ratios:
    cost_over_oracle_same : / post-hoc oracle of the same predictor in the same run (same scenario)
    cost_over_oracle_none : / post-hoc oracle of the base predictor in the no-outage run of the same
                            period and segment (scenario 'none')
  ceiling_<a_min> : share of hops with score >= tau at q = 1 for that a_min (predictor-specific scores).
Output: outage_suite/suite_summary.csv per period and all_periods_summary.csv in the confirmation folder.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.posthoc import load_config, set_display
from posthoc_regrade import DEFS, group_rows

PRED = "src_zone_hour_speed"


def summarize_run(d, period, oracle_none, min_n):
    H = pd.read_parquet(d / "hits.parquet")
    S = pd.read_csv(d / "summary.csv")
    meta = pd.read_csv(d / "run_meta.csv").iloc[0]
    orc = S[S["method"] == "oracle(post-hoc)"].set_index(["predictor", "segment"])["cost_mean_cam_s"]
    rows = []
    for col in [c for c in H.columns if c.startswith("hit|")]:
        _, pred, meth = col.split("|")
        for seg in H["segment"].unique():
            ms = (H["segment"] == seg).to_numpy()
            gt = group_rows(H, col, DEFS["prereg_25"], seg, min_n)
            w = gt.loc[gt["coverage"].idxmin()]
            cost = H.loc[ms, col.replace("hit|", "cost|")].mean()
            r = {"period": period, "scenario": meta["scenario"], "site_seed": int(meta["site_seed"]),
                 "n_offline": int(meta["n_offline"]), "predictor": pred, "method": meth, "segment": seg,
                 "n": int(ms.sum()), "coverage": H.loc[ms, col].mean(),
                 "worst_group": f"{w['dim']}={w['group']}", "worst_cov": w["coverage"],
                 "n_sig_below_0.94": int((gt["ub95"] < 0.94).sum()), "n_sig_below_0.95": int((gt["ub95"] < 0.95).sum()),
                 "cost_mean_cam_s": cost,
                 # rule baselines (spatula, citytrac) have no oracle of their own -> NaN
                 "cost_over_oracle_same": cost / orc[(pred, seg)] if (pred, seg) in orc.index else np.nan,
                 "cost_over_oracle_none": cost / oracle_none.get(seg, np.nan)}
            sc = f"score|{pred}"
            if sc in H.columns:
                for a in ("0.001", "0.002", "0.005"):
                    tc = f"taumin{a}|{pred}"
                    if tc in H.columns:
                        r[f"ceiling_{a}"] = (H.loc[ms, sc] >= H[tc].iloc[0]).mean()
            rows.append(r)
    # oracle rows (cost ratios of the oracle itself)
    for (pred, seg), c in orc.items():
        o = S[(S["predictor"] == pred) & (S["segment"] == seg) & (S["method"] == "oracle(post-hoc)")].iloc[0]
        rows.append({"period": period, "scenario": meta["scenario"], "site_seed": int(meta["site_seed"]),
                     "n_offline": int(meta["n_offline"]), "predictor": pred, "method": "oracle(post-hoc)",
                     "segment": seg, "n": int(o["n"]), "coverage": o["coverage"], "cost_mean_cam_s": c,
                     "cost_over_oracle_same": 1.0, "cost_over_oracle_none": c / oracle_none.get(seg, np.nan)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", required=True)
    a = ap.parse_args()
    allrows = []
    for cfgp in a.configs:
        base = load_config(cfgp)
        period = base["out_dir"].split("/")[-1]
        root = Path(base["out_dir"] + "_posthoc") / "outage_suite"
        nd = root / "none_s7"
        if not (nd / "summary.csv").exists():
            print(f"[report] {period}: no 'none' run yet, skipped"); continue
        Sn = pd.read_csv(nd / "summary.csv")
        oracle_none = Sn[(Sn["predictor"] == PRED) & (Sn["method"] == "oracle(post-hoc)")].set_index("segment")[
            "cost_mean_cam_s"].to_dict()
        rows = []
        for d in sorted(root.glob("*_s*")):
            if (d / "hits.parquet").exists() and (d / "run_meta.csv").exists():
                rows += summarize_run(d, period, oracle_none, base["eval"].get("min_group_n", 200))
        T = pd.DataFrame(rows)
        T.to_csv(root / "suite_summary.csv", index=False)
        allrows.append(T)
        print(f"[report] {period}: {T[['scenario', 'site_seed']].drop_duplicates().shape[0]} runs")
    A = pd.concat(allrows, ignore_index=True)
    out = Path(load_config("configs/porto_cctv_confirm.yaml")["out_dir"] + "_posthoc") / "outage_suite"
    out.mkdir(parents=True, exist_ok=True)
    A.to_csv(out / "all_periods_summary.csv", index=False)
    set_display()
    print(f"-> {out / 'all_periods_summary.csv'} ({len(A)} rows)")


if __name__ == "__main__":
    main()
