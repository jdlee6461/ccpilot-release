"""EXPLORATORY, POST HOC (instruction 12 §5(r); verdict Shannon09 M6): worst group per method under feedback label set (iv)
(labels only from successful searches and a 5% audit), with full feedback for comparison. Read only; no method is run.

    python exploratory/feedback_iv_worst/feedback_iv_worst.py

Inputs: results/porto_cctv_confirm2_posthoc/review/B_aci_groups.csv (ACI, group-wise ACI, mvp_log, qr_ogd; five targets)
and B_refit_groups.csv (refit; targets 0.93, 0.95), with B_*_estimates.csv for D (estimand D, seed mean of the per-seed
worst-group shortfall). Scope combined, primary predictor, the 25 groups (family g25, judged rows).
Per (method, target): the group with the largest seed-mean deficit (argmax), its deficit [lo, hi], the second group, and
D of the estimates file. Since D is the mean over seeds of each seed's maximum, it can exceed the argmax deficit.
The (iv) refit is Bii_refit_a ('(iv) refit = (ii) refit by construction', posthoc_review_tables.py SETS).
Output: exploratory/feedback_iv_worst/feedback_iv_worst.csv, manifest.csv.
"""
import hashlib
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "results/porto_cctv_confirm2_posthoc/review"
OUT = ROOT / "exploratory/feedback_iv_worst"
SETS = {"full": {"ACI": "aci_g0005", "group-wise ACI": "A2_aci_groups", "mvp_log": "mvp_log", "qr_ogd": "qr_ogd",
                 "refit": "qr_groups_refit"},
        "(iv)": {"ACI": "iv_aci", "group-wise ACI": "iv_aci_groups", "mvp_log": "iv_mvp_log", "qr_ogd": "iv_qr_ogd",
                 "refit": "Bii_refit_a"}}
G = pd.concat([pd.read_csv(R / f"{x}_groups.csv", comment="#") for x in ("B_aci", "B_refit")])
E = pd.concat([pd.read_csv(R / f"{x}_estimates.csv", comment="#") for x in ("B_aci", "B_refit")])
G = G.query("scope == 'combined' and judged").drop_duplicates(["method", "target", "cell"])
E = E.query("scope == 'combined' and estimand == 'D'").drop_duplicates(["method", "target"]).set_index(["method", "target"])
rows = []
for st, ms in SETS.items():
    for disp, m in ms.items():
        for t, g in G[G.method == m].groupby("target"):
            assert g.family.eq("g25").all() if "family" in g else True
            g = g.sort_values("deficit", ascending=False)
            a, b = g.iloc[0], g.iloc[1]
            rows.append({"label_set": st, "method": disp, "run_name": m, "target": t, "n_groups": len(g),
                         "worst_group": a.cell, "worst_deficit": a.deficit, "worst_lo": a.lo, "worst_hi": a.hi,
                         "second_group": b.cell, "second_deficit": b.deficit,
                         "reacq_deficit": g.set_index("cell").deficit.get("hopkind=2"),
                         "D_estimates": E.point.get((m, t))})
D = pd.DataFrame(rows)
with open(OUT / "feedback_iv_worst.csv", "w") as f:
    f.write("# Post hoc analysis (after the confirm2 results were seen; exploratory, reads stored results only)\n"); D.to_csv(f, index=False)
commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "exploratory/feedback_iv_worst/feedback_iv_worst.py"],
                        cwd=ROOT, capture_output=True, text=True).stdout.strip() or "uncommitted"
pd.DataFrame({"file": ["exploratory/feedback_iv_worst/feedback_iv_worst.csv"],
              "sha256": [hashlib.sha256((OUT / "feedback_iv_worst.csv").read_bytes()).hexdigest()],
              "script_commit": commit}).to_csv(OUT / "manifest.csv", index=False)
pd.set_option("display.width", 250)
print(D.round(4).to_string(index=False))
