# PRE_REAPPROVAL — runs made before the re-approval (REVIEW deviation R1, POST HOC)

- Recorded 2026-10-20 (Sean instruction 01 v02 §4, verdict 01 Q3). Inventory: `pre_reapproval_runs.csv`; cache manifest:
  `manifest_cache.csv` (164 files under `work/review_cache/`, sha256, generator, commit). Script:
  `posthoc_review_prereapproval.py`.
- Plan in force when the runs were made: REVIEW_PLAN revision 2 (`1f74a93`, Sean (2nd) approval 2026-10-19). Code:
  `f8b9bc5` (2026-10-19 21:03:22 −04:00; `posthoc_review_{common,p0,methods,refit,summary}.py` unchanged since, `git diff
  f8b9bc5 HEAD` empty for these files, `ccpilot/` and `confirm2_analysis.py`).

## Runs

| Kind | Count | Started (−04:00) | Plan conditions of rev 2 |
|---|---|---|---|
| Method runs A, B (ACI, (ii) online), C (`posthoc_review_methods.py --run`) | 36 of 50: block1 all 25; block2 t0.90 and t0.93 (10); block2 t0.95 seed 0 (1) | 2026-10-19 21:03:23 (first, timing run) to 22:37 and later | 1 (A2 smallest τ_G, `posthoc_review_methods.py:101`) and 2 ((ii) feedback fb_mask ∪ audit for ACI, mvp_log, qr_ogd, `:166-170, :234-240`) match |
| Refit trials (`posthoc_review_refit.py --job`) | 2: block1, t 0.95, seed 0: `copy_check` (finished, 8,202 s) and `Bi_refit_b_k0005` (left-censored QR, κ 0.005, δ 0; **finished**, 12,329 s) | 2026-10-19 21:03 | 3: κ 0.005 run; **κ 0.02 not run** |
| Summary validation | 1: stored static, mvp_log, qr_ogd, t 0.95 (both blocks, seeds 0-4), compared with the confirm2 analysis csv | 2026-10-19 21:03:37 (end 21:17:40) | n/a |

- No run was found not matching the plan; nothing moved to `work/review_cache/runs_superseded/`.
- No aggregation of the new methods was computed and no per-hop hit/cost value of the new methods was read or reported.
  The summary validation compared only stored methods with the confirm2 analysis outputs.
- JD decision (2026-10-19, during instruction 00): "(b) 시험은 마치고 대기분은 취소" — the left-censored trial was let
  finish, the pending method runs were cancelled.
- Cancelled 14 runs, file `work/review_cache/CANCELLED_2026-10-19.txt` verbatim:

  ```
  cancelled 14 pending method runs (instruction 00); kept: 36 runs
  ```

  The 14 (the 50 runs minus the 36 outputs): block2_t0950_s1–s4, block2_t0970_s0–s4, block2_t0980_s0–s4.
- The cancelled 14 runs, the refits and the left-censored QR (κ 0.02, block2) are to run under instruction 02 (after
  verdict 02).

## R2 (verdict 03): concurrency of the instruction 02 v02 §6.3/6.4 refits

- 31 refit jobs ran 12 concurrent (2026-10-21 13:06–21:07 −04:00). The rule (CLAUDE.md §1 rule 7) is
  min(12, floor(32 / measured RSS)); the concurrency was set from the assumed 0.7 GB of the rule table, and the measured
  maximum RSS was 3.27 GiB (12 × 3.27 = 39.3 > 32). Three §7 aggregation jobs (up to 6.13 GiB) ran at the same time.
  `free -g` used 19 GiB at 13:06 and 13:15. All 31 exit status 0; outputs and hashes in `runs_02.csv`. Not rerun.
- From verdict 03 on, concurrency is set after the first unit is measured with `/usr/bin/time -v` (DEVIATIONS R2).

