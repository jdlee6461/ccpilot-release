"""EXPLORATORY, POST HOC (instruction 12 §5(q); verdict Shannon09 M4): shortfall on the intersections I1-I6 per method and
target, qr_groups alone against qr_groups with I1-I6 added as groups (A3_qr_groups_inter). Read only; no method is run.

    python exploratory/intersections_q/intersections_q.py

Inputs: results/porto_cctv_confirm2/analysis/intersections.csv (frozen analysis; the ten methods incl. qr_groups_refit7)
and results/porto_cctv_confirm2_posthoc/review/A_intersections.csv (REVIEW A, adds A3_qr_groups_inter and the two other
added baselines). Scope combined, primary predictor, seed mean, conservative 95% bounds (lo, hi) as stored.
Check: for the methods in both files, deficit equal (abs difference <= 1e-12).
Flags per (cell, target): qr_groups_le0 = deficit of qr_groups alone <= 0 (no shortfall to begin with);
A4 = hi <= 0.01 (the rule of review/aggregate/consequence_check.csv row A4 behind \\ctwoRevInterClosed).
Output: exploratory/intersections_q/intersections_q.csv (long) and intersections_q_wide.csv (pp, point [lo, hi]), manifest.
"""
import hashlib
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "exploratory/intersections_q"
F = pd.read_csv(ROOT / "results/porto_cctv_confirm2/analysis/intersections.csv").query("scope == 'combined'")
A = pd.read_csv(ROOT / "results/porto_cctv_confirm2_posthoc/review/A_intersections.csv", comment="#").query("scope == 'combined'")
KEY = ["target", "method", "cell"]
both = F.merge(A, on=KEY, suffixes=("_f", "_a"))
assert len(both) > 0 and (both.deficit_f - both.deficit_a).abs().max() <= 1e-12, (both.deficit_f - both.deficit_a).abs().max()
D = pd.concat([F[KEY + ["n", "deficit", "lo", "hi"]],
               A[~A.method.isin(F.method.unique())][KEY + ["n", "deficit", "lo", "hi"]]], ignore_index=True)
METHODS = ["static", "aci_g0005", "mondrian_hour_hop_speed", "qr_groups", "A3_qr_groups_inter", "qr_groups_refit",
           "qr_groups_refit7", "qr_ogd", "mvp_log", "A1_mondrian_small", "A2_aci_groups"]
D = D[D.method.isin(METHODS)].copy()
qg = D[D.method == "qr_groups"].set_index(["target", "cell"]).deficit
D["qr_groups_le0"] = [qg[(t, c)] <= 0 for t, c in zip(D.target, D.cell)]
D["A4_hi_le_001"] = D.hi <= 0.01
D["method"] = pd.Categorical(D.method, METHODS, ordered=True)
D = D.sort_values(["cell", "target", "method"])
HEADER = "# Post hoc analysis (after the confirm2 results were seen; exploratory, reads stored results only)\n"
with open(OUT / "intersections_q.csv", "w") as f:
    f.write(HEADER); D.to_csv(f, index=False)
W = D.assign(txt=[f"{100 * d:.1f} [{100 * l:.1f}, {100 * h:.1f}]" for d, l, h in zip(D.deficit, D.lo, D.hi)])
W = W.pivot_table(index=["cell", "target"], columns="method", values="txt", aggfunc="first", observed=True)
with open(OUT / "intersections_q_wide.csv", "w") as f:
    f.write(HEADER); W.to_csv(f)
commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "exploratory/intersections_q/intersections_q.py"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip() or "uncommitted"
fs = ["intersections_q.csv", "intersections_q_wide.csv"]
pd.DataFrame({"file": [f"exploratory/intersections_q/{x}" for x in fs],
              "sha256": [hashlib.sha256((OUT / x).read_bytes()).hexdigest() for x in fs], "script_commit": commit}
             ).to_csv(OUT / "manifest.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 20)
print(W[["static", "qr_groups", "A3_qr_groups_inter", "qr_groups_refit", "mvp_log", "qr_ogd"]].to_string())
print(D[D.method == "qr_groups"].pivot(index="cell", columns="target", values="qr_groups_le0").to_string())
print(D[D.method == "A3_qr_groups_inter"].pivot(index="cell", columns="target", values="A4_hi_le_001").to_string())
print("rows compared with the frozen file:", len(both))
