"""Apply the pre-registered primary-method selection rule (PREREGISTRATION.md, section 3)
to the EXPLORATORY summaries.

    python select_primary.py results/porto_cctv/summary.csv results/porto_cctv_rep/summary.csv
"""
import sys

import pandas as pd

# optional: --regrade <regrade_summary.csv ...> replaces rule-1 counts with the pre-registered
# 25-group definition (definition == 'prereg_25'); cost figures still come from summary.csv
args = sys.argv[1:]
regrade = []
if "--regrade" in args:
    i = args.index("--regrade")
    regrade, args = args[i + 1:], args[:i]
sys.argv = [sys.argv[0]] + args

PRED = "src_zone_hour_speed"
CANDIDATES = ["mvp_groups", "mvp_log", "qr_groups", "qr_ogd"]
COST_FACTOR = 1.20

df = pd.concat([pd.read_csv(p) for p in sys.argv[1:]], ignore_index=True)
df = df[df["predictor"] == PRED]
if regrade:
    rg = pd.concat([pd.read_csv(p) for p in regrade], ignore_index=True)
    rg = rg[(rg["predictor"] == PRED) & (rg["definition"] == "prereg_25")]
    key = rg.set_index(["method", "segment"])["n_sig_below_0.94"]
    idx = pd.MultiIndex.from_frame(df[["method", "segment"]])
    new = key.reindex(idx).to_numpy()
    has = ~pd.isna(new)
    df.loc[has, "n_groups_sig_below_bar"] = new[has]
    print(f"[select] rule 1 uses the pre-registered 25-group definition for {int(has.sum())} rows")
oracle = df[df["method"] == "oracle(post-hoc)"].set_index("segment")["cost_mean_cam_s"]
rows = []
for m in CANDIDATES:
    d = df[df["method"] == m].set_index("segment")
    if d.empty:
        continue
    ratio = (d["cost_mean_cam_s"] / oracle.reindex(d.index)).mean()
    rows.append({"method": m, "segments": len(d),
                 "max_n_sig_below": int(d["n_groups_sig_below_bar"].max()),
                 "n_violating_segments": int((d["n_groups_sig_below_bar"] > 0).sum()),
                 "min_worst_group": d["worst_group_cov"].min(),
                 "mean_cost": d["cost_mean_cam_s"].mean(), "mean_cost_over_oracle": ratio,
                 "rule1_ok": bool((d["n_groups_sig_below_bar"] == 0).all()),
                 "rule2_ok": bool(ratio <= COST_FACTOR)})
t = pd.DataFrame(rows).sort_values("mean_cost")
pd.set_option("display.width", 200)
print(t.round(4).to_string(index=False))
ok = t[t.rule1_ok & t.rule2_ok]
if len(ok) == 0:
    ok = t[t.rule1_ok]
    print("\nNo candidate passes rules 1 and 2; falling back to rule 4 (rule 1 only).")
if len(ok) == 0:
    print("\nNo candidate passes rule 1. Selection rule cannot be applied as registered -> discuss before confirming.")
else:
    prim = ok.iloc[0]["method"]
    print(f"\nPRIMARY  : {prim}")
    if len(ok) > 1:
        print(f"SECONDARY: {ok.iloc[1]['method']}")
    else:  # rule 5 (v3)
        rest = t[(t.method != prim) & t.rule2_ok].copy()
        rest["n_viol"] = [int((df[(df.method == m)]["n_groups_sig_below_bar"] > 0).sum()) for m in rest.method]
        rest = rest.sort_values(["n_viol", "min_worst_group"], ascending=[True, False])
        if len(rest):
            print(f"SECONDARY: {rest.iloc[0]['method']}  (rule 5: fewest rule-1 violations, then highest min worst-group)")
