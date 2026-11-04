"""POST-HOC diagnosis of groups below the bar under a region outage (not pre-registered; report as post hoc).

    python posthoc_region_diag.py

For mvp_log (base and outage-aware predictor) in segment B_late, every pre-registered group whose
95 % Wilson upper bound is below 0.94 is decomposed:
  cov_none        : coverage of the same group, same segment, in the no-outage run (already weak?)
  share_rerouted  : share of the group's hops whose next camera was offline (exit_split classification)
  cov_unchanged / cov_rerouted : coverage within those hop categories
  miss_rerouted   : share of the group's misses that are rerouted hops
  miss_below_tmin : share of the group's misses with score < tau_min (the mvp_log ceiling)
Runs: fixed 20-site region in all three periods (outage_suite/region_fixed_s7 vs none_s7) and, for
reference, the old 6-site confirmation region (outage_aware/start_20140621/region vs outage_suite none_s7).
Output: <confirm out_dir>_posthoc/region_diag/.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.evaluate import _wilson_ub
from ccpilot.geo import date_to_unix
from ccpilot.posthoc import fixed_region_sites, load_config, offline_sites, outage_events, set_display
from posthoc_exit_split import classify
from posthoc_regrade import DEFS

PRED = "src_zone_hour_speed"
CONFIGS = ["configs/porto_cctv.yaml", "configs/porto_cctv_replication.yaml", "configs/porto_cctv_confirm.yaml"]


def diagnose(label, cfg, H, Hn, off, t_start):
    work = Path(cfg["work_dir"])
    base = pd.read_parquet(work / "transitions.parquet")
    out, _, _, _ = outage_events(pd.read_parquet(work / "sightings.parquet"), cfg, off, t_start)
    t_end = date_to_unix(cfg["eval"]["splits"]["test"][-1]["range"][1], cfg["timezone"])
    _, mo = classify(base, out, off, t_start, t_end)
    cat = mo.set_index("tr_id")["category"]
    H = H[H["segment"] == "B_late"].copy(); Hn = Hn[Hn["segment"] == "B_late"]
    H["cat"] = cat.reindex(H["tr_id"]).fillna("pre").to_numpy()
    rows = []
    for pk, pn in [("base", PRED), ("oa", PRED + "_oa")]:
        hit = H[f"hit|{pn}|mvp_log"].to_numpy().astype(bool)
        below = (H[f"score|{pn}"] < H[f"taumin0.002|{pn}"].iloc[0]).to_numpy()
        hn = Hn[f"hit|{PRED}|mvp_log"].to_numpy().astype(bool)
        for dim in DEFS["prereg_25"]:
            v = H[dim].to_numpy(); vn = Hn[dim].to_numpy()
            for g in np.unique(v):
                m = v == g; n = int(m.sum())
                if n < 200:
                    continue
                k = int(hit[m].sum()); ub = _wilson_ub(k, n)
                if ub >= 0.94:
                    continue
                mn = vn == g
                miss = m & ~hit
                rr = m & (H["cat"] == "rerouted").to_numpy(); uu = m & (H["cat"] == "unchanged").to_numpy()
                rows.append({"run": label, "predictor": pk, "group": "all" if dim == "grp_all" else f"{dim}={int(g)}",
                             "n": n, "coverage": k / n, "ub95": ub,
                             "cov_none": hn[mn].mean() if mn.any() else np.nan,
                             "ub95_none": _wilson_ub(int(hn[mn].sum()), int(mn.sum())) if mn.any() else np.nan,
                             "ceiling": 1 - below[m].mean(), "share_rerouted": rr.sum() / n,
                             "cov_unchanged": hit[uu].mean() if uu.any() else np.nan,
                             "cov_rerouted": hit[rr].mean() if rr.any() else np.nan,
                             "miss_rerouted": (miss & rr).sum() / max(1, miss.sum()),
                             "miss_below_tmin": (miss & below).sum() / max(1, miss.sum())})
    return rows


def main():
    rows = []
    ref = load_config("configs/porto_cctv_confirm.yaml")
    fixed = fixed_region_sites(ref)[2]
    for c in CONFIGS:
        cfg = load_config(c)
        root = Path(cfg["out_dir"] + "_posthoc") / "outage_suite"
        t_start = date_to_unix(cfg["eval"]["splits"]["test"][1]["range"][0], cfg["timezone"])
        Hn = pd.read_parquet(root / "none_s7" / "hits.parquet")
        H = pd.read_parquet(root / "region_fixed_s7" / "hits.parquet")
        rows += diagnose(f"{cfg['out_dir'].split('/')[-1]}:region_fixed20", cfg, H, Hn, fixed, t_start)
    # old 6-site confirmation region (radius 800 m around the busiest site)
    cams = pd.read_csv(Path(ref["work_dir"]) / "cameras.csv")
    old = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams,
                        pd.read_parquet(Path(ref["work_dir"]) / "transitions.parquet"), ref)["region"]
    Hn = pd.read_parquet(Path(ref["out_dir"] + "_posthoc") / "outage_suite" / "none_s7" / "hits.parquet")
    H = pd.read_parquet(Path(ref["out_dir"] + "_posthoc") / "outage_aware" / "start_20140621" / "region" / "hits.parquet")
    rows += diagnose("porto_cctv_confirm:region_old6", ref, H, Hn, old,
                     date_to_unix("2014-06-21", ref["timezone"]))
    R = pd.DataFrame(rows)
    out = Path(ref["out_dir"] + "_posthoc") / "region_diag"; out.mkdir(parents=True, exist_ok=True)
    R.to_csv(out / "region_groups_below_bar.csv", index=False)
    set_display(); print(R.round(4).to_string(index=False)); print(f"-> {out}")


if __name__ == "__main__":
    main()
