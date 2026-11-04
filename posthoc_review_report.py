"""POST HOC (external review): estimates and intervals per part (REVIEW_PLAN.md), from stored and recomputed outcomes.

    python posthoc_review_report.py --part A|B_aci|B_refit|B_v|C_<predictor>|C_refit --target T
    python posthoc_review_report.py --collect

Per (part, target): review/parts/<part>_tXXXX_{est,diff,cells}.csv. --collect concatenates them into review/<part>_*.csv.
Stored methods come from results/porto_cctv_confirm2/runs (read only); new ones from work/review_cache/runs.
"""
import argparse
from pathlib import Path

import pandas as pd

import posthoc_review_common as C

C.threads(1)
import numpy as np  # noqa: E402

import posthoc_review_summary as S  # noqa: E402

MAIN = ["static", "mondrian_hour_hop_speed", "aci_g0005", "qr_groups", "qr_groups_refit", "mvp_log", "qr_ogd"]
NEW_COLS = {"A1_mondrian_small", "A2_aci_groups", "A3_qr_groups_inter", "Bi_aci", "Bii_aci", "Bii_mvp_log", "Bii_qr_ogd"}
LABELS = {f"{l}_{m}" for l in ("iii", "iv") for m in ("aci", "aci_groups", "mvp_log", "qr_ogd")}   # posthoc_review_labels.py
LABELS_V = {f"v_{m}" for m in ("aci_groups", "mvp_log", "qr_ogd")}   # posthoc_review_labels.py --run-v (REVIEW_PLAN rev 5)
REFIT = {"Bi_refit_a", "Bii_refit_a", "Bi_refit_b_k0005", "Bi_refit_b_k002", "C_src_zone_speed_qr_groups_refit",
         "Biv_refit7_a"}
ONLINE_SETS = {"i": ("mvp_log", "qr_ogd"), "ii": ("Bii_mvp_log", "Bii_qr_ogd"), "iii": ("iii_mvp_log", "iii_qr_ogd"),
               "iv": ("iv_mvp_log", "iv_qr_ogd")}


def tag(b, t, s):
    return f"{b}_t{int(round(t * 1000)):04d}_s{s}"


def getter(pred, alias=None):
    """alias: display name -> cache label (new methods); other names are stored methods of `pred`."""
    alias = alias or {}
    st = S.stored_get(pred)

    def get(m, b, t, s):
        lab = alias.get(m, m)
        if lab in LABELS:
            D = pd.read_parquet(C.CACHE / "runs" / f"{tag(b, t, s)}__labels.parquet", columns=[f"hit|{lab}", f"cost|{lab}"])
        elif lab in LABELS_V:
            D = pd.read_parquet(C.CACHE / "runs" / f"{tag(b, t, s)}__labels_v.parquet", columns=[f"hit|{lab}", f"cost|{lab}"])
        elif lab in NEW_COLS or lab.startswith("C_") and lab not in REFIT:
            D = pd.read_parquet(C.CACHE / "runs" / f"{tag(b, t, s)}.parquet", columns=[f"hit|{lab}", f"cost|{lab}"])
        elif lab in REFIT:
            D = pd.read_parquet(C.CACHE / "runs" / f"{tag(b, t, s)}__{lab}.parquet")
        else:
            return st(lab, b, t, s)
        return D.iloc[:, 0].to_numpy(np.float64), D.iloc[:, 1].to_numpy(np.float64)
    return get


