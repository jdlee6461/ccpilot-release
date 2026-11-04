"""Write LOCK_confirm2.txt (plan notes/instructions/PLAN_confirm2.md §11.2) from the staged lock commit.

    git add <lock files>; python confirm2_lock.py; git add LOCK_confirm2.txt; git commit ...

Contents: sha256 of every staged file of the lock commit (except LOCK_confirm2.txt itself); the tree hash of the staged
index without LOCK_confirm2.txt (`git write-tree` with the lock file absent; reproduce at the tag with
`git rm --cached LOCK_confirm2.txt && git write-tree`) and the subtree hash of ccpilot/; the data hashes of
results/porto_cctv_confirm2/lock_data_hashes.json (raw CSV, preprocessed trip table, hop tables per block; content hash
method stated there); the push times of the earlier commits.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUSH = [("072ebfc", "2026-10-13T14:38:24-04:00", "precheck: confirm2 counts only"),
        ("dcc7f9f", "2026-10-13T16:27:52-04:00", "qr_groups_refit/refit7 definitions and implementation (before the trial run)"),
        ("b5e10e6", "2026-10-14T12:18:17-04:00", "detect_bins float64 comparison (output code only)"),
        ("ddae528", "2026-10-14T16:51:48-04:00", "rev 61 settings and sign convention (before the second trial runs)"),
        ("c2ad171", "2026-10-15T09:25:06-04:00", "rev 61 analysis, figures, macros"),
        ("94cf171", "2026-10-15T09:25:06-04:00", "rev 61 trial outputs")]


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def main():
    staged = sorted(f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if f != "LOCK_confirm2.txt")
    tracked = sorted(f for f in git("ls-files", "--cached").splitlines() if f != "LOCK_confirm2.txt")
    subprocess.run(["git", "rm", "-q", "--cached", "--ignore-unmatch", "LOCK_confirm2.txt"], cwd=ROOT, check=True)
    tree = git("write-tree")
    sub = git("write-tree", "--prefix=ccpilot/")
    head = git("rev-parse", "HEAD")
    data = json.load(open(ROOT / "results/porto_cctv_confirm2/lock_data_hashes.json"))
    plan_sha = sha("notes/instructions/PLAN_confirm2.md")
    assert plan_sha == "b23b9b748c54b6944f5ba9043119e6de8fe3af58e8a7a0a2ab825be9c7a0c4f7", plan_sha
    L = ["# LOCK_confirm2.txt -- confirmation experiment 2 lock (plan notes/instructions/PLAN_confirm2.md, rev 72, §11.2)",
         f"parent_commit: {head}",
         f"tree_without_lock_file: {tree}   (git rm --cached LOCK_confirm2.txt && git write-tree, at the tag)",
         f"tree_ccpilot_package: {sub}   (git write-tree --prefix=ccpilot/, same index)",
         f"plan_sha256: {plan_sha}", "",
         "## files of the lock commit (added or changed in it), sha256"]
    L += [f"{sha(f)}  {f}" for f in staged]
    L += ["", "## code and settings tracked at the lock (all tracked .py/.yaml/.yml/.sh/.json files), sha256"]
    L += [f"{sha(f)}  {f}" for f in tracked if f.endswith((".py", ".yaml", ".yml", ".sh")) or f == ".githooks/pre-commit"]
    L += ["", "## trial-run outputs (exploratory period 1) and confirm2 lock outputs tracked at the lock, sha256"]
    L += [f"{sha(f)}  {f}" for f in tracked if f.startswith(("results/precheck_confirm2/", "results/porto_cctv_confirm2/"))]
    L += ["", "## data (results/porto_cctv_confirm2/lock_data_hashes.json; content hash: " + data["hash_method"] + ")",
          f"raw_csv {data['raw_csv']['path']} sha256(file) {data['raw_csv']['sha256']}",
          f"trip_table (porto.load with drop_duplicate_trip_id: both) trips {data['trip_table']['trips']} points {data['trip_table']['points']} "
          f"sha256(content) {data['trip_table']['sha256']}",
          f"cameras sites {data['cameras']['sites']} sha256(content) {data['cameras']['sha256']}",
          f"hop_table_all (no visibility sets) rows {data['hop_table_all']['rows']} sha256(content) {data['hop_table_all']['sha256']}"]
    for k in ("hop_table_block1", "hop_table_block2"):
        d = data[k]
        L.append(f"{k} t_exit in [{d['range'][0]}, {d['range'][1]}) rows {d['rows']} sha256(content) {d['sha256']}")
    e = data["exclusion"]
    L += [f"duplicate TRIP_ID rule: trips {e['trips_without_rule']} -> {e['trips_with_rule']}, "
          f"transitions {e['transitions_without_rule']} -> {e['transitions_with_rule']} (results/porto_cctv_confirm2/lock_exclusions.csv)",
          "", "## push times (-04:00)"]
    L += [f"{c} {t} {d}" for c, t, d in PUSH]
    (ROOT / "LOCK_confirm2.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L[:8])); print(f"... {len(staged)} lock-commit files")


if __name__ == "__main__":
    main()
