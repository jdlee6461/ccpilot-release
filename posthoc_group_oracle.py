"""POST-HOC (review M1, 2026-10-01): hindsight references that satisfy the group condition.
(not pre-registered; additional analysis after the main results)

    python posthoc_group_oracle.py

Held-out period, segments test_jun_a and test_jun_b, primary predictor, evaluation seed 0, no outage.
Two hindsight references, fitted on the evaluation segment's own scores:
  (a) group-minimum rule: for each of the 25 pre-registered groups, tau_G = the largest threshold at which the
      group's recall is >= 1 - alpha; each hop uses the minimum tau_G over the groups that contain it. In-sample,
      every group then has recall >= 1 - alpha (checked).
  (b) hindsight group quantile regression: the qr_groups design (log score, intercept + reference-coded indicators
      of the six attributes, quantile level alpha) fitted to the segment's scores without subsampling and applied
      to the same hops (LP solved with HiGHS interior point + crossover; the default dual simplex did not finish
      within 40 min for ~265,000 hops; same LP, same optimum).
Costs need the predictor's probability matrices, which are not saved: the predictor is refitted exactly as in
evaluate.run (no new experiment) and three checks must pass: refitted scores equal the saved scores, the static
costs recomputed at its constant threshold equal the saved costs, and the hindsight oracle's recall and cost equal
the frozen summary.
Output: results/porto_cctv_confirm_posthoc/group_oracle/{group_oracle_summary.csv, group_oracle_groups.csv}
(groups file: recall and mean cost per group; static and ACI added there 2026-10-01 for the per-group cost comparison)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.calibration import conformal_tau
from ccpilot.evaluate import _add_spatial, _add_strata, _period_mask, _wilson_ub
from ccpilot.multigroup import qr_group_taus
from ccpilot.posthoc import load_config, load_work, set_display
from ccpilot.predictors import VisibilityModel, _truth_by_tr, candidate_sets
from posthoc_regrade import DEFS

PRED = "src_zone_hour_speed"
ATTRS = ["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
CFG = "configs/porto_cctv_confirm.yaml"


def groups_of(df):
    """25 pre-registered groups: list of (key, boolean mask)."""
    out = [("grp_all=0", np.ones(len(df), bool))]
    for d in ATTRS:
        for v in sorted(df[d].unique()):
            out.append((f"{d}={int(v)}", (df[d] == v).to_numpy()))
    return out


def group_stats(hit, G, min_n, cost=None):
    rows = []
    for key, m in G:
        n = int(m.sum()); k = int(hit[m].sum())
        rows.append({"key": key, "n": n, "recall": k / n, "ub95": _wilson_ub(k, n), "judged": n >= min_n,
                     "cost_cam_s": float(np.mean(cost[m])) if cost is not None else np.nan})
    D = pd.DataFrame(rows)
    J = D[D.judged]
    return D, {"recall_mean": float(hit.mean()), "worst": float(J.recall.min()), "worst_key": J.loc[J.recall.idxmin(), "key"],
               "below94": int((J.ub95 < 0.94).sum()), "below95": int((J.ub95 < 0.95).sum())}


def main():
    cfg = load_config(CFG)
    ev, ex, tz = cfg["events"], cfg["eval"], cfg["timezone"]
    delta = ev["bin_s"]; alpha = 1 - ex["target_recall"]; min_n = ex.get("min_group_n", 200)
    ph = Path(cfg["out_dir"] + "_posthoc")
    H = pd.read_parquet(ph / "outage_suite" / "none_s7" / "hits.parquet")
    F = pd.read_csv(Path(cfg["out_dir"]) / "summary.csv")
    F = F[F.predictor == PRED].set_index(["method", "segment"])

    trans, truth, cams, n_bins = load_work(cfg)
    t = trans["t_exit"].to_numpy(); sp = ex["splits"]
    m_train = _period_mask(t, sp["train"], tz)
    seg_masks = {s["name"]: _period_mask(t, s["range"], tz) for s in sp["test"]}
    m_test = np.zeros(len(t), bool)
    for m in seg_masks.values():
        m_test |= m
    trans = _add_strata(trans, trans[m_train], ex.get("n_speed_bins", 4))
    trans = _add_spatial(trans, m_train, cams, ex.get("n_spatial_bins", 4))
    ok = ~trans["is_exit"].to_numpy()
    tr_train = trans[m_train]
    m_cal = _period_mask(t, sp["cal"], tz)
    tr_cal = trans[m_cal & ok].sort_values("t_exit").reset_index(drop=True)
    tr_test = trans[m_test & ok].sort_values("t_exit").reset_index(drop=True)
    tm = _truth_by_tr(truth)
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    vm = VisibilityModel(ex["predictors"][PRED], cand, n_bins, **ex["model"]).fit(tr_train, tm)
    s_cal, _, _ = vm.score(tr_cal, tm)
    s_test, kid, _ = vm.score(tr_test, tm)

    J = tr_test[["tr_id"] + ATTRS].assign(s=s_test, kid=kid).merge(
        H[["tr_id", "segment", f"score|{PRED}"] + [f"{a}|{PRED}|{m}" for a in ("hit", "cost") for m in ("static", "aci_g0005", "mvp_log", "qr_ogd")]],
        on="tr_id", how="inner", validate="one_to_one")
    assert len(J) == len(H) == len(tr_test)
    J["seg"] = J["segment"].replace({"B_early": "test_jun_b", "B_late": "test_jun_b"})
    # check 1: scores; check 2: static cost (constant threshold) recomputed
    d_score = float(np.abs(J["s"] - J[f"score|{PRED}"]).max())
    tau_static = conformal_tau(s_cal, alpha)
    c_static = vm.cost(J["kid"].to_numpy(), tau_static, delta)
    d_static = float(np.abs(c_static - J[f"cost|{PRED}|static"].to_numpy()).max())
    rows, grows, checks = [], [], {"max_abs_score_diff": d_score, "max_abs_static_cost_diff": d_static}
    for seg in ["test_jun_a", "test_jun_b"]:
        B = J[J.seg == seg].reset_index(drop=True)
        s = B["s"].to_numpy(); k = B["kid"].to_numpy()
        G = groups_of(B)
        # hindsight oracle (check 3 against the frozen summary)
        tau_o = conformal_tau(s, alpha)
        hit_o = s >= tau_o; cost_o = vm.cost(k, tau_o, delta)
        fo = F.loc[("oracle(post-hoc)", seg)]
        checks[f"oracle_recall_diff_{seg}"] = abs(hit_o.mean() - fo["coverage"])
        checks[f"oracle_cost_rel_diff_{seg}"] = abs(cost_o.mean() - fo["cost_mean_cam_s"]) / fo["cost_mean_cam_s"]
        # (a) group-minimum rule
        tau_G = {}
        for key, m in G:
            sg = np.sort(s[m])[::-1]
            need = int(np.ceil((1 - alpha) * len(sg)))
            tau_G[key] = float(sg[need - 1])            # largest tau with recall >= 1 - alpha (s >= tau hits)
        tau_a = np.full(len(B), np.inf)
        for key, m in G:
            tau_a[m] = np.minimum(tau_a[m], tau_G[key])
        hit_a = s >= tau_a; cost_a = vm.cost(k, tau_a, delta)
        # (b) hindsight group QR, full fit
        tau_b, beta_b = qr_group_taus(B, s, B, ATTRS, alpha, max_n=len(B) + 1, seed=0, lp_method="highs-ipm")
        u = np.log(np.maximum(s, 1e-8)) - np.log(tau_b)        # pinball objective of the fit (LP optimum)
        checks[f"qr_objective_{seg}"] = float(np.sum(np.where(u > 0, alpha * u, (alpha - 1) * u)))
        checks[f"qr_share_below_{seg}"] = float((s < tau_b).mean())
        hit_b = s >= tau_b; cost_b = vm.cost(k, tau_b, delta)
        refs = {"oracle": (hit_o, cost_o), "group_min": (hit_a, cost_a), "hindsight_qr": (hit_b, cost_b),
                "mvp_log": (B[f"hit|{PRED}|mvp_log"].to_numpy().astype(bool), B[f"cost|{PRED}|mvp_log"].to_numpy()),
                "qr_ogd": (B[f"hit|{PRED}|qr_ogd"].to_numpy().astype(bool), B[f"cost|{PRED}|qr_ogd"].to_numpy()),
                # added 2026-10-01 for the per-group cost comparison (groups file only)
                "static": (B[f"hit|{PRED}|static"].to_numpy().astype(bool), B[f"cost|{PRED}|static"].to_numpy()),
                "aci": (B[f"hit|{PRED}|aci_g0005"].to_numpy().astype(bool), B[f"cost|{PRED}|aci_g0005"].to_numpy())}
        for name, (h, c) in refs.items():
            D, st = group_stats(h, G, min_n, c)
            grows.append(D.assign(segment=seg, method=name))
            if name in ("static", "aci"):
                continue
            rows.append({"segment": seg, "method": name, **st, "cost_cam_s": float(c.mean()),
                         "n_groups_lt200_used": int((~D.judged).sum()) if name in ("group_min", "hindsight_qr") else 0})
        D_a, _ = group_stats(hit_a, G, min_n)
        checks[f"group_min_all_groups_ge_target_{seg}"] = bool((D_a.recall >= 1 - alpha - 1e-12).all())
    S = pd.DataFrame(rows)
    for seg in ["test_jun_a", "test_jun_b"]:
        m = S.segment == seg
        S.loc[m, "ratio_vs_oracle"] = S.loc[m, "cost_cam_s"] / S.loc[m & (S.method == "oracle"), "cost_cam_s"].iloc[0]
        S.loc[m, "ratio_vs_group_min"] = S.loc[m, "cost_cam_s"] / S.loc[m & (S.method == "group_min"), "cost_cam_s"].iloc[0]
    print("[checks]", checks)
    assert d_score == 0 and d_static < 1e-9 and all(v < 1e-9 for k_, v in checks.items() if k_.startswith("oracle_"))
    assert all(v for k_, v in checks.items() if k_.startswith("group_min_all"))
    out = ph / "group_oracle"; out.mkdir(parents=True, exist_ok=True)
    S.to_csv(out / "group_oracle_summary.csv", index=False)
    pd.concat(grows, ignore_index=True).to_csv(out / "group_oracle_groups.csv", index=False)
    pd.DataFrame([checks]).to_csv(out / "checks.csv", index=False)
    set_display()
    print(S.round(4).to_string(index=False))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
