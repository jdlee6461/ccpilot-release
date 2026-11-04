"""Regrade the confirmation run under different group definitions / bars.

Background (deviation to be disclosed): the confirmation run judged C1 over the strata
list in the config, which is NOT the 25 groups defined in PREREGISTRATION.md:
    as run   : hgroup 5 + hopfirst 2 + hopkind 3 + zone 4 + speed 4 + entropy 4 + nn 4 = 26
               (no 'all' group; hopfirst=0 equals hopkind=0, hopfirst=1 = hopkind 1 or 2)
    prereg   : all 1 + hgroup 5 + hopkind 3 + speed 4 + zone 4 + entropy 4 + nn 4      = 25

    python posthoc_regrade.py --config configs/porto_cctv_confirm.yaml
    python posthoc_regrade.py --config configs/porto_cctv_confirm.yaml --hits results/porto_cctv_confirm_regrade/hits.parquet

Step 1 re-runs the pre-registered evaluation UNCHANGED (seed, methods, predictors; the
config file on disk is not edited) only to save per-hop outcomes. Step 2 regrades.
Outputs: <out_dir>_regrade/regrade_summary.csv, group_table_<method>.csv
"""
import argparse
import copy
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot import evaluate
from ccpilot.evaluate import _wilson_ub
from ccpilot.posthoc import load_config, load_work, set_display

DEFS = {
    "as_run_26": ["hgroup", "hopfirst", "hopkind", "zone", "speed_bin", "entropy_bin", "nn_bin"],
    "prereg_25": ["grp_all", "hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"],
}
BARS = [0.94, 0.95]


def group_rows(H, col, dims, seg, min_n):
    m = H["segment"].to_numpy() == seg
    hit = H[col].to_numpy()
    rows = []
    for d in dims:
        v = H[d].to_numpy()
        for g in np.unique(v[m]):
            mm = m & (v == g)
            n = int(mm.sum())
            if n < min_n:
                continue
            k = int(hit[mm].sum())
            rows.append({"dim": d, "group": int(g), "n": n, "coverage": k / n, "ub95": _wilson_ub(k, n)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--hits", default=None, help="reuse a saved hits.parquet instead of re-running")
    a = ap.parse_args()
    base = load_config(a.config)
    out = Path(base["out_dir"] + "_regrade"); out.mkdir(parents=True, exist_ok=True)
    if a.hits:
        H = pd.read_parquet(a.hits)
    else:
        cfg = copy.deepcopy(base)
        cfg["eval"]["save_hits"] = True
        trans, truth, cams, n_bins = load_work(cfg)
        evaluate.run(cfg, trans, truth, cams, n_bins, out)
        H = pd.read_parquet(out / "hits.parquet")
    min_n = base["eval"].get("min_group_n", 200)
    segs = [s["name"] for s in base["eval"]["splits"]["test"]]
    hit_cols = [c for c in H.columns if c.startswith("hit|")]
    rows = []
    for col in hit_cols:
        _, pred, meth = col.split("|")
        for dname, dims in DEFS.items():
            for seg in segs:
                gt = group_rows(H, col, dims, seg, min_n)
                w = gt.loc[gt["coverage"].idxmin()]
                r = {"predictor": pred, "method": meth, "definition": dname, "segment": seg,
                     "n_groups": len(gt), "coverage": H.loc[H["segment"] == seg, col].mean(),
                     "worst_group": f"{w['dim']}={w['group']}", "worst_n": int(w["n"]),
                     "worst_cov": w["coverage"], "worst_ub95": w["ub95"]}
                for b in BARS:
                    r[f"n_sig_below_{b:.2f}"] = int((gt["ub95"] < b).sum())
                rows.append(r)
                if meth in ("mvp_log", "qr_ogd", "static") and pred == "src_zone_hour_speed" and dname == "prereg_25":
                    gt.assign(segment=seg).to_csv(out / f"group_table_{meth}_{seg}.csv", index=False)
    R = pd.DataFrame(rows)
    R.to_csv(out / "regrade_summary.csv", index=False)
    set_display(400)
    P = R[R["predictor"] == "src_zone_hour_speed"]
    print("\n================ REGRADE of the confirmation run (primary predictor) ================")
    print(P[["method", "definition", "segment", "n_groups", "coverage", "worst_group", "worst_n", "worst_cov",
             "worst_ub95", "n_sig_below_0.94", "n_sig_below_0.95"]].round(4).to_string(index=False))
    print("\n[C1 verdict: no group with ub95 < 0.94 in both segments]")
    v = P.groupby(["method", "definition"])["n_sig_below_0.94"].max().unstack()
    print((v == 0).replace({True: "pass", False: "fail"}).to_string())
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
