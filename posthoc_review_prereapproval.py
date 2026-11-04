"""POST HOC (external review, instruction 01 v02 §4): inventory of the runs made before the re-approval (REVIEW deviation R1).

    python posthoc_review_prereapproval.py

Writes review/pre_reapproval_runs.csv (one row per run: id, block, target, seed, methods, sha256 of the stored
run_config.yaml used as input, code commit, start/end time, match with conditions 1-3 of REVIEW_PLAN revision 2) and
review/manifest_cache.csv (every file under work/review_cache/: path, bytes, sha256, generating commit).
Per-hop hit/cost values are not read: files are hashed as bytes only; the timing json files hold run times and the
internal copy checks (booleans).
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import posthoc_review_common as C

CODE = "f8b9bc5"            # commit holding posthoc_review_{common,methods,refit,summary}.py at run time (unchanged since)
PLAN_REV2 = "1f74a93"
COND = {   # condition of REVIEW_PLAN rev 2 -> code location (file:line) implementing it
    1: "posthoc_review_methods.py:101 (taus[i] = tau_g[gl[i]].min(): smallest tau_G over the hop's groups)",
    2: "posthoc_review_methods.py:166-170 (audit = second draw of default_rng(seed) < 0.05), :234 (fb2 = fb | audit), "
       ":235 Bii_aci (events fb2, scores revealed for audit), :238 Bii_mvp_log (fb2), :240 Bii_qr_ogd (fb2)",
    3: "posthoc_review_refit.py:82-84, :129-131 (CH three-step, kappa from label k0005 = 0.005 / k002 = 0.02, delta 0)",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ts(x):
    return datetime.fromtimestamp(x, timezone.utc).astimezone().isoformat(timespec="seconds")


def commit_time(c):
    return float(subprocess.run(["git", "log", "-1", "--format=%ct", c], capture_output=True, text=True).stdout)


def main():
    t_code, t_plan = commit_time(CODE), commit_time(PLAN_REV2)
    rows = []
    for f in sorted((C.OUT / "timing").glob("methods_*.json")):
        info = json.load(open(f)); tag = f.stem.split("_", 1)[1].rsplit("_", 1)[0]
        b, tt, s = tag.split("_"); t = int(tt[1:]) / 1000; s = int(s[1:])
        out = C.CACHE / "runs" / f"{tag}.parquet"
        end = f.stat().st_mtime; start = end - info["seconds_total"]
        rows.append({"run_id": f"methods:{tag}", "block": b, "target": t, "seed": s,
                     "methods": "A1_mondrian_small, A2_aci_groups, A3_qr_groups_inter, Bi_aci, Bii_aci, Bii_mvp_log, "
                                "Bii_qr_ogd, C_{src,src_zone,src_zone_hour}_{qr_groups,mvp_log,qr_ogd}",
                     "config_sha256": sha(C.run_dir(b, t, s) / "run_config.yaml"), "code_commit": CODE,
                     "start": ts(start), "end": ts(end), "after_plan_rev2": start > t_plan, "after_code": start > t_code,
                     "cond1_A2_min_tau": "yes", "cond2_Bii_same_feedback": "yes", "cond3_b_kappa": "n/a",
                     "internal_checks": "; ".join(f"{k}={v}" for k, v in info.items() if "bitwise" in k),
                     "output": str(out), "output_sha256": sha(out)})
    for f in sorted((C.OUT / "timing").glob("refit_*.json")):
        info = json.load(open(f)); tag, lab = f.stem.split("_", 1)[1].split("__")
        b, tt, s = tag.split("_"); t = int(tt[1:]) / 1000; s = int(s[1:])
        out = C.CACHE / "runs" / f"{tag}__{lab}.parquet"
        end = f.stat().st_mtime; start = end - info["seconds"]
        rows.append({"run_id": f"refit:{tag}:{lab}", "block": b, "target": t, "seed": s, "methods": lab,
                     "config_sha256": sha(C.run_dir(b, t, s) / "run_config.yaml"), "code_commit": CODE,
                     "start": ts(start), "end": ts(end), "after_plan_rev2": start > t_plan, "after_code": start > t_code,
                     "cond1_A2_min_tau": "n/a", "cond2_Bii_same_feedback": "n/a",
                     "cond3_b_kappa": (f"yes (kappa {info.get('kappa')}, delta {info.get('delta')}; kappa 0.02 not run)"
                                       if lab.startswith("Bi_refit_b") else "n/a"),
                     "internal_checks": "; ".join(f"{k}={v}" for k, v in info.items() if "bitwise" in k),
                     "output": str(out), "output_sha256": sha(out)})
    val = C.CACHE / "val_summary.out"
    tot = float([ln.split()[1] for ln in open(val) if ln.startswith("total")][0])      # "total <seconds>" line
    v_end = val.stat().st_mtime; v_start = v_end - tot
    rows.append({"run_id": "summary_validation:t0950", "block": "both", "target": 0.95, "seed": "0-4",
                 "methods": "stored static, mvp_log, qr_ogd (primary predictor)", "config_sha256": "",
                 "code_commit": CODE, "start": ts(v_start), "end": ts(v_end), "after_plan_rev2": v_start > t_plan,
                 "after_code": v_start > t_code, "cond1_A2_min_tau": "n/a", "cond2_Bii_same_feedback": "n/a", "cond3_b_kappa": "n/a",
                 "internal_checks": "compared with results/porto_cctv_confirm2/analysis csv (cells, WORST, H2 ratio)",
                 "output": "work/review_cache/val_est.csv, val_cells.csv", "output_sha256": ""})
    D = pd.DataFrame(rows)
    D.to_csv(C.OUT / "pre_reapproval_runs.csv", index=False)
    print(D.groupby(D.run_id.str.split(":").str[0]).size().to_string())
    print("all after plan rev2:", bool(D.after_plan_rev2.all()), "| all after code commit:", bool(D.after_code.all()))
    M = []
    for p in sorted(x for x in C.CACHE.rglob("*") if x.is_file()):
        gen = ("posthoc_review_p0.py --scores" if p.parent.name in C.BLOCKS else
               "posthoc_review_methods.py --run" if p.parent.name == "runs" and "__" not in p.name else
               "posthoc_review_refit.py --job" if p.parent.name == "runs" else "log / pid / helper")
        M.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p), "mtime": ts(p.stat().st_mtime),
                  "generator": gen, "generating_commit": CODE})
    pd.DataFrame(M).to_csv(C.OUT / "manifest_cache.csv", index=False)
    print("manifest files:", len(M))
    for k, v in COND.items():
        print(f"condition {k}: {v}")


if __name__ == "__main__":
    main()
