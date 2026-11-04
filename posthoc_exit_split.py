"""POST-HOC split of the hop loss under camera outage (not pre-registered; report as post hoc).

    python posthoc_exit_split.py --config configs/porto_cctv_confirm.yaml

Baseline = transitions without outage (work_dir), outage = transitions rebuilt after removing
sightings at offline sites from the outage start (same sites as posthoc_outage.py, seed 7).
Transitions are matched on (trip_id, t_exit, src).

Baseline hops (non-exit, t_exit in [start, end of test)) are classified as
  unchanged         : same source and same next camera under outage
  rerouted          : same source, next camera offline -> target next seen at a later camera
                      within T_max (the hop survives but ends farther away)
  a_src_offline     : the source site is offline, so the hop disappears
  b_exit_converted  : same source, the target is not seen again within T_max (10 min)
                      -> the hop becomes an 'exit' and leaves the evaluation. Split into
                      _trip_end (baseline path ended right after the offline site: the lost hop
                      was the last one) and _lost_track (baseline continued to an online camera,
                      but more than T_max later: tracking really is interrupted)
  episode_changed   : the source episode lost its last-ending sighting at an offline site
                      (same trip, different src / t_exit); reappears as 'new' on the outage side
Identity: baseline_hops - outage_hops = a_src_offline + b_exit_converted + episode_changed - out_new
('new' = the source episode survived at an overlapping online camera; a_net_of_new nets it out).
Outage hops are classified as unchanged / rerouted / new, and flagged 'reacq_by_outage' when
they start a chain only because the previous hop was exit-converted (hopkind 2 created by the outage).
n_skipped_off = number of consecutive offline sites the baseline path passed before the next
online camera (limits a one-step outage-aware composition).
Coverage by category uses per-hop hits of posthoc_outage_diag.py runs when they exist.
Output: <out_dir>_posthoc/exit_split/.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ccpilot.geo import date_to_unix
from ccpilot.posthoc import load_config, offline_sites, outage_events, set_display
from ccpilot.predictors import candidate_sets

KEY = ["trip_id", "t_exit", "src"]
METHODS = ["static", "qr_ogd", "mvp_global", "mvp_log"]


def classify(base, out, off, t_start, t_end):
    off = set(off)
    B = base.set_index("tr_id", drop=False)
    in_per = lambda d: (d["t_exit"] >= t_start) & (d["t_exit"] < t_end)
    b = base[in_per(base) & ~base["is_exit"]].copy()
    o_all = out[in_per(out)]
    m = b.merge(o_all[KEY + ["tr_id", "is_exit", "first_cam"]].rename(
        columns={"tr_id": "tr_id_out", "is_exit": "exit_out", "first_cam": "first_cam_out"}), on=KEY, how="left")
    found = m["tr_id_out"].notna()
    cat = np.where(~found, np.where(m["src"].isin(off), "a_src_offline", "episode_changed"),
                   np.where(m["exit_out"].astype(bool), "b_exit_converted",
                            np.where(m["first_cam"] == m["first_cam_out"], "unchanged", "rerouted")))
    m["category"] = cat
    # consecutive offline sites on the baseline path after the source
    fc = B["first_cam"].to_numpy(); ex = B["is_exit"].to_numpy(); pos = {t: i for i, t in enumerate(B.index)}
    skipped, ends_exit = [], []
    for tid, c in zip(m["tr_id"].to_numpy(), m["category"].to_numpy()):
        if c not in ("rerouted", "b_exit_converted"):
            skipped.append(0); ends_exit.append(False); continue
        i = pos[tid]; k = 0
        while i < len(fc) and not ex[i] and fc[i] in off:
            k += 1; i += 1
        skipped.append(k)
        ends_exit.append(bool(i >= len(fc) or ex[i]))
    m["n_skipped_off"] = skipped
    # True: in the baseline the path already ended (exit) right after the offline site(s),
    # i.e. the lost hop was the trip's last hop, not a track interrupted mid-trip
    m["baseline_ends_after_off"] = ends_exit

    o = o_all[~o_all["is_exit"]].copy()
    mo = o.merge(base[KEY + ["is_exit", "first_cam"]].rename(
        columns={"is_exit": "exit_base", "first_cam": "first_cam_base"}), on=KEY, how="left")
    fo = mo["exit_base"].notna()
    mo["category"] = np.where(~fo, "new", np.where(mo["exit_base"].astype(bool), "new_from_exit",
                              np.where(mo["first_cam"] == mo["first_cam_base"], "unchanged", "rerouted")))
    # chain start created by an exit conversion: previous outage transition is an exit that was a hop in baseline
    O = out.set_index("tr_id")
    prev = mo["tr_id"] - 1
    prev_ok = prev.isin(O.index)
    pk = O.reindex(prev)[KEY + ["is_exit"]].reset_index(drop=True)
    pk_base = pk.merge(base[KEY + ["is_exit"]].rename(columns={"is_exit": "exit_base"}), on=KEY, how="left")
    conv = prev_ok.to_numpy() & pk["is_exit"].fillna(False).to_numpy().astype(bool) & \
        (pk_base["exit_base"] == False).to_numpy() & (mo["trip_id"].to_numpy() == O.reindex(prev)["trip_id"].to_numpy())  # noqa: E712
    mo["reacq_by_outage"] = conv & (mo["hop"].to_numpy() == 0)
    mo["hopkind"] = np.where(mo["hop"] > 0, 0, np.where(mo["chain"] == 0, 1, 2))
    return m, mo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--scenarios", nargs="*", default=["rand10", "rand20", "rand30", "region"])
    ap.add_argument("--starts", nargs="*", default=["2014-06-21", "2014-06-12"])
    ap.add_argument("--predictor", default="src_zone_hour_speed")
    ap.add_argument("--radius", type=float, default=800.0)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    base_cfg = load_config(a.config)
    tz = base_cfg["timezone"]; ex = base_cfg["eval"]
    work = Path(base_cfg["work_dir"])
    sight = pd.read_parquet(work / "sightings.parquet")
    cams = pd.read_csv(work / "cameras.csv")
    base = pd.read_parquet(work / "transitions.parquet")
    sites = offline_sites(["none", "rand10", "rand20", "rand30", "region"], cams, base, base_cfg, a.radius, a.seed)
    t_end = date_to_unix(ex["splits"]["test"][-1]["range"][1], tz)
    tr_train = base[(base["t_exit"] >= date_to_unix(ex["splits"]["train"][0], tz)) &
                    (base["t_exit"] < date_to_unix(ex["splits"]["train"][1], tz))]
    cand = candidate_sets(cams, tr_train, ex["candidate_radius_m"])
    root = Path(base_cfg["out_dir"] + "_posthoc") / "exit_split"; root.mkdir(parents=True, exist_ok=True)
    diag = Path(base_cfg["out_dir"] + "_posthoc") / "outage_diag"
    loss_rows, out_rows, cov_rows = [], [], []
    for start in a.starts:
        t_start = date_to_unix(start, tz)
        for sc in a.scenarios:
            off = sites[sc]
            out, truth, _, _ = outage_events(sight, base_cfg, off, t_start)
            m, mo = classify(base, out, off, t_start, t_end)
            # structural: no truth camera in the source's candidate set (no threshold can find it)
            tcam = truth.groupby("tr_id")["cam"].apply(set)
            mo["struct"] = [not (tcam.get(t, set()) & set(cand[int(s)].tolist()))
                            for t, s in zip(mo["tr_id"], mo["src"])]
            for w, lo, hi in [("0-48h", 0, 48), ("all_post", 0, 1e9)]:
                bm = m[(m["t_exit"] - t_start < hi * 3600) & (m["t_exit"] - t_start >= lo * 3600)]
                om = mo[(mo["t_exit"] - t_start < hi * 3600) & (mo["t_exit"] - t_start >= lo * 3600)]
                n_b, n_o = len(bm), len(om)
                r = {"start": start, "scenario": sc, "window": w, "n_offline": len(off),
                     "baseline_hops": n_b, "outage_hops": n_o, "net_loss": n_b - n_o}
                for c in ["unchanged", "rerouted", "a_src_offline", "b_exit_converted", "episode_changed"]:
                    r[c] = int((bm["category"] == c).sum())
                for c in ["new", "new_from_exit"]:
                    r["out_" + c] = int((om["category"] == c).sum())
                bx = bm[bm["category"] == "b_exit_converted"]
                r["b_exit_converted_trip_end"] = int(bx["baseline_ends_after_off"].sum())
                r["b_exit_converted_lost_track"] = int((~bx["baseline_ends_after_off"]).sum())
                r["a_net_of_new"] = r["a_src_offline"] - r["out_new"]    # src moved to an overlapping online camera
                r["out_reacq_by_outage"] = int(om["reacq_by_outage"].sum())
                r["out_hopkind2"] = int((om["hopkind"] == 2).sum())
                for c in ["rerouted", "b_exit_converted"]:
                    s = bm.loc[bm["category"] == c, "n_skipped_off"]
                    r[f"{c}_skip1"] = int((s == 1).sum()); r[f"{c}_skip2plus"] = int((s >= 2).sum())
                r["rerouted_struct"] = int(om.loc[om["category"] == "rerouted", "struct"].sum())
                loss_rows.append(r)
            m.assign(start=start, scenario=sc).to_parquet(root / f"baseline_hops_{start.replace('-', '')}_{sc}.parquet")
            mo.assign(start=start, scenario=sc).to_parquet(root / f"outage_hops_{start.replace('-', '')}_{sc}.parquet")
            # coverage by outage-side category (hits from posthoc_outage_diag.py, if run)
            hp = diag / f"start_{start.replace('-', '')}" / sc / "hits.parquet"
            if hp.exists():
                H = pd.read_parquet(hp)
                J = mo.merge(H[["tr_id"] + [f"hit|{a.predictor}|{x}" for x in METHODS]], on="tr_id", how="inner")
                J["cat2"] = np.where(J["reacq_by_outage"], "reacq_by_outage", J["category"])
                for w, hi in [("0-48h", 48), ("all_post", 1e9)]:
                    Jw = J[(J["t_exit"] - t_start) < hi * 3600]
                    for (cat, st), g in Jw.groupby(["cat2", "struct"]):
                        rr = {"start": start, "scenario": sc, "window": w, "category": cat, "structural": bool(st),
                              "n": len(g)}
                        for x in METHODS:
                            rr[x] = g[f"hit|{a.predictor}|{x}"].mean()
                        cov_rows.append(rr)
                    tot = {"start": start, "scenario": sc, "window": w, "category": "ALL", "structural": None, "n": len(Jw)}
                    for x in METHODS:
                        tot[x] = Jw[f"hit|{a.predictor}|{x}"].mean()
                    cov_rows.append(tot)
    L = pd.DataFrame(loss_rows); L.to_csv(root / "hop_loss_split.csv", index=False)
    Cv = pd.DataFrame(cov_rows); Cv.to_csv(root / "coverage_by_category.csv", index=False)
    set_display()
    print("\n================ POST-HOC EXIT-CONVERSION SPLIT (not pre-registered) ================")
    print(L.to_string(index=False))
    if len(Cv):
        print("\n[coverage by outage-side category, primary predictor]")
        print(Cv.round(4).to_string(index=False))
    print(f"\n-> {root}")


if __name__ == "__main__":
    main()
