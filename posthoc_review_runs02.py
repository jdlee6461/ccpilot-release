"""POST HOC (external review, instruction 02 v02 §8): per-run table of the §6-§7 runs and the refreshed cache manifest.

    python posthoc_review_runs02.py

Reads the /usr/bin/time -v logs in work/review_cache/ (labels_*, checka2_*, methods_* with a time block, refit_*,
refit93_*, agg_*) and writes review/runs_02.csv: one row per run with block, target, seed, method set, variant, wall
seconds, maximum RSS, exit status, start/end, the commit holding the generator script at start, and the output files
with sha256. Rewrites review/manifest_cache.csv (every file under work/review_cache/: path, bytes, sha256, mtime,
generator, generating commit = last commit of the generator script at or before the file's mtime).
Per-hop values are not read; files are hashed as bytes only.
"""
import re
import subprocess
from datetime import datetime, timezone

import pandas as pd

import posthoc_review_common as C
from posthoc_review_prereapproval import sha

GEN = {"labels": "posthoc_review_labels.py", "checka2": "posthoc_review_labels.py", "methods": "posthoc_review_methods.py",
       "refit": "posthoc_review_refit.py", "refit93": "posthoc_review_refit.py", "agg": "posthoc_review_report.py",
       "agg93": "posthoc_review_report.py"}
STEP = {"labels": "6.2", "checka2": "6.2 (A2 copy check)", "methods": "6.1", "refit": "6.3/6.4", "refit93": "6.3 (0.93)",
        "agg": "7", "agg93": "7 (0.93)"}
LABEL_SETS = "iii_/iv_ {aci, aci_groups, mvp_log, qr_ogd}"
METHODS = ("A1_mondrian_small, A2_aci_groups, A3_qr_groups_inter, Bi_aci, Bii_aci, Bii_mvp_log, Bii_qr_ogd, "
           "C_{src,src_zone,src_zone_hour}_{qr_groups,mvp_log,qr_ogd}")


def ts(x):
    return datetime.fromtimestamp(x, timezone.utc).astimezone().isoformat(timespec="seconds")


DEPS = {"posthoc_review_report.py": ["posthoc_review_report.py", "posthoc_review_summary.py", "posthoc_review_common.py"],
        "posthoc_review_labels.py": ["posthoc_review_labels.py", "posthoc_review_methods.py", "posthoc_review_common.py"],
        "posthoc_review_refit.py": ["posthoc_review_refit.py", "posthoc_review_methods.py", "posthoc_review_common.py"]}


def commits(path):
    """commits touching the generator script or a review module it imports, newest first"""
    out = subprocess.run(["git", "log", "--format=%h %ct", "--", *DEPS.get(path, [path, "posthoc_review_common.py"])],
                         capture_output=True, text=True).stdout.split("\n")
    return [(h, float(t)) for h, t in (ln.split() for ln in out if ln)]


def commit_at(path, t):
    c = [h for h, ct in commits(path) if ct <= t]
    return c[0] if c else "before first commit (" + commits(path)[-1][0] + ")"


def parse_time(f):
    txt = open(f, errors="replace").read()
    if "Command being timed" not in txt:
        return None
    g = lambda k: re.search(rf"{k}: (.*)", txt).group(1).strip()
    el = g(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\)").split(":")
    sec = sum(float(x) * 60 ** i for i, x in enumerate(reversed(el)))
    return {"command": g("Command being timed").strip('"'), "seconds": round(sec, 2),
            "max_rss_gb": round(int(g(r"Maximum resident set size \(kbytes\)")) / 1024 ** 2, 3),
            "exit_status": int(g("Exit status")), "end": f.stat().st_mtime}


def main():
    rows = []
    for f in sorted(C.CACHE.glob("*.out")):
        kind = f.name.split("_", 1)[0]
        if kind not in GEN:
            continue
        r = parse_time(f)
        if r is None:                       # methods_* logs of the pre-re-approval runs (R1) carry no time block
            continue
        a = r["command"].split()
        if kind in ("labels", "checka2", "methods"):
            b, t, s = a[a.index("--run" if "--run" in a else "--check-a2") + 1:][:3]
            t, s = float(t), int(s); tag = f"{b}_t{int(round(t * 1000)):04d}_s{s}"
            ms, var = ({"labels": (LABEL_SETS, "label sets (iii), (iv)"), "checka2": ("A2_aci_groups", "full-label copy check"),
                        "methods": (METHODS, "cancelled runs of 2026-10-19")}[kind])
            outs = {"labels": [f"runs/{tag}__labels.parquet"], "checka2": [], "methods": [f"runs/{tag}.parquet"]}[kind]
        elif kind in ("refit", "refit93"):
            lab, b, s = a[a.index("--job") + 1:][:3]; s = int(s)
            t = float(a[a.index("--target") + 1]) if "--target" in a else 0.95
            tag = f"{b}_t{int(round(t * 1000)):04d}_s{s}"; ms = lab
            var = {"Bi_refit_a": "(i)(a)", "Bii_refit_a": "(ii)(a)", "Bi_refit_b_k002": "(i)(b) kappa 0.02",
                   "C_src_zone_speed_qr_groups_refit": "src_zone_speed, full feedback"}.get(lab, lab)
            outs = [f"runs/{tag}__{lab}.parquet"]
        else:
            part, t = a[a.index("--part") + 1], float(a[a.index("--target") + 1])
            b, s, ms, var = "both" if part != "B_refit_b" else "block1", "0-4" if part != "B_refit_b" else "0", part, "aggregate"
            k = f"{part}_t{int(round(t * 1000)):04d}"
            outs = [C.OUT / "parts" / f"{k}_{x}.csv" for x in ("est", "diff", "cells")]
        start = r["end"] - r["seconds"]
        ofs = [o if kind.startswith("agg") else C.CACHE / o for o in outs]
        rows.append({"step": STEP[kind], "block": b, "target": t, "seed": s, "methods": ms, "variant": var,
                     "seconds": r["seconds"], "max_rss_gb": r["max_rss_gb"], "exit_status": r["exit_status"],
                     "start": ts(start), "end": ts(r["end"]), "code_commit": commit_at(GEN[kind], start),
                     "log": str(f),
                     "output": "; ".join(str(o) for o in ofs),
                     "output_sha256": "; ".join(sha(o) for o in ofs)})
    D = pd.DataFrame(rows).sort_values(["step", "block", "target", "seed", "methods"], key=lambda x: x.astype(str))
    D.to_csv(C.OUT / "runs_02.csv", index=False)
    print(D.groupby("step").agg(n=("seconds", "size"), s_min=("seconds", "min"), s_max=("seconds", "max"),
                                rss_max=("max_rss_gb", "max"), exit_max=("exit_status", "max")).to_string())
    M = []
    for p in sorted(x for x in C.CACHE.rglob("*") if x.is_file()):
        n = p.name
        gen = ("posthoc_review_p0.py" if p.parent.name in C.BLOCKS else
               "posthoc_review_labels.py" if n.endswith("__labels.parquet") else
               "posthoc_review_methods.py" if p.parent.name == "runs" and "__" not in n else
               "posthoc_review_refit.py" if p.parent.name == "runs" else None)
        M.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p),
                  "mtime": ts(p.stat().st_mtime), "generator": gen or "log / pid / helper",
                  "generating_commit": commit_at(gen, p.stat().st_mtime) if gen else ""})
    pd.DataFrame(M).to_csv(C.OUT / "manifest_cache.csv", index=False)
    print("manifest files:", len(M))


if __name__ == "__main__":
    main()
