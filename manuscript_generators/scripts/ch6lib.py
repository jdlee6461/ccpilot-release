"""Shared definitions for the Chapter 6 tables and figures (scripts/make_tables.py, scripts/make_figures.py).

Instructions: notes/instructions/2026-09-30_ch6_figures_tables.md (ccpilot). Everything here is computed from
stored results (summary CSVs, hop-level hits.parquet); no new experiment is run.
"""
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))   # work copy outside ccpilot: CCPILOT_REPO=/home/user/ccpilot
PRED = "src_zone_hour_speed"
MIN_N = 200                     # groups with fewer hops are shown grey and excluded from judgements
BARS = (0.94, 0.95)
CONF = "results/porto_cctv_confirm"
PH = CONF + "_posthoc"

# ---------------------------------------------------------------- methods (one order for every table and figure)
# key: (label in tables/figures, column in hits.parquet or None, added after the main results)
METHODS = [
    ("static", "static", f"hit|{PRED}|static", False),
    ("aci", "ACI", f"hit|{PRED}|aci_g0005", False),
    ("mondrian", "Mondrian", f"hit|{PRED}|mondrian_hour_hop_speed", False),
    ("spatula", "Spatula-style", "hit|spatula_rule|fixed", False),
    ("citytrac095", "CityTrac-style (0.95)", "hit|citytrac_rule|target095", True),
    ("citytrac099", "CityTrac-style (0.99)", "hit|citytrac_rule|target099", True),
    ("qr_groups", "qr\\_groups", f"hit|{PRED}|qr_groups", False),
    ("mvp_groups", "mvp\\_groups", f"hit|{PRED}|mvp_groups", False),
    ("mvp_global", "mvp\\_global", f"hit|{PRED}|mvp_global", False),
    ("qr_ogd", "qr\\_ogd", f"hit|{PRED}|qr_ogd", False),
    ("mvp_log", "mvp\\_log", f"hit|{PRED}|mvp_log", False),
    ("oracle", "hindsight oracle", None, False),
]
MKEYS = [m[0] for m in METHODS]
MLABEL = {m[0]: m[1] for m in METHODS}
MCOL = {m[0]: m[2] for m in METHODS}
MLATE = {m[0]: m[3] for m in METHODS}


def tex_label(key):
    """Table label; CityTrac-style rows carry a dagger (added after the main results were known)."""
    return MLABEL[key] + ("$^\\dagger$" if MLATE[key] else "")


def plain_label(key):
    return MLABEL[key].replace("\\_", "_")


# Okabe-Ito palette; colour and marker differ per method so that figures survive greyscale printing.
OKABE = {"black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
         "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7"}
STYLE = {
    "static": (OKABE["orange"], "o"),
    "aci": (OKABE["sky"], "s"),
    "mondrian": (OKABE["purple"], "D"),
    "spatula": (OKABE["yellow"], "v"),
    "citytrac095": (OKABE["green"], "^"),
    "citytrac099": (OKABE["green"], "<"),
    "qr_groups": (OKABE["purple"], "P"),
    "mvp_groups": (OKABE["sky"], "X"),
    "mvp_global": (OKABE["yellow"], "h"),
    "qr_ogd": (OKABE["vermillion"], ">"),
    "mvp_log": (OKABE["blue"], "*"),
    "oracle": (OKABE["black"], "d"),
}

# ---------------------------------------------------------------- groups (pre-registered 25-group definition)
DIMS25 = ["grp_all", "hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin"]
DIM_NAME = {"grp_all": "All", "hgroup": "Time of day", "hopkind": "Track state", "speed_bin": "Exit speed",
            "zone": "Exit zone", "entropy_bin": "Branching", "nn_bin": "Isolation"}
# label of hopkind 2 in every generated table and figure (verdict 14 A2, request v06); the plan, the result files and the
# repository bundle (verbatim 7c55fbc) keep "re-acquisition" / "reacquired"
POSTGAP_LABEL = "post-gap"
POSTGAP_HEAD = POSTGAP_LABEL[0].upper() + POSTGAP_LABEL[1:]          # "Post-gap" at the start of a cell
LEVEL_NAME = {
    "grp_all": {0: "All hops"},
    "hgroup": {0: "00-06 h", 1: "06-10 h", 2: "10-16 h", 3: "16-20 h", 4: "20-24 h"},
    "hopkind": {0: "Later", 1: "Initiated", 2: POSTGAP_HEAD},
    "speed_bin": {0: "Speed Q1 (slow)", 1: "Speed Q2", 2: "Speed Q3", 3: "Speed Q4 (fast)"},
    "zone": {0: "Exit east", 1: "Exit north", 2: "Exit west", 3: "Exit south"},   # events.py: 0=E, 1=N, 2=W, 3=S
    "entropy_bin": {0: "Branching Q1 (low)", 1: "Branching Q2", 2: "Branching Q3", 3: "Branching Q4 (high)"},
    "nn_bin": {0: "Isolation Q1 (low)", 1: "Isolation Q2", 2: "Isolation Q3", 3: "Isolation Q4 (high)"},
}