def spec(part, t):
    """(predictor, methods, alias, refs, seeds, blocks); comparison pairs of REVIEW_PLAN rev 3 'Comparison pairs'."""
    seeds, blocks = C.SEEDS, C.BLOCKS
    online = [m for v in ONLINE_SETS.values() for m in v]
    if part == "A":                 # new baselines vs QR family and online methods; stored main comparators listed
        return (C.PRIMARY, MAIN + ["A1_mondrian_small", "A2_aci_groups", "A3_qr_groups_inter"], {},
                ("qr_groups", "qr_groups_refit", "mvp_log", "qr_ogd"), seeds, blocks)
    if part == "B_aci":             # ACI variants vs the online methods of the same label set, all targets
        ms = ["aci_g0005", "Bi_aci", "Bii_aci", "iii_aci", "iv_aci", "iii_aci_groups", "iv_aci_groups", "A2_aci_groups"] + online
        return C.PRIMARY, ms, {}, tuple(online), seeds, blocks
    if part == "B_refit":           # online vs refit within the same label set, t = 0.95
        ms = ["qr_groups_refit", "Bi_refit_a", "Bii_refit_a"] + online
        return C.PRIMARY, ms, {}, ("qr_groups_refit", "Bi_refit_a", "Bii_refit_a"), seeds, blocks
    if part == "B_v":               # REVIEW_PLAN rev 5: label set (v) against full feedback and (iv); refit7 (iv) at 0.95
        ms = ["mvp_log", "qr_ogd", "A2_aci_groups", "iv_mvp_log", "iv_qr_ogd", "iv_aci_groups",
              "v_mvp_log", "v_qr_ogd", "v_aci_groups"]
        refs = ("mvp_log", "qr_ogd", "A2_aci_groups", "iv_mvp_log", "iv_qr_ogd", "iv_aci_groups")
        if abs(t - 0.95) < 1e-9 or abs(t - 0.93) < 1e-9 and all(
                (C.CACHE / "runs" / f"{tag(b, t, s)}__Biv_refit7_a.parquet").exists() for b in blocks for s in seeds):
            ms += ["qr_groups_refit", "qr_groups_refit7", "Bii_refit_a", "Biv_refit7_a"]
            refs += ("Bii_refit_a", "Biv_refit7_a")
        return C.PRIMARY, ms, {}, refs, seeds, blocks
    if part == "B_refit_b":         # left-censored QR trial: block1, seed 0
        ms = ["qr_groups_refit", "Bi_refit_a", "Bi_refit_b_k0005", "Bi_refit_b_k002", "mvp_log", "qr_ogd"]
        return C.PRIMARY, ms, {}, ("qr_groups_refit", "Bi_refit_a"), [0], ["block1"]
    if part.startswith("C_") and part != "C_refit":   # per predictor: group methods vs marginal methods
        p = part[2:]
        base = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "mvp_log", "qr_ogd"]
        alias = {m: f"C_{p}_{m}" for m in ("qr_groups", "mvp_log", "qr_ogd")} if p in ("src", "src_zone", "src_zone_hour") else {}
        refs = ("qr_groups", "mvp_log", "qr_ogd")
        if p == C.PRIMARY and abs(t - 0.95) < 1e-9:
            base.append("qr_groups_refit"); refs += ("qr_groups_refit",)
        return p, base, alias, refs, seeds, blocks
    if part == "C_refit":           # src_zone_speed with its refit, t = 0.95
        return ("src_zone_speed", ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "qr_groups_refit",
                                   "mvp_log", "qr_ogd"], {"qr_groups_refit": "C_src_zone_speed_qr_groups_refit"},
                ("qr_groups", "qr_groups_refit", "mvp_log", "qr_ogd"), seeds, blocks)
    raise SystemExit(part)


def run(part, t):
    pred, ms, alias, refs, seeds, blocks = spec(part, t)
    base = S.Base(blocks=blocks)
    e, d, c = S.summarize(base, pred, getter(pred, alias), ms, [t], seeds=seeds, refs=refs, label=part)
    out = C.OUT / "parts"; out.mkdir(parents=True, exist_ok=True)
    k = f"{part}_t{int(round(t * 1000)):04d}"
    e.to_csv(out / f"{k}_est.csv", index=False); d.to_csv(out / f"{k}_diff.csv", index=False)
    c.to_csv(out / f"{k}_cells.csv", index=False)


def collect():
    fs = sorted((C.OUT / "parts").glob("*_t*_*.csv"))
    groups = {}
    for f in fs:
        part, rest = f.stem.rsplit("_t", 1)
        kind = rest.split("_", 1)[1]
        groups.setdefault(("C" if part.startswith("C_") else part, kind), []).append(f)
    for (part, kind), L in groups.items():
        D = pd.concat([pd.read_csv(f) for f in L], ignore_index=True)
        if kind == "cells":
            D[D.family == "g25"].to_csv(C.OUT / f"{part}_groups.csv", index=False)
            D[D.family == "intersection"].to_csv(C.OUT / f"{part}_intersections.csv", index=False)
        else:
            D.to_csv(C.OUT / f"{part}_{'estimates' if kind == 'est' else 'differences'}.csv", index=False)
        print(part, kind, len(D))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part"); ap.add_argument("--target", type=float)
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args()
    if a.part:
        run(a.part, a.target)
    if a.collect:
        collect()


if __name__ == "__main__":
    main()
