"""POST-HOC outage suite across periods (not pre-registered; report as post hoc).

    python posthoc_outage_suite.py --config configs/porto_cctv.yaml --scenario region_fixed --methods full
    python posthoc_outage_suite.py --config configs/porto_cctv.yaml --scenario rand10 --site-seed 3 --methods reduced --amin
    python posthoc_outage_suite.py --config configs/porto_cctv.yaml --scenario none --methods full

One run = one period (config) x one scenario x one site seed. Outage start = start of the second
test segment in every period; segments A (earlier test segments), B_early (first 48 h), B_late.
  scenario    : none (no outage, same segments; gives the no-outage oracle), randXX (site seed),
                region_fixed (geographically fixed 20-site region, ccpilot.posthoc.fixed_region_sites,
                centre/radius from the confirmation training period, same sites in every period)
  --methods   : full    = every method of the config for the primary predictor
                reduced = static, aci_g0005, mvp_log, qr_groups/qr_ogd, oracle (+ spatula, citytrac)
  --amin      : add mvp_log variants a_min 0.001 and 0.005
  --no-aware  : skip the outage-aware predictor '<predictor>_oa' (it is added whenever sites are offline)
  --mvp-diag  : store per-query q and (V, N) snapshots (outage start, then daily)
Always saves per-hop hits, scores and tau_min at a_min 0.001 / 0.002 / 0.005.
Output: <out_dir>_posthoc/outage_suite/<scenario>_s<seed>/
"""
import argparse
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot import evaluate
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import fixed_region_sites, load_config, load_work, offline_sites, outage_events, reduce_cfg

REF_CONFIG = "configs/porto_cctv_confirm.yaml"
AMIN = [{"name": "mvp_log_a001", "scale": "log", "m": 40, "a_min": 0.001},
        {"name": "mvp_log_a005", "scale": "log", "m": 40, "a_min": 0.005}]


def sites_for(base, scenario, seed, radius=800.0):
    if scenario == "none":
        return []
    if scenario == "region_fixed":
        return fixed_region_sites(load_config(REF_CONFIG))[2]
    work = Path(base["work_dir"])
    return offline_sites(["none", "rand10", "rand20", "rand30", "region"], pd.read_csv(work / "cameras.csv"),
                         pd.read_parquet(work / "transitions.parquet"), base, radius, seed)[scenario]


def build_cfg(base, pred, methods, amin):
    cfg = copy.deepcopy(base)
    ex = cfg["eval"]
    if methods == "reduced":
        cfg = reduce_cfg(cfg, pred); ex = cfg["eval"]
        ex["mondrian"] = {}
        ex["multigroup"]["mvp_variants"] = [v for v in ex["multigroup"]["mvp_variants"] if v["name"] == "mvp_log"]
    else:
        ex["predictors"] = {pred: ex["predictors"][pred]}
        ex["multigroup"]["predictors"] = [pred]
        ex.setdefault("citytrac", {"targets": [0.95, 0.99], "window_q": 0.98, "min_n": 30})
    if amin:
        ex["multigroup"]["mvp_variants"] = ex["multigroup"]["mvp_variants"] + AMIN
    ex["plot_methods"] = ["static", "mvp_log", "qr_ogd"]
    ex["save_hits"] = True
    ex["save_scores"] = {"tau_min_levels": [0.001, 0.002, 0.005]}
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--site-seed", type=int, default=7)
    ap.add_argument("--methods", choices=["full", "reduced"], default="reduced")
    ap.add_argument("--amin", action="store_true")
    ap.add_argument("--no-aware", action="store_true")
    ap.add_argument("--mvp-diag", action="store_true")
    a = ap.parse_args()
    base = load_config(a.config)
    tz = base["timezone"]
    tests = base["eval"]["splits"]["test"]
    start, end = tests[1]["range"][0], tests[-1]["range"][1]
    t_start = date_to_unix(start, tz)
    b_early_end = str((pd.Timestamp(start) + pd.Timedelta(days=2)).date())
    off = sites_for(base, a.scenario, a.site_seed)
    cfg = build_cfg(base, a.predictor, a.methods, a.amin)
    ex = cfg["eval"]
    ex["splits"]["test"] = [t for t in tests if t["range"][1] <= start] + [
        {"name": "B_early", "range": [start, b_early_end]}, {"name": "B_late", "range": [b_early_end, end]}]
    if off:
        trans, truth, n_bins, n_drop = outage_events(pd.read_parquet(Path(base["work_dir"]) / "sightings.parquet"),
                                                     base, off, t_start)
        ex["outage"] = {"cams": off, "t_start": t_start}
        if not a.no_aware:
            ex["outage"]["aware_predictors"] = [a.predictor]
            ex["multigroup"]["predictors"] = [a.predictor, a.predictor + "_oa"]
    else:
        trans, truth, _, n_bins = load_work(base); n_drop = 0
    if a.mvp_diag:
        t_end = date_to_unix(end, tz)
        ex["mvp_diag"] = {"snapshot_times": [t_start - 86400.0, t_start] +
                          list(np.arange(t_start + 86400.0, t_end, 86400.0))}
    out = Path(base["out_dir"] + "_posthoc") / "outage_suite" / f"{a.scenario}_s{a.site_seed}"
    print(f"[suite] {base['out_dir']} {a.scenario} seed {a.site_seed}: {len(off)} sites offline from {start}, "
          f"{n_drop} sightings removed, methods={a.methods}, amin={a.amin}")
    res, _, _ = evaluate.run(cfg, trans, truth, pd.read_csv(Path(base["work_dir"]) / "cameras.csv"), n_bins, out)
    pd.DataFrame([{"config": a.config, "scenario": a.scenario, "site_seed": a.site_seed, "start": start,
                   "n_offline": len(off), "sightings_removed": n_drop, "methods": a.methods, "amin": a.amin,
                   "offline_sites": ",".join(map(str, off))}]).to_csv(out / "run_meta.csv", index=False)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
