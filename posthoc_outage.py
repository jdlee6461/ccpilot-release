"""POST-HOC stress test: camera outage (not pre-registered; report as post hoc).

    python posthoc_outage.py --config configs/porto_cctv_confirm.yaml
    python posthoc_outage.py --config configs/porto_cctv_confirm.yaml --scenarios none rand20 region --radius 800

From --start (default: start of the second test segment, 2014-06-21) a set of camera
sites goes offline for the rest of the test period:
  none    : no outage (sanity check; must reproduce the seed-0 results on segment A)
  randXX  : XX% of sites chosen at random (seeded)
  region  : every site within --radius metres of the busiest site (a localised loss,
            e.g. strike or jamming in one district)
Sightings at offline sites after the start are removed and hop transitions are REBUILT,
so a target that passes an offline site next appears at a later, farther camera.
The system knows which feeds are down (offline sites are never searched), but its
predictor and thresholds are NOT retrained -- online methods can only adapt through
feedback. Test segments: A (before), B_early (first 48 h of the outage), B_late.
"""
import argparse
import copy
from pathlib import Path

import pandas as pd

from ccpilot import evaluate
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import (add_cost_over_oracle, load_config, offline_sites, outage_events, reduce_cfg,
                             set_display)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--scenarios", nargs="*", default=["none", "rand10", "rand20", "rand30", "region"])
    ap.add_argument("--start", default="2014-06-21")
    ap.add_argument("--radius", type=float, default=800.0)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    base = load_config(a.config)
    tz = base["timezone"]
    work = Path(base["work_dir"])
    sight = pd.read_parquet(work / "sightings.parquet")
    cams = pd.read_csv(work / "cameras.csv")
    trans0 = pd.read_parquet(work / "transitions.parquet")
    t_start = date_to_unix(a.start, tz)
    tests = base["eval"]["splits"]["test"]
    end = tests[-1]["range"][1]
    b_early_end = str((pd.Timestamp(a.start) + pd.Timedelta(days=2)).date())
    new_tests = [t for t in tests if t["range"][1] <= a.start] + [
        {"name": "B_early", "range": [a.start, b_early_end]},
        {"name": "B_late", "range": [b_early_end, end]}]

    ids = cams["cam_id"].to_numpy()
    sites = offline_sites(a.scenarios, cams, trans0, base, a.radius, a.seed)

    root = Path(base["out_dir"] + "_posthoc") / "outage"
    allres, meta = [], []
    for sc in a.scenarios:
        off = sites[sc]
        print(f"\n########## outage scenario {sc}: {len(off)} of {len(ids)} sites offline from {a.start}")
        trans, truth, n_bins, n_drop = outage_events(sight, base, off, t_start)
        cfg = reduce_cfg(copy.deepcopy(base), a.predictor)
        cfg["eval"]["splits"]["test"] = new_tests
        cfg["eval"].setdefault("citytrac", {"targets": [0.95], "window_q": 0.98, "min_n": 30})
        cfg["eval"]["outage"] = {"cams": off, "t_start": t_start}
        res, _, _ = evaluate.run(cfg, trans, truth, cams, n_bins, root / sc)
        res.insert(0, "scenario", sc)
        allres.append(res)
        meta.append({"scenario": sc, "n_offline": len(off), "share_offline": len(off) / len(ids),
                     "sightings_removed": n_drop, "offline_sites": ",".join(map(str, off))})
    df = pd.concat(allres, ignore_index=True)
    keep = ["static", "mondrian_hour_hop_speed", "aci_g0005", "mvp_log", "mvp_global", "qr_groups", "qr_ogd",
            "oracle(post-hoc)", "target095", "fixed"]
    df = df[df["method"].isin(keep)].copy()
    add_cost_over_oracle(df, "scenario")
    root.mkdir(parents=True, exist_ok=True)
    df.to_csv(root / "outage_summary.csv", index=False)
    pd.DataFrame(meta).to_csv(root / "outage_scenarios.csv", index=False)
    set_display()
    print("\n================ POST-HOC CAMERA OUTAGE (not pre-registered) ================")
    print(pd.DataFrame(meta)[["scenario", "n_offline", "share_offline", "sightings_removed"]].to_string(index=False))
    cols = ["scenario", "predictor", "method", "segment", "coverage", "worst_group_cov", "worst_group",
            "n_groups_sig_below_bar", "cost_mean_cam_s", "cost_over_oracle", "roll_p05", "frac_below"]
    print(df[cols].round(3).to_string(index=False))
    print(f"\n-> {root}")


if __name__ == "__main__":
    main()
