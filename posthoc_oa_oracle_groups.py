"""POST-HOC: why does outage-aware mvp_log cost about twice the post-hoc oracle after an outage?
(not pre-registered; report as post hoc)

    python posthoc_oa_oracle_groups.py

Confirmation period, rand10 (site seed 7) from 2014-06-21, outage-aware predictor, segment B_late.
Hypothesis: mvp_log searches wider than the single global oracle threshold in order to keep the
spatial groups where rerouted hops concentrate.

Per-hop mvp_log hits/costs come from the saved run (outage_suite/rand10_s7). The oracle's per-hop
COST is not saved (it needs each hop's probability matrix), so the predictor alone is refitted exactly
as in evaluate.run (no MVP, no evaluation re-run) and three checks must pass: refitted scores equal the
saved scores, the oracle row equals summary.csv, and mvp_log costs recomputed from the saved q equal
the saved costs.
Outputs (results/porto_cctv_confirm_posthoc/review/):
  oa_rand10_Blate_mvp_vs_oracle_by_group.csv     : 25 pre-registered groups
  oa_rand10_Blate_mvp_vs_oracle_by_category.csv  : additive split by hop category (exit_split), incl.
                                                   each category's share of the total extra cost
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.calibration import conformal_tau
from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask
from ccpilot.geo import date_to_unix
from ccpilot.multigroup import MVP
from ccpilot.posthoc import load_config, offline_sites, outage_events, set_display
from ccpilot.predictors import OutageAwareModel, _truth_by_tr, candidate_sets
from posthoc_exit_split import KEY
from posthoc_regrade import DEFS

PRED = "src_zone_hour_speed"
PA = PRED + "_oa"


def main():
    cfg = load_config("configs/porto_cctv_confirm.yaml")
    ev, ex, tz = cfg["events"], cfg["eval"], cfg["timezone"]
    delta = ev["bin_s"]; alpha = 1 - ex["target_recall"]
    work = Path(cfg["work_dir"]); ph = Path(cfg["out_dir"] + "_posthoc")
    run = ph / "outage_suite" / "rand10_s7"
    H = pd.read_parquet(run / "hits.parquet"); Q = pd.read_parquet(run / "mvp_q.parquet")
    S = pd.read_csv(run / "summary.csv")
    t_start = date_to_unix("2014-06-21", tz)
    cams = pd.read_csv(work / "cameras.csv")
    off = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams,
                        pd.read_parquet(work / "transitions.parquet"), cfg)["rand10"]
    trans, truth, n_bins, _ = outage_events(pd.read_parquet(work / "sightings.parquet"), cfg, off, t_start)

    # --- preprocessing exactly as evaluate.run
    t = trans["t_exit"].to_numpy(); sp = ex["splits"]
    m_train = _period_mask(t, sp["train"], tz); m_cal = _period_mask(t, sp["cal"], tz)
    m_test = _period_mask(t, [sp["test"][0]["range"][0], sp["test"][-1]["range"][1]], tz)
    trans = _add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    trans = _add_spatial(trans, m_train, cams, ex.get("n_spatial_bins", 4))
    ok = ~trans["is_exit"].to_numpy()
    tr_train = trans[m_train]
    tr_cal = trans[m_cal & ok].sort_values("t_exit").reset_index(drop=True)
    tr_test = trans[m_test & ok].sort_values("t_exit").reset_index(drop=True)
    tm = _truth_by_tr(truth)
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    vm = OutageAwareModel(ex["predictors"][PRED], cand, n_bins, **ex["model"]).fit(tr_train, tm)
    vm.fit_next(tr_train, trans, delta)
    s_cal, _, _ = vm.score(tr_cal, tm)
    vm.set_offline(off)
    s_test, kid, _ = vm.score(tr_test, tm, tr_test["t_exit"].to_numpy() >= t_start)

    # --- align with the saved run by tr_id; check 1: scores
    J = tr_test[["tr_id"]].assign(s=s_test, kid=kid).merge(
        H[["tr_id", "segment", f"score|{PA}", f"hit|{PA}|mvp_log", f"cost|{PA}|mvp_log"] + DEFS["prereg_25"]],
        on="tr_id", how="inner", validate="one_to_one")
    J = J.merge(Q[["tr_id", f"q|{PA}|mvp_log"]], on="tr_id", validate="one_to_one")
    assert len(J) == len(H) == len(tr_test)
    d_score = np.abs(J["s"] - J[f"score|{PA}"]).max()
    # check 3: mvp_log cost from the saved q
    mvp = MVP(s_cal, 1, alpha, m=40, scale="log", a_min=0.002)
    tau_mvp = np.array([mvp.q_to_tau(q) for q in J[f"q|{PA}|mvp_log"].to_numpy()])
    c_mvp_re = vm.cost(J["kid"].to_numpy(), tau_mvp, delta)
    d_cost = np.abs(c_mvp_re - J[f"cost|{PA}|mvp_log"].to_numpy()).max()
    # oracle on B_late (check 2)
    B = J[J["segment"] == "B_late"].copy()
    tau_o = conformal_tau(B["s"].to_numpy(), alpha)
    B["hit_oracle"] = B["s"].to_numpy() >= tau_o
    B["cost_oracle"] = vm.cost(B["kid"].to_numpy(), tau_o, delta)
    B["tau_mvp"] = tau_mvp[(J["segment"] == "B_late").to_numpy()]
    so = S[(S["predictor"] == PA) & (S["method"] == "oracle(post-hoc)") & (S["segment"] == "B_late")].iloc[0]
    d_orc = (abs(B["hit_oracle"].mean() - so["coverage"]), abs(B["cost_oracle"].mean() - so["cost_mean_cam_s"]))
    print(f"[check] max|score diff| {d_score:.3g}; max|mvp_log cost diff| {d_cost:.3g}; "
          f"oracle B_late coverage/cost diff {d_orc[0]:.3g} / {d_orc[1]:.3g}")
    assert d_score == 0 and d_cost < 1e-3 and d_orc[0] < 1e-12 and d_orc[1] < 1e-6 * so["cost_mean_cam_s"]

    # hop categories (exit_split, same outage transitions)
    es = ph / "exit_split"
    mo = pd.read_parquet(es / "outage_hops_20140621_rand10.parquet")
    mb = pd.read_parquet(es / "baseline_hops_20140621_rand10.parquet")
    mo = mo.merge(mb[KEY + ["n_skipped_off"]], on=KEY, how="left")
    cat = np.where(mo["reacq_by_outage"], "reacq_by_outage", mo["category"])
    cat = np.where(cat == "rerouted", np.where(mo["n_skipped_off"] >= 2, "rerouted_skip2plus", "rerouted_skip1"), cat)
    B = B.merge(pd.DataFrame({"tr_id": mo["tr_id"], "cat": cat}), on="tr_id", how="left")
    B["cat"] = B["cat"].fillna("pre_outage_start")
    B["rerouted"] = B["cat"].str.startswith("rerouted")
    hm, cm = B[f"hit|{PA}|mvp_log"].astype(bool), B[f"cost|{PA}|mvp_log"]
    B["extra"] = cm - B["cost_oracle"]
    total_extra = B["extra"].sum()
    B["wider"] = B["tau_mvp"] < tau_o          # mvp_log threshold below the oracle's -> searches more

    def row(g):
        return {"n": len(g), "share_rerouted": g["rerouted"].mean(),
                "mvp_log_coverage": g[f"hit|{PA}|mvp_log"].mean(), "oracle_coverage": g["hit_oracle"].mean(),
                "mvp_log_cost": g[f"cost|{PA}|mvp_log"].mean(), "oracle_cost": g["cost_oracle"].mean(),
                "cost_ratio_mvp_over_oracle": g[f"cost|{PA}|mvp_log"].mean() / g["cost_oracle"].mean(),
                "share_hops_mvp_wider": g["wider"].mean(),
                "extra_cost_per_hop": g["extra"].mean()}

    grp = []
    for dim in DEFS["prereg_25"]:
        for v, g in B.groupby(dim):
            grp.append({"group": "all" if dim == "grp_all" else f"{dim}={int(v)}", **row(g)})
    G = pd.DataFrame(grp)
    corr = G[G["group"] != "all"][["share_rerouted", "cost_ratio_mvp_over_oracle", "extra_cost_per_hop"]].corr()
    cats = []
    for c, g in B.groupby("cat"):
        cats.append({"category": c, "share_of_hops": len(g) / len(B), **row(g),
                     "share_of_total_extra_cost": g["extra"].sum() / total_extra})
    C = pd.DataFrame(cats).sort_values("share_of_hops", ascending=False)
    out = ph / "review"; out.mkdir(parents=True, exist_ok=True)
    G.to_csv(out / "oa_rand10_Blate_mvp_vs_oracle_by_group.csv", index=False)
    C.to_csv(out / "oa_rand10_Blate_mvp_vs_oracle_by_category.csv", index=False)
    set_display()
    print(f"oracle tau (B_late) = {tau_o:.3g}")
    print(G.round(4).to_string(index=False))
    print("\n[correlation over the 24 non-'all' groups]"); print(corr.round(3).to_string())
    print(C.round(4).to_string(index=False))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
