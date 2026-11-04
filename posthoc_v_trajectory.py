"""POST-HOC: does negative V accumulated during saturation cause over-search later? (not pre-registered)

    python posthoc_v_trajectory.py

Confirmation period, rand10 (site seed 7) from 2014-06-21, reduced methods, mvp_log for the base and the
outage-aware predictor (outage_suite/rand10_s7, run with --mvp-diag), against the no-outage run none_s7.
Daily (24 h after the outage start):
  coverage, mean cost, cost / same-day mvp_log cost without outage, share of queries in the top bucket
  (q >= 39/40), mean q, and for group 'all' the (V, N) of every bucket at the daily snapshots.
Over-search = coverage well above 0.95 together with cost above the no-outage level after recovery.
Output: <out_dir>_posthoc/v_trajectory/.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.geo import date_to_unix
from ccpilot.posthoc import load_config, set_display

PRED = "src_zone_hour_speed"


def main():
    cfg = load_config("configs/porto_cctv_confirm.yaml")
    root = Path(cfg["out_dir"] + "_posthoc")
    t0 = date_to_unix("2014-06-21", cfg["timezone"])
    d = root / "outage_suite" / "rand10_s7"
    H = pd.read_parquet(d / "hits.parquet"); Q = pd.read_parquet(d / "mvp_q.parquet")
    Hn = pd.read_parquet(root / "outage_suite" / "none_s7" / "hits.parquet")
    ST = pd.read_parquet(d / "mvp_state.parquet")
    assert (H["tr_id"].to_numpy() == Q["tr_id"].to_numpy()).all()
    H["day"] = np.floor((H["t_exit"] - t0) / 86400).astype(int)
    Hn["day"] = np.floor((Hn["t_exit"] - t0) / 86400).astype(int)
    nday = Hn.groupby("day")[f"cost|{PRED}|mvp_log"].mean()
    rows = []
    for pk, pn in [("base", PRED), ("oa", PRED + "_oa")]:
        q = Q[f"q|{pn}|mvp_log"].to_numpy()
        for day, g in H.groupby("day"):
            if day < -2:
                continue
            m = (H["day"] == day).to_numpy()
            rows.append({"predictor": pk, "day": day, "n": int(m.sum()),
                         "coverage": g[f"hit|{pn}|mvp_log"].mean(), "cost": g[f"cost|{pn}|mvp_log"].mean(),
                         "cost_over_none_same_day": g[f"cost|{pn}|mvp_log"].mean() / nday.get(day, np.nan),
                         "coverage_none": Hn.loc[Hn["day"] == day, f"hit|{PRED}|mvp_log"].mean(),
                         "top_bucket_share": (q[m] >= 39 / 40).mean(), "mean_q": q[m].mean()})
    D = pd.DataFrame(rows)
    st = ST[(ST["method"] == "mvp_log") & (ST["group"] == "all")].copy()
    st["day"] = np.round((st["t_snap"] - t0) / 86400).astype(int)
    st["predictor"] = np.where(st["predictor"] == PRED, "base", "oa")
    V = st.pivot_table(index=["predictor", "bucket"], columns="day", values="V")
    N = st.pivot_table(index=["predictor", "bucket"], columns="day", values="N")
    out = root / "v_trajectory"; out.mkdir(parents=True, exist_ok=True)
    D.to_csv(out / "daily_mvp_log.csv", index=False)
    st.to_csv(out / "state_group_all_mvp_log.csv", index=False)
    set_display()
    print(D.round(4).to_string(index=False))
    used = N.max(axis=1) > 50
    print("\n[V, group all, buckets with N > 50]"); print(V[used].round(1).to_string())
    print("\n[N]"); print(N[used].round(0).to_string())
    print(f"-> {out}")


if __name__ == "__main__":
    main()
