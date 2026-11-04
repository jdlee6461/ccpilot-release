"""POST HOC (external review, REVIEW_PLAN rev 5 appendix B7): mechanical evaluation of the result consequences of
label set (v). No sentence is chosen; the conditions of B7a-B7d and the mixed rule are evaluated as written.

    python posthoc_review_b7.py

Inputs: review/B_v_differences.csv, review/B_v_estimates.csv (posthoc_review_report.py --part B_v, --collect),
review/v_updates/<tag>.csv (posthoc_review_labels.py --run-v). Scope combined, target 0.95 (B7), seed means,
conservative 95% bounds. Also: the rev 3 additional-target rule for refit7 under (iv) (order online vs refit on the
post-gap d at 0.95 against confirm2, where the refit has the smaller deficit).
Output: review/B_v_consequence_check.csv, review/B_v_updates_postgap.csv.
"""
import numpy as np
import pandas as pd

import posthoc_review_common as C

T = 0.95
ONLINE = [("mvp_log", "iv_mvp_log", "v_mvp_log"), ("qr_ogd", "iv_qr_ogd", "v_qr_ogd"),
          ("A2_aci_groups", "iv_aci_groups", "v_aci_groups")]


def main():
    D = pd.read_csv(C.OUT / "B_v_differences.csv").query("scope == 'combined'")
    E = pd.read_csv(C.OUT / "B_v_estimates.csv").query("scope == 'combined'")

    def diff(ref, comp, est, t=T):
        r = D[(D.reference == ref) & (D.comparator == comp) & (D.estimand == est) & (D.target == t)]
        assert len(r) == 1, (ref, comp, est, t)
        return r.iloc[0]
    # post-gap label updates per run (v)
    U = []
    for b in C.BLOCKS:
        for t in C.TARGETS:
            for s in C.SEEDS:
                u = pd.read_csv(C.OUT / "v_updates" / f"{b}_t{int(round(t * 1000)):04d}_s{s}.csv").set_index("group")
                U.append({"block": b, "target": t, "seed": s, **{c.split("|")[1]: u.loc["hopkind=2", c] for c in u.columns
                                                                  if c.startswith("n_updates|")},
                          "max_abs_theta_qr_ogd": u.loc["hopkind=2", "max_abs_theta|qr_ogd"]})
    U = pd.DataFrame(U)
    U.to_csv(C.OUT / "B_v_updates_postgap.csv", index=False)
    rows = []

    def rec(rule, method, cond, value, sat):
        rows.append({"rule": rule, "method": method, "condition": cond, "value": value, "satisfied": bool(sat)})
    cases = {}
    for full, iv, v in ONLINE:
        a, b = diff(full, v, "D_diff"), diff(iv, v, "D_diff")
        va = f"D(v) - D(full) {a.point:.4f} [{a.lo:.4f}, {a.hi:.4f}]"
        vb = f"D(v) - D(iv) {b.point:.4f} [{b.lo:.4f}, {b.hi:.4f}]"
        b7a = a.hi <= 0.02
        b7b = (not b7a) and b.hi < 0
        b7c = (not b7a) and not b7b
        rec("B7a", v, "upper bound of D(v) - D(full) <= 0.02", va, b7a)
        rec("B7b", v, "not B7a and D(iv) - D(v) interval excludes 0 with v better (D(v) - D(iv) upper bound < 0)", vb, b7b)
        rec("B7c", v, "not B7a and not B7b", vb, b7c)
        med = float(np.median(U.query("target == @T")[v.replace("v_", "")]))
        rec("B7d", v, "median label updates of the post-gap group per run < 200 (target 0.95, 10 runs)", f"median {med:.0f}",
            med < 200)
        if full != "A2_aci_groups":
            cases[v] = "B7a" if b7a else "B7b" if b7b else "B7c"
    rec("mixed", "mvp_log, qr_ogd", "the two online methods fall in different cases (B7a-c)", str(cases),
        len(set(cases.values())) > 1)
    # rev 3 additional-target rule, refit7 under (iv) at 0.95 (confirm2: refit has the smaller post-gap deficit)
    for m in ("iv_mvp_log", "iv_qr_ogd", "v_mvp_log", "v_qr_ogd"):
        r = diff("Biv_refit7_a", m, "reacq_d_diff")
        rec("additional target 0.93", m, "post-gap d(online) - d(refit7 (iv)) upper bound < 0 (online smaller: order "
            "differs from confirm2)", f"{r.point:.4f} [{r.lo:.4f}, {r.hi:.4f}]", r.hi < 0)
    out = pd.DataFrame(rows)
    out.to_csv(C.OUT / "B_v_consequence_check.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
