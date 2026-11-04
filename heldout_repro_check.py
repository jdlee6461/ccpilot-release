"""Reproduction check of the held-out re-analysis (plan notes/instructions/PLAN_confirm2.md §12).

    python heldout_repro_check.py

Target 0.95, evaluation seeds 0-4: every (predictor, method, segment) row of the re-analysis run summary
(results/porto_cctv_heldout_reanalysis/runs/t0950/s<k>/summary.csv) that also exists in the existing held-out seed
repetition (results/porto_cctv_confirm_posthoc/seeds_prereg25/seed_<k>/summary.csv) is compared column by column, and the
per-hop outcomes (hits.parquet, columns present in both) are compared when both files exist locally.
Writes results/porto_cctv_heldout_reanalysis/repro_t0950.csv (one row per seed, predictor, method, segment, column:
old, new, abs difference) and repro_t0950_hits.csv; prints a summary. Rows only in the re-analysis (new comparators)
are listed as such.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
NEW = ROOT / "results/porto_cctv_heldout_reanalysis/runs/t0950"
OLD = ROOT / "results/porto_cctv_confirm_posthoc/seeds_prereg25"
OUT = ROOT / "results/porto_cctv_heldout_reanalysis"
KEY = ["predictor", "method", "segment"]
COLS = ["n", "coverage", "coverage_detected", "target_used", "worst_group_cov", "worst_group", "worst_group_n",
        "worst_group_ub95", "n_groups_sig_below_bar", "cost_mean_cam_s", "cost_median_cam_s", "roll_p05", "frac_below"]


def main():
    rows, only_new, hrows = [], set(), []
    for k in range(5):
        a = pd.read_csv(OLD / f"seed_{k}" / "summary.csv").set_index(KEY)
        b = pd.read_csv(NEW / f"s{k}" / "summary.csv").set_index(KEY)
        only_new |= set(b.index.difference(a.index))
        for idx in a.index.intersection(b.index):
            for c in COLS:
                if c not in a.columns or c not in b.columns:
                    continue
                o, n = a.at[idx, c], b.at[idx, c]
                if isinstance(o, str) or isinstance(n, str):
                    diff = 0.0 if o == n else np.nan
                else:
                    diff = 0.0 if (pd.isna(o) and pd.isna(n)) else abs(float(o) - float(n))
                rows.append(dict(seed=k, predictor=idx[0], method=idx[1], segment=idx[2], column=c, old=o, new=n,
                                 abs_diff=diff))
        ho, hn = OLD / f"seed_{k}" / "hits.parquet", NEW / f"s{k}" / "hits.parquet"
        if ho.exists() and hn.exists():
            HO, HN = pd.read_parquet(ho), pd.read_parquet(hn)
            common = [c for c in HO.columns if c in HN.columns]
            same_len = len(HO) == len(HN)
            for c in common:
                eq = same_len and (HO[c].to_numpy() == HN[c].to_numpy()).all() if same_len else False
                hrows.append(dict(seed=k, column=c, rows_old=len(HO), rows_new=len(HN), identical=bool(eq)))
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "repro_t0950.csv", index=False)
    H = pd.DataFrame(hrows)
    if len(H):
        H.to_csv(OUT / "repro_t0950_hits.csv", index=False)
    num = R[R.column != "worst_group"]
    print(f"[repro] compared {len(R)} values ({R[['predictor', 'method', 'segment']].drop_duplicates().shape[0]} rows x "
          f"seeds); max abs diff {num.abs_diff.max():.3g}; values with diff > 1e-12: {(num.abs_diff > 1e-12).sum()}; "
          f"worst_group labels different: {int(R[(R.column == 'worst_group')].abs_diff.isna().sum())}")
    print(f"[repro] rows only in the re-analysis: {sorted(only_new)}")
    if len(H):
        print(f"[repro] hits.parquet: {len(H)} (seed, column) pairs, identical {int(H.identical.sum())}; "
              f"non-identical: {H[~H.identical][['seed', 'column']].values.tolist()[:20]}")


if __name__ == "__main__":
    main()