def group_name(dim, g):
    return LEVEL_NAME[dim][int(g)]


def group_key(dim, g):
    return f"{dim}={int(g)}"


def wilson(k, n, z=1.96):
    """95% Wilson interval (same formula as ccpilot.evaluate._wilson_ub for the upper end)."""
    k = np.asarray(k, float); n = np.asarray(n, float)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def group_table(H, hitcol, seg_mask=None):
    """Recall per group of the 25-group definition. H must hold the group columns and hitcol."""
    m = np.ones(len(H), bool) if seg_mask is None else np.asarray(seg_mask)
    hit = H[hitcol].to_numpy()[m]
    rows = []
    for d in DIMS25:
        v = H[d].to_numpy()[m]
        for g in sorted(np.unique(v)):
            mm = v == g
            n = int(mm.sum()); k = int(hit[mm].sum())
            lo, hi = wilson(k, n)
            rows.append({"dim": d, "group": int(g), "key": group_key(d, g), "name": group_name(d, g),
                         "n": n, "hits": k, "recall": k / n, "lo95": float(lo), "ub95": float(hi), "judged": n >= MIN_N})
    return pd.DataFrame(rows)


def summarize(G):
    """Worst group and counts significantly below each bar, among groups with n >= MIN_N."""
    J = G[G.judged]
    w = J.loc[J.recall.idxmin()]
    out = {"worst_key": w.key, "worst_name": w["name"], "worst": w.recall, "worst_n": int(w.n),
           "worst_lo": w.lo95, "worst_ub": w.ub95, "n_groups_judged": len(J)}
    for b in BARS:
        out[f"below{int(round(b * 100))}"] = int((J.ub95 < b).sum())
    return out


# ---------------------------------------------------------------- provenance
def commit_of(path, repo=REPO):
    out = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(path)], cwd=repo, capture_output=True, text=True)
    return out.stdout.strip() or "untracked"


def write_csv(df, name, sources, kind, note=""):
    """generated/data/<name>.csv; first line: comment with sources (path @ ccpilot commit), class and notes."""
    assert kind in ("main", "additional", "exploratory"), kind
    src = "; ".join(f"{p} @ paper {commit_of(p[6:], PAPER)}" if str(p).startswith("paper/") else f"{p} @ {commit_of(p)}"
                    for p in sources)
    out = PAPER / "generated" / "data" / f"{name}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(f"# class: {kind} | source: {src}" + (f" | note: {note}" if note else "") + "\n")
        df.to_csv(fh, index=False, float_format="%.17g", lineterminator="\n")
    return out


def write_tex(body, name):
    out = PAPER / "generated" / "tables" / f"{name}.tex"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("% AUTO-GENERATED by scripts/make_tables.py -- DO NOT EDIT. Data: generated/data/"
                   f"{name}.csv\n" + body.rstrip() + "\n", encoding="utf-8")
    return out


def f3(x):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def f2(x):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"


def f1(x):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.1f}"


def fi(x):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{int(round(x)):d}"


# ---------------------------------------------------------------- held-out period, evaluation seed 0, no outage
HELD_HITS = PH + "/outage_suite/none_s7/hits.parquet"     # no-outage run; identical hits to the confirmation run
HELD_SUMMARY = CONF + "/summary.csv"                     # frozen confirmation summary (oracle cost)
SEGS = [("test_jun_a", "A"), ("test_jun_b", "B")]


def load_held():
    """Hop-level results of the held-out period, seed 0, with the hindsight-oracle hits reconstructed.

    none_s7 (posthoc_outage_suite.py, scenario 'none') stores every method incl. mvp_groups and the CityTrac-style
    rule, plus the per-hop score. Its hits equal the regrade hits of the confirmation run (all shared methods, all
    508,156 hops; checked in scripts/check_claims.py). Oracle: per segment, tau = conformal_tau(score, alpha) as in
    ccpilot.evaluate (no detection error, so observed = true score); its recall equals the frozen summary exactly.
    """
    import sys as _s
    _s.path.insert(0, str(REPO))
    from ccpilot.calibration import conformal_tau
    H = pd.read_parquet(REPO / HELD_HITS)
    H["seg"] = H["segment"].replace({"B_early": "test_jun_b", "B_late": "test_jun_b"})
    s = H[f"score|{PRED}"].to_numpy()
    hit = np.zeros(len(H), np.int8)
    for seg, _ in SEGS:
        m = (H.seg == seg).to_numpy()
        hit[m] = s[m] >= conformal_tau(s[m], 0.05)
    H["hit|oracle"] = hit
    return H


def held_oracle_cost():
    F = pd.read_csv(REPO / HELD_SUMMARY)
    F = F[(F.predictor == PRED) & (F.method == "oracle(post-hoc)")]
    return F.set_index("segment")["cost_mean_cam_s"].to_dict()


def hitcol(key):
    return "hit|oracle" if key == "oracle" else MCOL[key]


def costcol(key):
    return None if key == "oracle" else MCOL[key].replace("hit|", "cost|")
