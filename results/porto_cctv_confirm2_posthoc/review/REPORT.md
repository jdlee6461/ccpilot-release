# REVIEW — external-review analyses on confirm2 (POST HOC)

- Plan: `REVIEW_PLAN.md` (Sean approved 2026-10-19). POST HOC; no §10.8 judgement wording; description only.
- Period: confirm2 (two blocks), evaluation seeds 0-4. 2014 unused periods not touched. Frozen files read only.

## 1. P0: calibration scores, cost lookups, reproduction check (2026-10-19)

Commands: `python posthoc_review_p0.py --scores`; `python posthoc_review_p0.py --check BLOCK T SEED` (50 runs, 12 in
parallel); `python posthoc_review_p0.py --summary`. Outputs: `p0/scores_block{1,2}.json`, `p0_repro_hits.csv`;
cache `work/review_cache/<block>/` (cal.parquet, cost lookups, key ids; git-ignored).

| Check | block1 | block2 |
|---|---|---|
| hops train / cal / eval | 718,140 / 141,001 / 534,713 | 781,977 / 173,080 / 667,972 |
| eval hop order and 6 group columns = stored | yes | yes |
| eval scores = stored `score|*`, bit for bit, 5 predictors | yes (max abs diff 0) | yes (max abs diff 0) |
| primary key ids and `cost_lookup_src_zone_hour_speed.npz` = stored | yes | yes |
| fit + scoring time, 5 predictors | 29 s | 36 s |

- Hits recomputed from s_cal + stored eval scores + stored feedback, all 50 runs (2 blocks x 5 targets x seeds 0-4),
  predictors `src_zone_hour_speed` and `src_zone_speed`, methods `static`, `qr_groups`, `mvp_log`:
  **300 of 300 comparisons bit for bit equal, 0 differing hops.**
- Time per check run 340-829 s (median 696 s, 12 in parallel); memory about 1.3 GB per process (ps RSS).
- A(1) cells from the recomputed calibration hops (`A1_mondrian_cells.csv`): in both blocks the four re-acquired cells
  have < 200 calibration hops (block1 165/146/85/57, block2 276/207/94/107) and are one cell (block1 453, block2 684 hops);
  all 8 cells of hopkind 0 and 1 have >= 2,744 hops, so no other merge; **9 final cells per block, no global fallback.**
