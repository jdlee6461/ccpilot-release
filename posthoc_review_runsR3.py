"""POST HOC (external review, instruction 03 §1, REVIEW deviation R3): run table of the R3 reruns and refreshed manifest.

    python posthoc_review_runsR3.py

review/runs_R3.csv: the 50 label-set replay reruns (work/review_cache/labels_*.out) and the 7 re-aggregations
(work/review_cache/aggR3_*.out): wall seconds, maximum RSS, exit status, code commit at start, outputs with sha256, and
for the replays the sha256 of the superseded output (work/review_cache/runs_superseded/). review/runs_02.csv keeps the
original runs. review/manifest_cache.csv is rewritten as in posthoc_review_runs02.py (runs_superseded/ included).
"""
import pandas as pd

import posthoc_review_common as C
from posthoc_review_prereapproval import sha
from posthoc_review_runs02 import commit_at, parse_time, ts

LAB = C.CACHE / "runs"
SUP = C.CACHE / "runs_superseded"


def main():
    rows = []
    for f in sorted(C.CACHE.glob("labels_*.out")) + sorted(C.CACHE.glob("aggR3_*.out")):
        r = parse_time(f); a = r["command"].split(); start = r["end"] - r["seconds"]
        if f.name.startswith("labels_"):
            b, t, s = a[a.index("--run") + 1:][:3]; t = float(t)
            tag = f"{b}_t{int(round(t * 1000)):04d}_s{s}"
            out = LAB / f"{tag}__labels.parquet"; old = SUP / out.name
            row = {"kind": "replay (iii)/(iv)", "block": b, "target": t, "seed": s, "part": "",
                   "code_commit": commit_at("posthoc_review_labels.py", start), "output": str(out),
                   "output_sha256": sha(out), "superseded_sha256": sha(old)}
        else:
            part, t = a[a.index("--part") + 1], float(a[a.index("--target") + 1])
            k = f"{part}_t{int(round(t * 1000)):04d}"
            outs = [C.OUT / "parts" / f"{k}_{x}.csv" for x in ("est", "diff", "cells")]
            row = {"kind": "aggregate", "block": "both", "target": t, "seed": "0-4", "part": part,
                   "code_commit": commit_at("posthoc_review_report.py", start), "output": "; ".join(map(str, outs)),
                   "output_sha256": "; ".join(sha(o) for o in outs), "superseded_sha256": ""}
        row.update(seconds=r["seconds"], max_rss_gb=r["max_rss_gb"], exit_status=r["exit_status"], start=ts(start),
                   end=ts(r["end"]), log=str(f))
        rows.append(row)
    D = pd.DataFrame(rows)
    D.to_csv(C.OUT / "runs_R3.csv", index=False)
    print(D.groupby("kind").agg(n=("seconds", "size"), s_min=("seconds", "min"), s_max=("seconds", "max"),
                                rss=("max_rss_gb", "max"), exit_max=("exit_status", "max")).to_string())
    M = []
    for p in sorted(x for x in C.CACHE.rglob("*") if x.is_file()):
        n = p.name; d = p.parent.name
        gen = ("posthoc_review_p0.py" if d in C.BLOCKS else
               "posthoc_review_labels.py" if n.endswith("__labels.parquet") else
               "posthoc_review_methods.py" if d in ("runs", "runs_superseded") and "__" not in n and n.endswith(".parquet") else
               "posthoc_review_refit.py" if d == "runs" else None)
        M.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p), "mtime": ts(p.stat().st_mtime),
                  "generator": gen or "log / pid / helper",
                  "generating_commit": commit_at(gen, p.stat().st_mtime) if gen else ""})
    pd.DataFrame(M).to_csv(C.OUT / "manifest_cache.csv", index=False)
    print("manifest files:", len(M))


if __name__ == "__main__":
    main()
