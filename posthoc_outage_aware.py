"""POST-HOC outage-aware predictor under camera outage (not pre-registered; report as post hoc).

    python posthoc_outage_aware.py --config configs/porto_cctv_confirm.yaml
    python posthoc_outage_aware.py --config configs/porto_cctv_confirm.yaml --starts 2014-06-12 --scenarios rand10
    python posthoc_outage_aware.py --config configs/porto_cctv_confirm.yaml --combine   # merge per-run summaries
    python posthoc_outage_aware.py --config configs/porto_cctv_confirm.yaml --seed 1 --out-sub seeds/seed_1 \
        --scenarios rand10 rand20 rand30                      # another random draw of offline sites
    python posthoc_outage_aware.py --config configs/porto_cctv_confirm.yaml --aggregate-seeds

Same outage scenarios, sites (seed 7) and segments as posthoc_outage.py. Each run evaluates the
primary predictor AND an outage-aware copy '<predictor>_oa' (ccpilot.predictors.OutageAwareModel):
for an offline next camera `off`, p(c'|src) + p(off|src) * p(c'|off), delays composed by convolution.
This is a SEPARATE method added after the confirmation run; the base-predictor rows reproduce
posthoc_outage.py. Limitation: one-step composition only (a second offline site after `off`
is not propagated); see exit_split/hop_loss_split.csv (rerouted_skip2plus) for how often that occurs.
Output: <out_dir>_posthoc/outage_aware/.
"""
import argparse
import copy
from pathlib import Path

import pandas as pd

from ccpilot import evaluate
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import (add_cost_over_oracle, load_config, offline_sites, outage_events, reduce_cfg,
                             set_display)

