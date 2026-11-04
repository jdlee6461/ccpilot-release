"""POST-HOC per-hop analysis of the outage-aware runs (not pre-registered; report as post hoc).

    python posthoc_outage_ceiling.py --config configs/porto_cctv_confirm.yaml

Needs posthoc_outage_aware.py --save-hits runs and posthoc_exit_split.py outputs.
(a) coverage by outage-side hop category: unchanged / rerouted with 1 skipped offline site /
    rerouted with >= 2 skipped offline sites / new / reacquisition created by an exit conversion,
    for the base predictor and the outage-aware '_oa' predictor (one-step composition).
(b) ceiling of mvp_log: tau_min = tau at q = 1 = the 0.2 % quantile of the calibration scores.
    No mvp_log threshold is lower, so a hop with score sigma < tau_min is missed whatever MVP does.
    ceiling = 1 - Pr[sigma < tau_min], overall and per pre-registered group, per segment.
Output: <out_dir>_posthoc/outage_aware/hop_analysis/.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.posthoc import load_config, set_display
from posthoc_exit_split import KEY
from posthoc_regrade import DEFS

METHODS = ["static", "qr_ogd", "mvp_global", "mvp_log"]
SEGS = ["B_early", "B_late"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    a = ap.parse_args()
    base = load_config(a.config)
    ph = Path(base["out_dir"] + "_posthoc")
    root = ph / "outage_aware"; out = root / "hop_analysis"; out.mkdir(parents=True, exist_ok=True)
    preds = {"base": a.predictor, "oa": a.predictor + "_oa"}
    cat_rows, ceil_rows, grp_rows = [], [], []
    for d in sorted(root.glob("start_*/*")):
        if not (d / "hits.parquet").exists():
            continue
        start, sc = d.parent.name.replace("start_", ""), d.name
        H = pd.read_parquet(d / "hits.parquet")
        es = ph / "exit_split"
        mo = pd.read_parquet(es / f"outage_hops_{start}_{sc}.parquet")
        mb = pd.read_parquet(es / f"baseline_hops_{start}_{sc}.parquet")
        mo = mo.merge(mb[KEY + ["n_skipped_off"]], on=KEY, how="left")
        cat = np.where(mo["reacq_by_outage"], "reacq_by_outage", mo["category"])
        cat = np.where(cat == "rerouted", np.where(mo["n_skipped_off"] >= 2, "rerouted_skip2plus", "rerouted_skip1"), cat)
        mo["cat"] = cat
        J = H.merge(mo[["tr_id", "cat", "struct"]], on="tr_id", how="left")
        J["cat"] = J["cat"].fillna("pre_outage")
        tmin = float(H[f"taumin0.002|{a.predictor}"].iloc[0])
        for seg in SEGS:
            Js = J[J["segment"] == seg]
            for c, g in Js.groupby("cat"):
                r = {"start": start, "scenario": sc, "segment": seg, "category": c, "n": len(g),
                     "share": len(g) / len(Js), "structural_base": g["struct"].mean()}
                for pk, pn in preds.items():
                    for m in METHODS:
                        r[f"{pk}:{m}"] = g[f"hit|{pn}|{m}"].mean()
                    r[f"{pk}:ceiling"] = (g[f"score|{pn}"] >= tmin).mean()
                cat_rows.append(r)
            # (b) ceiling overall and per pre-registered group
            for pk, pn in preds.items():
                above = (Js[f"score|{pn}"] >= tmin).to_numpy()
                hit = Js[f"hit|{pn}|mvp_log"].to_numpy()
                ceil_rows.append({"start": start, "scenario": sc, "segment": seg, "predictor": pk, "tau_min": tmin,
                                  "n": len(Js), "ceiling": above.mean(), "mvp_log": hit.mean(),
                                  "gap_to_ceiling": above.mean() - hit.mean(),
                                  "mvp_log_miss_below_tau_min": ((~above) & (hit == 0)).sum() / max(1, (hit == 0).sum())})
                for dim in DEFS["prereg_25"]:
                    v = Js[dim].to_numpy()
                    for gv in np.unique(v):
                        mm = v == gv
                        if mm.sum() < 200:
                            continue
                        grp_rows.append({"start": start, "scenario": sc, "segment": seg, "predictor": pk,
                                         "group": "all" if dim == "grp_all" else f"{dim}={int(gv)}", "n": int(mm.sum()),
                                         "ceiling": above[mm].mean(), "mvp_log": hit[mm].mean(),
                                         "pr_below_tau_min": 1 - above[mm].mean()})
    C = pd.DataFrame(cat_rows); E = pd.DataFrame(ceil_rows); G = pd.DataFrame(grp_rows)
    C.to_csv(out / "coverage_by_hop_category.csv", index=False)
    E.to_csv(out / "ceiling_overall.csv", index=False)
    G.to_csv(out / "ceiling_by_group.csv", index=False)
    (out / "README.txt").write_text(
        "POST-HOC. ceiling = share of hops with score >= tau_min (tau at q = 1 of mvp_log = 0.2% quantile of\n"
        "calibration scores); no mvp_log threshold can find a hop below it. Categories from exit_split.\n"
        "rerouted_skip1 / _skip2plus: offline sites passed consecutively in the no-outage path.\n"
        "The '_oa' predictor composes ONE step through an offline site.\n")
    set_display()
    print("\n================ POST-HOC OUTAGE HOP ANALYSIS (not pre-registered) ================")
    print(C.round(4).to_string(index=False))
    print(E.round(4).to_string(index=False))
    gw = G[G["predictor"] == "base"].sort_values("ceiling").groupby(["start", "scenario", "segment"]).head(3)
    print("\n[lowest-ceiling groups, base predictor]")
    print(gw.round(4).to_string(index=False))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
