"""Shared helpers for the posthoc_*.py scripts (loading events, reduced configs, cost ratios)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_config(path):
    return yaml.safe_load(open(path, encoding="utf-8"))


def load_work(cfg):
    """Events already computed for cfg: (transitions, truth, cameras, n_bins)."""
    work = Path(cfg["work_dir"])
    trans = pd.read_parquet(work / "transitions.parquet")
    truth = pd.read_parquet(work / "truth.parquet")
    cams = pd.read_csv(work / "cameras.csv")
    n_bins = json.load(open(work / "meta.json"))["n_bins"]
    return trans, truth, cams, n_bins


def reduce_cfg(cfg, predictor):
    """Restrict cfg (in place) to one predictor and the reduced post-hoc method set."""
    ex = cfg["eval"]
    ex["predictors"] = {predictor: ex["predictors"][predictor]}
    ex["mondrian"] = {"mondrian_hour_hop_speed": ex["mondrian"]["mondrian_hour_hop_speed"]}
    ex["aci_variants"] = [v for v in ex["aci_variants"] if v["name"] == "aci_g0005"]
    mg = ex["multigroup"]
    mg["predictors"] = [predictor]
    mg["mvp_variants"] = [v for v in mg["mvp_variants"] if v["name"] in ("mvp_log", "mvp_global")]
    ex["plot_methods"] = ["static", "aci_g0005", "mvp_log", "qr_ogd"]
    # post-hoc baseline added after the confirmation run (the frozen confirm config is not edited)
    ex.setdefault("citytrac", {"targets": [0.95, 0.99], "window_q": 0.98, "min_n": 30})
    return cfg


def add_cost_over_oracle(df, key):
    """Add cost_mean_cam_s / oracle cost, matching the oracle row on (key, segment)."""
    orc = df[df["method"] == "oracle(post-hoc)"].set_index([key, "segment"])["cost_mean_cam_s"]
    df["cost_over_oracle"] = df["cost_mean_cam_s"].to_numpy() / orc.reindex(
        pd.MultiIndex.from_frame(df[[key, "segment"]])).to_numpy()
    return df


def set_display(max_rows=500):
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", max_rows)


def offline_sites(scenarios, cams, trans, cfg, radius=800.0, seed=7):
    """Offline camera sites per outage scenario ('none', 'randXX', 'region').
    One RNG is shared across scenarios in the given order, so 'rand10' drawn first
    gives the same sites whatever follows it."""
    from .geo import date_to_unix
    tz = cfg["timezone"]; tr = cfg["eval"]["splits"]["train"]
    rng = np.random.default_rng(seed)
    ids = cams["cam_id"].to_numpy()
    m_train = (trans["t_exit"] >= date_to_unix(tr[0], tz)) & (trans["t_exit"] < date_to_unix(tr[1], tz))
    busiest = int(trans.loc[m_train, "src"].value_counts().idxmax())
    xy = cams.set_index("cam_id")[["x", "y"]]
    d_busy = np.hypot(xy["x"] - xy.loc[busiest, "x"], xy["y"] - xy.loc[busiest, "y"])
    out = {}
    for sc in scenarios:
        if sc == "none":
            out[sc] = []
        elif sc.startswith("rand"):
            k = int(round(len(ids) * int(sc[4:]) / 100))
            out[sc] = sorted(rng.choice(ids, size=k, replace=False).tolist())
        elif sc == "region":
            out[sc] = sorted(d_busy.index[d_busy <= radius].tolist())
        else:
            raise SystemExit(f"unknown scenario {sc}")
    return out


def outage_events(sight, cfg, off, t_start):
    """Remove sightings at offline sites from t_start on and rebuild hop transitions."""
    from . import events
    drop = sight["cam"].isin(off) & (sight["t_in"] >= t_start)
    trans, truth, n_bins = events.build_transitions(sight.loc[~drop].reset_index(drop=True), cfg)
    return trans, truth, n_bins, int(drop.sum())


def fixed_region_sites(ref_cfg, n_min=20):
    """Geographically fixed region outage used for every period (post hoc):
    centre = busiest source site in the training period of ref_cfg (the confirmation config),
    radius = smallest radius (m) that puts at least n_min sites (centre included) offline."""
    from .geo import date_to_unix
    work = Path(ref_cfg["work_dir"]); tz = ref_cfg["timezone"]; tr = ref_cfg["eval"]["splits"]["train"]
    cams = pd.read_csv(work / "cameras.csv")
    trans = pd.read_parquet(work / "transitions.parquet", columns=["src", "t_exit"])
    m = (trans["t_exit"] >= date_to_unix(tr[0], tz)) & (trans["t_exit"] < date_to_unix(tr[1], tz))
    centre = int(trans.loc[m, "src"].value_counts().idxmax())
    xy = cams.set_index("cam_id")[["x", "y"]]
    d = np.hypot(xy["x"] - xy.loc[centre, "x"], xy["y"] - xy.loc[centre, "y"]).sort_values()
    radius = float(d.iloc[n_min - 1])
    sites = sorted(d.index[d <= radius].tolist())
    return centre, radius, sites
