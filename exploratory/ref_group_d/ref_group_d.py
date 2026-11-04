"""EXPLORATORY, POST HOC (instruction 13 §2(f); JD decision D14-1): per-group shortfall d of the hindsight references H1, H3
and H4 on the confirmation-2 evaluation hops, point estimates only (no intervals), for the reference rows of Table 3.

    python exploratory/ref_group_d/ref_group_d.py

Read only. The frozen code is imported, not changed (confirm2_analysis.py at 6758bce: HStruct, single_tau, CostLookup,
DIMS25, ATTRS). Thresholds as confirm2_analysis.py:458-469: per block, unit weights, H1 = HStruct.h1, H4 = HStruct.h4;
H3 = the cached full-sample fits work/h3_tau_check/tau3_BLOCK_tTTTT.npz (bitwise reproduction of the frozen H3 checked in
instruction 05, exploratory/h3_tau_check/reproduce_hindsight.csv). Point estimates as ref_point (confirm2_analysis.py:
507-512): per scope (block1, block2, combined = both blocks with their own thresholds) recall per group = hits / n,
d = t - recall, judged if n >= min_group_n.
Check before writing: for every scope, target and reference, recall_all, worst_deficit and worst_group equal the frozen
hindsight.csv (abs difference <= 1e-12, same group).
Outputs: exploratory/ref_group_d/ref_group_d.csv (scope, target, reference, group, n, judged, recall, d), check.csv,
manifest.csv.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import hashlib  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from confirm2_analysis import ANALYSIS, DIMS25, CostLookup, HStruct  # noqa: E402

RUNS = Path("results/porto_cctv_confirm2/runs")
HIND = Path("results/porto_cctv_confirm2/analysis/hindsight.csv")
CACHE = Path("work/h3_tau_check")
OUT = Path("exploratory/ref_group_d")
BLOCKS = ["block1", "block2"]


def main():
    A = yaml.safe_load(open(ANALYSIS)); pred = A["predictor"]
    blocks = []
    for b in BLOCKS:
        d = sorted(p for p in (RUNS / b).glob("t*/s*") if p.is_dir())[0]          # hops and scores equal in every run
        H0 = pd.read_parquet(d / "hits.parquet", columns=["tr_id"] + DIMS25 + [f"score|{pred}", f"kid|{pred}"])
        lk = CostLookup(d / f"cost_lookup_{pred}.npz", H0[f"kid|{pred}"].to_numpy())
        blocks.append({"name": b, "H0": H0, "score": H0[f"score|{pred}"].to_numpy(), "lk": lk})
    H = pd.concat([b["H0"] for b in blocks], ignore_index=True)
    cells = [(f"{d}={int(v)}", d, v) for d in DIMS25 for v in sorted(H[d].unique())]           # g25 order of the analysis
    hs, G = [], []
    for b in blocks:
        Gb = np.column_stack([b["H0"][d].to_numpy() == v for _, d, v in cells])
        dims_idx = []
        for d_ in DIMS25:
            cols = [k for k, (nm, dd, _) in enumerate(cells) if dd == d_]
            dims_idx.append(np.array(cols)[np.argmax(Gb[:, cols], 1)])
        hs.append(HStruct(b, Gb, dims_idx)); G.append(Gb)
    frozen = pd.read_csv(HIND)
    rows, chk = [], []
    for t in A["targets"]:
        thr = {"H1": [], "H3": [], "H4": []}
        for b, h in zip(blocks, hs):
            w1 = np.ones(len(b["H0"]))
            thr["H1"].append(np.full(len(w1), h.h1(w1, t)[0]))
            thr["H4"].append(h.h4(w1, t)[0])
            z = np.load(CACHE / f"tau3_{b['name']}_t{int(round(t * 1000)):04d}.npz")
            assert abs(float(z["target"]) - t) < 1e-9 and len(z["tau"]) == len(w1)
            thr["H3"].append(z["tau"])
        for sc, bl in (("combined", [0, 1]), ("block1", [0]), ("block2", [1])):
            cm = np.concatenate([G[i] for i in bl]).astype(np.float64); nG = cm.sum(0); jgm = nG >= A["min_group_n"]
            for ref, tb in thr.items():
                hits = np.concatenate([blocks[i]["score"] >= tb[i] for i in bl]).astype(float)
                rec = (cm.T @ hits) / nG
                dd = np.where(jgm, t - rec, -np.inf)
                f = frozen.query("scope == @sc and target == @t and reference == @ref").iloc[0]
                chk.append({"scope": sc, "target": t, "reference": ref, "recall_all": hits.mean(),
                            "recall_all_frozen": f.recall_all, "worst_deficit": float(dd.max()),
                            "worst_deficit_frozen": f.worst_deficit, "worst_group": cells[int(np.argmax(dd))][0],
                            "worst_group_frozen": f.worst_group})
                for k, (nm, _, _) in enumerate(cells):
                    rows.append({"scope": sc, "target": t, "reference": ref, "group": nm, "n": int(nG[k]),
                                 "judged": bool(jgm[k]), "recall": rec[k], "d": t - rec[k]})
    C = pd.DataFrame(chk)
    C["equal"] = ((C.recall_all - C.recall_all_frozen).abs() <= 1e-12) & \
                 ((C.worst_deficit - C.worst_deficit_frozen).abs() <= 1e-12) & (C.worst_group == C.worst_group_frozen)
    OUT.mkdir(parents=True, exist_ok=True)
    head = "# Post hoc analysis (after the confirm2 results were seen; exploratory, point estimates only, no intervals)\n"
    with open(OUT / "check.csv", "w") as fh:
        fh.write(head); C.to_csv(fh, index=False)
    assert C.equal.all(), C[~C.equal]
    D = pd.DataFrame(rows)
    with open(OUT / "ref_group_d.csv", "w") as fh:
        fh.write(head); D.to_csv(fh, index=False)
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "exploratory/ref_group_d/ref_group_d.py"],
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
    fs = ["ref_group_d.csv", "check.csv"]
    pd.DataFrame({"file": [str(OUT / x) for x in fs], "sha256": [hashlib.sha256((OUT / x).read_bytes()).hexdigest() for x in fs],
                  "script_commit": commit}).to_csv(OUT / "manifest.csv", index=False)
    print(f"check: {int(C.equal.sum())}/{len(C)} equal to hindsight.csv")
    P = D.query("scope == 'combined' and group in ['hopkind=2', 'nn_bin=3']").pivot_table(
        index=["reference", "group"], columns="target", values="d")
    print((100 * P).round(1).to_string())


if __name__ == "__main__":
    main()