KEEP = ["static", "mondrian_hour_hop_speed", "aci_g0005", "mvp_log", "mvp_global", "qr_groups", "qr_ogd",
        "oracle(post-hoc)", "target095", "fixed"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--scenarios", nargs="*", default=["rand10", "rand20", "rand30", "region"])
    ap.add_argument("--starts", nargs="*", default=["2014-06-21"])
    ap.add_argument("--radius", type=float, default=800.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--combine", action="store_true", help="only merge summary_*.csv of earlier runs")
    ap.add_argument("--save-hits", action="store_true", help="save per-hop hits, scores and tau_min")
    ap.add_argument("--out-sub", default="", help="sub-folder, e.g. seeds/seed_1 for repeated site draws")
    ap.add_argument("--aggregate-seeds", action="store_true",
                    help="summarise randXX over site seeds (seed 7 = top folder, others = seeds/seed_k)")
    a = ap.parse_args()
    base = load_config(a.config)
    root = Path(base["out_dir"] + "_posthoc") / "outage_aware"
    if a.aggregate_seeds:
        return aggregate_seeds(root, a.predictor)
    if a.out_sub:
        root = root / a.out_sub
    if a.combine:
        return report(pd.concat([pd.read_csv(f) for f in sorted(root.glob("summary_*.csv"))], ignore_index=True),
                      root, a.predictor)
    tz = base["timezone"]
    work = Path(base["work_dir"])
    sight = pd.read_parquet(work / "sightings.parquet")
    cams = pd.read_csv(work / "cameras.csv")
    sites = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams,
                          pd.read_parquet(work / "transitions.parquet"), base, a.radius, a.seed)
    tests = base["eval"]["splits"]["test"]
    end = tests[-1]["range"][1]
    pa = a.predictor + "_oa"
    allres = []
    for start in a.starts:
        t_start = date_to_unix(start, tz)
        b_early_end = str((pd.Timestamp(start) + pd.Timedelta(days=2)).date())
        new_tests = [t for t in tests if t["range"][1] <= start] + [
            {"name": "B_early", "range": [start, b_early_end]},
            {"name": "B_late", "range": [b_early_end, end]}]
        if not any(t["range"][1] <= start for t in tests):     # outage inside the first segment
            new_tests = [{"name": "A_pre", "range": [tests[0]["range"][0], start]}] + new_tests
        for sc in a.scenarios:
            off = sites[sc]
            trans, truth, n_bins, _ = outage_events(sight, base, off, t_start)
            cfg = reduce_cfg(copy.deepcopy(base), a.predictor)
            ex = cfg["eval"]
            ex["splits"]["test"] = new_tests
            ex["outage"] = {"cams": off, "t_start": t_start, "aware_predictors": [a.predictor]}
            ex["multigroup"]["predictors"] = [a.predictor, pa]
            ex["plot_methods"] = ["static", "mvp_log", "qr_ogd"]
            if a.save_hits:
                ex["save_hits"] = True
                ex["save_scores"] = {"tau_min_levels": [0.002]}
            print(f"\n########## start {start}, scenario {sc}: {len(off)} sites offline")
            res, _, _ = evaluate.run(cfg, trans, truth, cams, n_bins, root / f"start_{start.replace('-', '')}" / sc)
            res.insert(0, "scenario", sc); res.insert(0, "start", start); res.insert(0, "site_seed", a.seed)
            res.insert(0, "offline_sites", ",".join(map(str, off)))
            allres.append(res)
    root.mkdir(parents=True, exist_ok=True)
    tag = "_".join(s.replace("-", "") for s in a.starts) + "_" + "_".join(a.scenarios)
    pd.concat(allres, ignore_index=True).to_csv(root / f"summary_{tag}.csv", index=False)
    report(pd.concat([pd.read_csv(f) for f in sorted(root.glob("summary_*.csv"))], ignore_index=True),
           root, a.predictor)


def aggregate_seeds(root, pred):
    files = sorted(root.glob("summary_20140621_rand*.csv")) + sorted(root.glob("seeds/seed_*/summary_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df[df["method"].isin(["static", "qr_ogd", "mvp_global", "mvp_log", "oracle(post-hoc)"]) &
            df["scenario"].str.startswith("rand")]
    df = df.drop_duplicates(["site_seed", "start", "scenario", "predictor", "method", "segment"])
    df.to_csv(root / "seeds_all.csv", index=False)
    val = ["coverage", "worst_group_cov", "n_groups_sig_below_bar", "cost_mean_cam_s"]
    agg = df.groupby(["scenario", "segment", "predictor", "method"])[val].agg(["mean", "std", "min", "max"])
    agg.insert(0, ("n_seeds", ""), df.groupby(["scenario", "segment", "predictor", "method"]).size())
    agg.to_csv(root / "seeds_summary.csv")
    set_display()
    print("\n================ POST-HOC RANDOM OUTAGE, REPEATED SITE DRAWS (not pre-registered) ================")
    print(agg.round(4).to_string())
    print(f"\n-> {root / 'seeds_summary.csv'}")


def report(df, root, pred):
    df = df[df["method"].isin(KEEP)].copy()
    df["key"] = df["start"] + "|" + df["scenario"] + "|" + df["predictor"]
    add_cost_over_oracle(df, "key")      # each predictor against its own oracle
    base_orc = df[(df["method"] == "oracle(post-hoc)") & (df["predictor"] == pred)].set_index(
        ["start", "scenario", "segment"])["cost_mean_cam_s"]
    df["cost_over_base_oracle"] = df["cost_mean_cam_s"].to_numpy() / base_orc.reindex(
        pd.MultiIndex.from_frame(df[["start", "scenario", "segment"]])).to_numpy()
    df = df.drop(columns="key")
    df.to_csv(root / "outage_aware_summary.csv", index=False)
    (root / "README.txt").write_text(
        "POST-HOC (not pre-registered). '<predictor>_oa' = outage-aware predictor, a separate method added\n"
        "after the confirmation run: p(c'|src) + p(off|src) p(c'|off), delay by convolution, ONE STEP ONLY\n"
        "(a second offline site after `off` is not propagated). Thresholds/predictor are not refitted.\n"
        "cost_over_oracle: against the same predictor's post-hoc oracle; cost_over_base_oracle: against the\n"
        "base predictor's oracle (common yardstick).\n")
    set_display()
    print("\n================ POST-HOC OUTAGE-AWARE PREDICTOR (not pre-registered) ================")
    cols = ["start", "scenario", "predictor", "method", "segment", "coverage", "worst_group_cov", "worst_group",
            "n_groups_sig_below_bar", "cost_mean_cam_s", "cost_over_base_oracle", "structural_miss"]
    show = df[df["method"].isin(["static", "qr_ogd", "mvp_global", "mvp_log", "oracle(post-hoc)"])]
    print(show[cols].round(4).to_string(index=False))
    print(f"\n-> {root}")


if __name__ == "__main__":
    main()
