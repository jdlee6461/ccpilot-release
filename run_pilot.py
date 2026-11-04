"""Pilot runner.

    python run_pilot.py --config configs/synthetic.yaml --stage all
    stages: data | events | eval | all
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ccpilot import synthetic, porto, cameras as camlib, events, evaluate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stage", default="all", choices=["data", "events", "eval", "all"])
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    work = Path(cfg["work_dir"]); work.mkdir(parents=True, exist_ok=True)
    f_traj, f_cam = work / "trajectories.parquet", work / "cameras.csv"
    f_sig, f_tr, f_truth, f_meta = (work / "sightings.parquet", work / "transitions.parquet",
                                    work / "truth.parquet", work / "meta.json")
    t0 = time.time()

    if args.stage in ("data", "all"):
        if cfg["dataset"] == "synthetic":
            traj, cams = synthetic.generate(cfg)
        elif cfg["dataset"] == "porto":
            reuse = cfg["porto"].get("reuse_trajectories")
            if reuse and Path(reuse).exists():
                print(f"[data] reusing trajectories from {reuse}")
                traj = pd.read_parquet(reuse)
            else:
                traj = porto.load(cfg)
            cc = cfg["cameras"]
            if cc.get("geojson"):
                cams = camlib.load_cctv_geojson(cc["geojson"], cfg["porto"]["proj_center"],
                                                cc.get("merge_radius_m", 50.0), cc.get("exclude_tunnel", True))
                print(f"[data] real CCTV: {int(cams.n_cams.sum())} cameras merged into {len(cams)} sites "
                      f"(merge radius {cc.get('merge_radius_m', 50.0)} m)")
            elif cc.get("csv"):
                cams = pd.read_csv(cc["csv"])
            else:
                cams = camlib.place_by_density(traj, cc["n_cameras"], cc["min_spacing_m"],
                                               cc.get("cell_m", 50.0), region_xy=cc.get("region_xy"))
        else:
            raise ValueError(cfg["dataset"])
        traj.to_parquet(f_traj); cams.to_csv(f_cam, index=False)
        print(f"[data] trips={traj.trip_id.nunique()} points={len(traj)} cameras={len(cams)} "
              f"({time.time()-t0:.0f}s)")

    if args.stage in ("events", "all"):
        traj = pd.read_parquet(f_traj); cams = pd.read_csv(f_cam)
        ev = cfg["events"]
        sig = events.extract_sightings(traj, cams, ev["camera_radius_m"], ev["interp_step_s"],
                                       ev.get("max_overlap", 4))
        trans, truth, n_bins = events.build_transitions(sig, cfg)
        sig.to_parquet(f_sig); trans.to_parquet(f_tr); truth.to_parquet(f_truth)
        json.dump({"n_bins": n_bins}, open(f_meta, "w"))
        print(f"[events] sightings={len(sig)} transitions={len(trans)} "
              f"exit_rate={trans.is_exit.mean():.3f} mean_hops_per_trip={len(trans)/max(1,trans.trip_id.nunique()):.2f} "
              f"({time.time()-t0:.0f}s)")

    if args.stage in ("eval", "all"):
        trans = pd.read_parquet(f_tr); truth = pd.read_parquet(f_truth); cams = pd.read_csv(f_cam)
        n_bins = json.load(open(f_meta))["n_bins"]
        res, worst, conf = evaluate.run(cfg, trans, truth, cams, n_bins, cfg["out_dir"])
        pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
        cols = ["predictor", "method", "segment", "coverage", "worst_group_cov", "worst_group",
                "worst_group_ub95", "n_groups_sig_below_bar", "cost_mean_cam_s", "cost_median_cam_s",
                "roll_p05", "frac_below"]
        print(res[cols].round(3).to_string(index=False))
        print("\n[worst-group coverage] (min over groups with n >= min_group_n)")
        wp = worst.pivot_table(index=["predictor", "method"], columns=["segment", "dim"],
                               values="worst_coverage")
        print(wp.round(3).to_string())
        mp = cfg["eval"].get("confound_predictor", "src_zone")
        c = conf[(conf["predictor"] == mp) & (conf["method"] == "static")]
        if len(c):
            print(f"\n[confound] predictor={mp}, method=static  "
                  "(hopkind 0=later, 1=first hop of trip, 2=first hop after resume; speed_bin 0=slowest)")
            for seg, g in c.groupby("segment"):
                print(f"-- {seg}: share of hops")
                print(g.pivot_table(index="hopkind", columns="speed_bin", values="share").round(3).to_string())
                print(f"-- {seg}: coverage")
                print(g.pivot_table(index="hopkind", columns="speed_bin", values="coverage").round(3).to_string())
        print(f"[eval] done ({time.time()-t0:.0f}s) -> {cfg['out_dir']}")


if __name__ == "__main__":
    main()
