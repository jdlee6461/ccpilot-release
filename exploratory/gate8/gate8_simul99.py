"""EXPLORATORY, POST HOC (instruction 18 §2(a); verdict 21 A (f)): group-wise ACI against qr_groups_refit and
qr_groups_refit7, worst-group shortfall D and post-gap shortfall d, classified with the 99% intervals of the plan's main
comparisons (plan §5.2/§5.5: B = 10,000, 99% per target = Bonferroni over the five targets, taxi and day clusters,
conservative bound at each end) next to the 95% intervals (B = 2,000) used in the review.
Bootstrap only: stored per-hop hits are re-weighted; no method is run.

    python exploratory/gate8/gate8_simul99.py

Hits: group-wise ACI = work/review_cache/runs/<tag>.parquet hit|A2_aci_groups (REVIEW part A); refit, refit7 = stored
confirm2 hits (primary predictor). Weights: posthoc_review_summary.Base draws (bootstrap seed 20261013; the B = 10,000
main draws first, as confirm2_analysis.py, then the B = 2,000 draws); the B = 10,000 draws are regenerated here in the
same order. Delta = D(group-wise ACI) - D(refit variant) per seed, then mean over seeds (as the review differences;
negative = group-wise ACI smaller). Check: the 95% bounds against refit equal review/A_differences.csv.
Output: exploratory/gate8/simul99.csv, manifest_simul99.csv.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import os  # noqa: E402
os.chdir(ROOT)
import posthoc_review_common as C  # noqa: E402
import posthoc_review_summary as S  # noqa: E402
from confirm2_analysis import pct  # noqa: E402

OUT = ROOT / "exploratory/gate8"
TARGETS = [0.90, 0.93, 0.95, 0.97, 0.98]
REF = "A2_aci_groups"
COMPS = ["qr_groups_refit", "qr_groups_refit7"]
HEADER = "# Post hoc analysis (after the confirm2 results were seen; exploratory, bootstrap re-aggregation of stored hits only; instruction 18 §2(a))\n"


def main_weights(base):
    """the B = 10,000 draws of Base (same generator state: they are the first draws after default_rng(BOOT_SEED))."""
    rng = np.random.default_rng(S.BOOT_SEED)
    day_block = np.zeros(base.codes["day"].max() + 1, int); day_block[base.codes["day"]] = base.bid
    W = {}
    for c in base.codes:
        Cn = base.codes[c].max() + 1
        if c == "taxi":
            W[c] = rng.multinomial(Cn, np.full(Cn, 1 / Cn), size=S.B_MAIN).astype(np.float64)
        else:
            w = np.zeros((S.B_MAIN, Cn))
            for bi in range(len(base.blocks)):
                idx = np.flatnonzero(day_block == bi)
                w[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=S.B_MAIN)
            W[c] = w
    return W


def hits(m, b, t, s):
    tag = f"{b}_t{int(round(t * 1000)):04d}_s{s}"
    if m == REF:
        return pd.read_parquet(C.CACHE / "runs" / f"{tag}.parquet", columns=[f"hit|{m}"]).iloc[:, 0].to_numpy(float)
    return C.load_hits(b, t, s, columns=[f"hit|{C.PRIMARY}|{m}"]).iloc[:, 0].to_numpy(float)


def boot(base, H, W, t, jg):
    """per cluster type: bootstrap D and post-gap d, arrays (B, M, S)."""
    out = {}
    for c, Wc in W.items():
        cc = base.codes[c]; Cn = cc.max() + 1
        Nc = np.zeros((Cn, base.CM.shape[1])); np.add.at(Nc, cc, base.CM)
        Kc = np.zeros((Cn, base.CM.shape[1]) + H.shape[1:])
        for ci in range(base.CM.shape[1]):
            sel = base.CM[:, ci] > 0
            np.add.at(Kc[:, ci], cc[sel], H[sel])
        res = {"D": [], "reacq_d": []}
        for b0 in range(0, len(Wc), 1000):
            w = Wc[b0:b0 + 1000]
            db = t - np.einsum("bc,cgms->bgms", w, Kc) / (w @ Nc)[:, :, None, None]
            res["D"].append(db[:, jg].max(1)); res["reacq_d"].append(db[:, base.reacq])
        out[c] = {k: np.concatenate(v) for k, v in res.items()}
    return out


def main():
    base = S.Base()
    W95, W99 = base.W, main_weights(base)
    nC = base.CM.sum(0); jg = np.flatnonzero((nC >= S.MIN_N)[:base.n25])
    M = [REF] + COMPS
    rows = []
    for t in TARGETS:
        H = np.zeros((len(base.bid), len(M), len(C.SEEDS)))
        for mi, m in enumerate(M):
            for si, s in enumerate(C.SEEDS):
                for i, b in enumerate(base.blocks):
                    H[base.off[i]:base.off[i + 1], mi, si] = hits(m, b, t, s)
        rec = np.einsum("nc,nms->cms", base.CM, H) / nC[:, None, None]
        d = t - rec
        pts = {"D": d[jg].max(0), "reacq_d": d[base.reacq]}
        bs = {"95": boot(base, H, W95, t, jg), "99": boot(base, H, W99, t, jg)}
        for ci, cm in enumerate(COMPS, start=1):
            for k in ("D", "reacq_d"):
                dseed = pts[k][0] - pts[k][ci]
                r = {"target": t, "reference": cm, "comparator": REF, "estimand": f"{k}_diff", "point": dseed.mean(),
                     "seeds_negative": int((dseed < 0).sum()), "seeds_positive": int((dseed > 0).sum())}
                for lv, L in (("95", 0.95), ("99", 0.99)):
                    for c in ("taxi", "day"):
                        lo, hi = pct((bs[lv][c][k][:, 0] - bs[lv][c][k][:, ci]).mean(-1), L)
                        r[f"lo{lv}_{c}"], r[f"hi{lv}_{c}"] = float(lo), float(hi)
                    r[f"lo{lv}"] = min(r[f"lo{lv}_taxi"], r[f"lo{lv}_day"]); r[f"hi{lv}"] = max(r[f"hi{lv}_taxi"], r[f"hi{lv}_day"])
                    r[f"class{lv}"] = ("group-wise ACI smaller" if r[f"hi{lv}"] < 0 else
                                       "refit variant smaller" if r[f"lo{lv}"] > 0 else "undetermined")
                r["B95"], r["B99"] = S.B_OTHER, S.B_MAIN
                rows.append(r)
        print("[simul99] t", t, "done", flush=True)
    R = pd.DataFrame(rows)
    A = pd.read_csv(C.OUT / "A_differences.csv", comment="#").query(
        "scope == 'combined' and reference == 'qr_groups_refit' and comparator == 'A2_aci_groups'")
    A = A.set_index(["target", "estimand"])
    chk = R[R.reference == "qr_groups_refit"].copy()
    key = {"D_diff": "D_diff", "reacq_d_diff": "reacq_d_diff"}
    chk["review_lo"] = [A.loc[(t, key[e]), "lo"] for t, e in zip(chk.target, chk.estimand)]
    chk["review_hi"] = [A.loc[(t, key[e]), "hi"] for t, e in zip(chk.target, chk.estimand)]
    chk["review_point"] = [A.loc[(t, key[e]), "point"] for t, e in zip(chk.target, chk.estimand)]
    R["check_95_equals_review"] = pd.Series([None] * len(R), dtype=object)
    ok = ((chk.lo95 - chk.review_lo).abs() < 1e-12) & ((chk.hi95 - chk.review_hi).abs() < 1e-12) & \
         ((chk.point - chk.review_point).abs() < 1e-12)
    R.loc[chk.index, "check_95_equals_review"] = ok.values
    with open(OUT / "simul99.csv", "w") as f:
        f.write(HEADER); R.to_csv(f, index=False)
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "exploratory/gate8/gate8_simul99.py"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
    pd.DataFrame({"file": ["exploratory/gate8/simul99.csv"],
                  "sha256": [hashlib.sha256((OUT / "simul99.csv").read_bytes()).hexdigest()],
                  "script_commit": commit}).to_csv(OUT / "manifest_simul99.csv", index=False)
    print("95% check against review/A_differences.csv:", bool(ok.all()))


if __name__ == "__main__":
    main()
