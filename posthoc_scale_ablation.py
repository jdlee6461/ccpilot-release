"""POST-HOC ablation of mvp_log on the EXPLORATORY periods (not pre-registered; report as post hoc).

    python posthoc_scale_ablation.py --config configs/porto_cctv.yaml --modes normal rand10 region
    python posthoc_scale_ablation.py --config configs/porto_cctv.yaml --combine

Question: does mvp_log's lower cost under normal conditions come from the log-scale resolution
(fine buckets near miss level 0.05) or from the cap a_min (tau never below the a_min quantile)?
MVP variants (all 25 groups, same eta rule, seed and feedback as the registered runs):
  mvp_log         log buckets, a_min 0.002 (registered primary)
  unif_nocap      uniform buckets, no cap (= mvp_groups)
  unif_cap002     uniform buckets, miss level floored at 0.002 (cap without log resolution)
  log_cap1e6      log buckets, a_min 1e-6 (cap practically removed; ALSO coarser: 40 buckets span
                  6 decades instead of 2.7)
  log_cap1e6_m89  log buckets, a_min 1e-6, 89 buckets (same per-decade resolution as mvp_log)
  log_cap001      log buckets, a_min 0.001
  log_cap005      log buckets, a_min 0.005
Modes: normal (no outage) and outage tests rand10 / region from the start of the second test
segment (same site rule as posthoc_outage.py, seed 7). Groups: pre-registered 25.
Output: <out_dir>_posthoc/scale_ablation/<mode>/ and scale_ablation_summary.csv.
"""
import argparse
import copy
from pathlib import Path

import pandas as pd

from ccpilot import evaluate
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import load_config, load_work, offline_sites, outage_events, reduce_cfg, set_display
from posthoc_regrade import DEFS, group_rows

VARIANTS = [
    {"name": "mvp_log", "scale": "log", "m": 40, "a_min": 0.002},
    {"name": "unif_nocap", "scale": "quantile", "m": 40},
    {"name": "unif_cap002", "scale": "quantile", "m": 40, "floor_level": 0.002},
    {"name": "log_cap1e6", "scale": "log", "m": 40, "a_min": 1e-6},
    {"name": "log_cap1e6_m89", "scale": "log", "m": 89, "a_min": 1e-6},
    {"name": "log_cap001", "scale": "log", "m": 40, "a_min": 0.001},
    {"name": "log_cap005", "scale": "log", "m": 40, "a_min": 0.005},
]
REF = ["static", "qr_ogd", "mvp_global"]


def run_mode(base, pred, mode, root, radius, seed):
    cfg = reduce_cfg(copy.deepcopy(base), pred)
    ex = cfg["eval"]
    ex["multigroup"]["mvp_variants"] = VARIANTS + [v for v in ex["multigroup"]["mvp_variants"]
                                                   if v["name"] == "mvp_global"]
    ex["save_hits"] = True
    ex["plot_methods"] = ["static", "mvp_log", "unif_cap002", "log_cap1e6"]
    if mode == "normal":
        trans, truth, cams, n_bins = load_work(cfg)
    else:
        tz = base["timezone"]; work = Path(base["work_dir"])
        cams = pd.read_csv(work / "cameras.csv")
        sites = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams,
                              pd.read_parquet(work / "transitions.parquet"), base, radius, seed)
        tests = ex["splits"]["test"]
        start = tests[1]["range"][0]                      # start of the second test segment
        end = tests[-1]["range"][1]
        b_early_end = str((pd.Timestamp(start) + pd.Timedelta(days=2)).date())
        ex["splits"]["test"] = [t for t in tests if t["range"][1] <= start] + [
            {"name": "B_early", "range": [start, b_early_end]}, {"name": "B_late", "range": [b_early_end, end]}]
        t_start = date_to_unix(start, tz)
        trans, truth, n_bins, _ = outage_events(pd.read_parquet(work / "sightings.parquet"), base, sites[mode], t_start)
        ex["outage"] = {"cams": sites[mode], "t_start": t_start}
        print(f"[ablation] outage {mode}: {len(sites[mode])} sites from {start}")
    res, _, _ = evaluate.run(cfg, trans, truth, cams, n_bins, root / mode)
    return res


def summarize(root, modes, pred, min_n):
    rows = []
    for mode in modes:
        d = root / mode
        H = pd.read_parquet(d / "hits.parquet")
        S = pd.read_csv(d / "summary.csv")
        orc = S[(S["predictor"] == pred) & (S["method"] == "oracle(post-hoc)")].set_index("segment")["cost_mean_cam_s"]
        meths = [v["name"] for v in VARIANTS] + REF
        for seg in H["segment"].unique():
            for m in meths:
                col = f"hit|{pred}|{m}"
                gt = group_rows(H, col, DEFS["prereg_25"], seg, min_n)
                w = gt.loc[gt["coverage"].idxmin()]
                ms = H["segment"] == seg
                cost = H.loc[ms, f"cost|{pred}|{m}"].mean()
                rows.append({"mode": mode, "segment": seg, "method": m, "coverage": H.loc[ms, col].mean(),
                             "worst_group": f"{w['dim']}={w['group']}", "worst_cov": w["coverage"],
                             "n_sig_below_0.94": int((gt["ub95"] < 0.94).sum()),
                             "n_sig_below_0.95": int((gt["ub95"] < 0.95).sum()),
                             "cost_mean_cam_s": cost, "cost_over_oracle": cost / orc.get(seg, float("nan"))})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--modes", nargs="*", default=["normal", "rand10", "region"])
    ap.add_argument("--radius", type=float, default=800.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--combine", action="store_true", help="only summarise the modes already run")
    a = ap.parse_args()
    base = load_config(a.config)
    root = Path(base["out_dir"] + "_posthoc") / "scale_ablation"
    if not a.combine:
        for mode in a.modes:
            run_mode(base, a.predictor, mode, root, a.radius, a.seed)
    modes = [m for m in ["normal", "rand10", "region"] if (root / m / "hits.parquet").exists()]
    T = summarize(root, modes, a.predictor, base["eval"].get("min_group_n", 200))
    T.insert(0, "period", base["out_dir"].split("/")[-1])
    T.to_csv(root / "scale_ablation_summary.csv", index=False)
    set_display()
    print("\n================ POST-HOC SCALE / CAP ABLATION, EXPLORATORY (not pre-registered) ================")
    print(T.round(4).to_string(index=False))
    print(f"\n-> {root}")


if __name__ == "__main__":
    main()
