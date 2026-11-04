<!-- English translation for the public snapshot (instruction 28 §3a, 2026-11-03). Translation only: the original
     DEVIATIONS.md (in Korean) is authoritative and unchanged.
     Original SHA-256 21565e1610876827d2ec59d4a9f48c3d6a2855313ca3d108c32483443a3c6834, last changed in commit 50ea7ce. -->

# Preregistration deviations and errata

`PREREGISTRATION.md` (git tag `prereg-v3`) is not modified. Deviations and notation errors found after the confirmation experiment are recorded in this document, and the same content is disclosed in an appendix of the paper.

## D1. The set of groups judged for C1 differs from the preregistered definition

- **Found:** 2026-09-29, confirmed when a count of groups below the bar of up to 26 appeared while reviewing the camera-outage results (David's review).
- **Content:** The preregistration document has 25 groups (all 1 + time of day 5 + hop kind 3 + exit speed 4 + exit zone 4 + branching 4 + isolation 4). The actual verdict was carried out with the `strata` list of the configuration file (26: no "all", plus 2 for first hop or not). First hop "no" is the same set as hop kind "later hop", and "yes" is the union of hop kinds "track start" and "re-acquisition". The groups that MVP calibrated are the same 25 as in the preregistered definition.
- **Impact analysis:** The worst-group recall is the same under both definitions (the union group and the all group cannot be the minimum). The number of groups below the bar can differ.
- **Re-grading (per hop, `posthoc_regrade.py`):** After re-running the confirmation experiment with its configuration as is and reproducing the original results exactly (difference 0 in the worst group and in the number of groups below the bar), it was re-graded with the preregistered definition. **The C1 verdict of every method is the same.** The primary method mvp_log has 0 groups below the bar in evaluation A and B under both definitions and passes C1; the secondary method qr_ogd has 1 in evaluation B under both definitions and does not pass. The number of groups below the bar is equal or smaller under the preregistered definition.
- **Re-check of the selection on the exploratory period (2026-09-29, done):** The two exploratory configurations (`porto_cctv`, `porto_cctv_replication`) were re-run with `posthoc_regrade.py`. The re-run reproduced the committed exploratory summaries exactly (difference 0 in recall, worst group, number of groups below the bar, cost). The per-segment number of groups below the bar of the four candidate methods (mvp_groups, mvp_log, qr_groups, qr_ogd) is the same under both definitions in all 5 evaluation segments. mvp_log and mvp_groups have 0 in all segments, and qr_groups and qr_ogd have 1 each in the two segments of exploratory period 1 (test_same, test_holiday). The result of `select_primary.py --regrade` is also the same as the original selection (PRIMARY mvp_log, SECONDARY qr_ogd, rule 5 applied: violating segments tied 2 to 2, lowest worst-group recall 0.920 to 0.910). The results are in `results/porto_cctv_regrade/` and `results/porto_cctv_rep_regrade/`.
- **Recomputation of the seed repetition and the cost-matched comparison (2026-09-30, done):** The post hoc seed repetition (seeds 0 to 4) and the cost-matched comparison were re-graded with the preregistered 25-group definition (`posthoc_seeds.py --groups prereg_25`, `posthoc_frontier.py --groups prereg_25`).
  - For every method and seed, the C1 verdict, the worst-group recall and the cost ratio are the same as under the 26-group definition. mvp_log passes C1 in 3 of 5 seeds, qr_ogd in 2.
  - Seed 0 is the same as the re-grading of the confirmation experiment.
  - In the cost-matched comparison, only the number of groups below the bar decreases by 1 in 20 of 48 rows (all group added, the 2 hopfirst groups removed); the worst group at the same cost and the 'minimum cost needed for 0 groups below the bar' are the same.
  - The results are in `results/porto_cctv_confirm_posthoc/seeds_prereg25/` and `frontier_prereg25/`.
- No check related to D1 remains.

## D2. Wrong column name in the selection-result table of the preregistration document

- **Found:** 2026-09-29, David's review.
- **Content:** The values in the column "Segments violating rule 1" of the selection-result table (qr_groups 1, qr_ogd 1) are actually "the maximum of the per-segment number of groups below the bar". The actual number of segments violating rule 1 is qr_groups 2, qr_ogd 2 (the two evaluation segments of exploratory period 1).
- **Impact:** None. The code computing rule 5 counted the violating segments correctly, and on the tie (2 to 2) qr_ogd became the secondary method by the lowest worst-group recall (qr_ogd 0.920, qr_groups 0.910). The value of the primary method mvp_log (0) is the same under both readings.

## D3. Changes to and restoration of the preregistration document after the tag

- **Found:** 2026-09-30, with `git log --follow -- PREREGISTRATION.md` while organizing the list of post hoc analyses (POSTHOC.md).
- **Content:** After the tag `prereg-v3` (`729b651`, 2026-09-28 17:04:24 −0400) there are three commits that changed `PREREGISTRATION.md`.
  - `3f696b4` (17:12:10, after the tag, before the confirmation run): one line of the "Code" row of the table deleted. This line was "The hash of a code archive at the time of fixing is also recorded: `________________`", a blank with no hash filled in. The confirmation experiment (working folder created 17:12:37, result commit `e77fb0a` 17:33:02) was run in this state.
  - `b71d6bc` (17:50:25, after the confirmation run): an overwrite accident. When the post hoc sensitivity analysis code was committed, an earlier draft from the analysis package overwrote the document. A draft title and 4 lines of guidance were added, the configuration-file hash was changed to a blank, and the deleted "Code" row reappeared.
  - `b6195be` (19:51:00, after the confirmation run): restored to the state at the tag. The current document is identical to the tag down to the git blob (`a19f9f9`).
- **Impact:** The decision criteria did not change. The three commits changed only the title and guidance at the head of the document, the configuration-file hash row and the code hash row, and did not touch the hypotheses, metrics, decision criteria (C1 to C4) or the rule for selecting the primary method. The confirmation-experiment configuration file (`configs/porto_cctv_confirm.yaml`) has not changed since the tag, and its sha256 equals the value written in the document. There is no code change between the tag commit and the confirmation-run commit (POSTHOC.md integrity record).
- **To disclose:** The code hash field of the document at the tag is blank. The code at the time of fixing is identified by the tag commit `729b651` itself, but a code archive hash was not recorded separately.

## D4. Confirmation experiment 2: the camera content hash in the lock record cannot be reproduced (found in the pre-run check)

- **Found:** 2026-10-15 17:48:29 −04:00. Found in the pre-run data check of the execution script (CHECK and STOP lines of `results/porto_cctv_confirm2/run_log.txt`).
- **Content:** The content hash of the camera table differed from the value in `LOCK_confirm2.txt` (`5bbd88e9…`). The hashes of the trip table and the hop table (transitions) were the same as in the lock.
- **Cause:** `frame_sha256` of the lock preparation script `confirm2_lock_prep.py` hashes `to_numpy().tobytes()` for each column. `cctv_ids` of the camera table is a string column, so this method hashes the bytes of Python object pointers (memory addresses), not the values. The hash of the same file therefore differs from run to run (computing twice on the same file gave `793ac531…` and `cb61e27e…`). The trip and hop tables, which have only numeric columns, are not affected.
- **Scope of impact:** `frame_sha256` is used only in the lock preparation (recording the data hashes) and in the pre-run check. It is not used in computing results (predictor, calibration, analysis). The camera data themselves are the same as at the lock: `work/porto_cctv_confirm2/cameras.csv` made by the run and `work/porto_cctv_confirm/cameras.csv` read at the lock are byte-identical (sha256 `cdaae7bd…`), and the values of the 7 columns are the same for all 176 sites.
- **State at the time of finding:** Only the data and events stages (`run_pilot.py --stage data`, `--stage events`, 17:46:27 to 17:48:26) had finished. The 50 runs had not started and there were no result files. No aggregation or viewing was done.
- **Handling (approved by JD, 2026-10-15):**
  - The frozen files and `LOCK_confirm2.txt` are not modified. The wrongly computed camera hash `5bbd88e9…` is also left as it is.
  - A supplementary record `LOCK_confirm2_addendum.txt` was newly created (`confirm2_addendum.py`). Its content is the definition of the function `frame_sha256_v2`, corrected to hash strings as UTF-8; the camera, trip and per-block hop table hashes recomputed with that function (trip and hop equal to the lock); the file sha256 of the two camera files and of `data/porto/porto_cctv.json`; and the result of the per-column value comparison.
  - The camera comparison of the pre-run check (`confirm2_execute.py`) was changed to three checks: (i) byte identity with the file read at the lock, (ii) per-column value identity, (iii) agreement of the corrected content hash with the supplementary record. The locked analysis and simulation code and the configuration were not changed.
- **Changes to the execution script after the lock:** `2ac330b` (execution script created, pushed 2026-10-15 17:46:27 −04:00) and this fix. This fix is at tag `confirm2-exec`, and its push time is in `LOCK_confirm2_addendum.txt` and `run_log.txt`. The tag `confirm2-plan` is unchanged.

## D5. Confirmation experiment 2: the taxi ID map of the new period was made by a script after the lock

- **Found:** 2026-10-16 22:0x −04:00. Found while preparing the analysis inputs after the 50 runs had finished.
- **Content:** The locked script `notes/confirm2/taxi_map.py`, which makes the trip_id → TAXI_ID map needed for the taxi cluster bootstrap, replays the filters of `porto.load` but not the rule excluding duplicate TRIP_IDs added at the lock (§2). It therefore does not match the trip numbers of the new-period working folder (numbers reassigned after the rule is applied).
- **Handling:** `confirm2_taxi_map.py` (committed and pushed 2026-10-16 22:03 −04:00, before the analysis started) was newly created.
  - It replays the same filters and exclusion rule and keeps TAXI_ID.
  - It was checked (assert) that the number of trips (535,843) and the start times of all trips are the same as in `work/porto_cctv_confirm2/trajectories.parquet`.
  - The result is 435 taxis, and 17 duplicate TRIP_IDs were excluded.
- **Impact:** The locked analysis and simulation code and the configuration were not changed. The map is only an input that attaches the cluster unit (TAXI_ID), and is the same as the definition of the plan (§5.2, the recorded TAXI_ID is used as the cluster unit). The result files were aggregated for the first time after the map was made.
- **Supplement (2026-10-20, instruction 02 v02 A-17):** Record of the map that the analysis read.
  - Analysis command line: Claude Code session record `~/.claude/projects/-home-user-ccpilot/916fde38-61ee-4063-9eea-c707f94ea4ef.jsonl` line 2542 (2026-10-16 22:03:51 −04:00). Content: `confirm2_analysis.py --block block1 $B1 --block block2 $B2 --taxi-map block1 work/porto_cctv_confirm2/taxi_map.parquet --taxi-map block2 work/porto_cctv_confirm2/taxi_map.parquet --attr block1 work/porto_cctv_confirm2/attr_block1.parquet --attr block2 work/porto_cctv_confirm2/attr_block2.parquet --out results/porto_cctv_confirm2/analysis --reachable`.
  - The modification time of the map read, `work/porto_cctv_confirm2/taxi_map.parquet` (output of the revised `confirm2_taxi_map.py`), is 2026-10-16 22:03:16 −04:00, and the modification time of `work/pid_c2an` (PID file of the analysis process) is 22:03:52 −04:00.
  - `--taxi-map` of `confirm2_analysis.py:694` is a required argument with no default. `analysis_log.json` has no path field (clusters: taxi 430, day 56).
  - The map before the fix (`work/confirm2_hops/taxi_map.parquet`, output of `notes/confirm2/taxi_map.py --candidate`) was used only for the count tallies of the pre-lock precheck (2026-10-13) (`results/precheck_confirm2/block_taxis.csv`, `daily_trips_taxis.csv`). **No record was found of computing confirm2 aggregates or confidence intervals with the map before the fix.**

## Correction (wording of the confirmation experiment 2 plan, no D number)

- Correction: the value 0.92 in the S4 qualifying wording (`PLAN_confirm2.md` §10.8, line 449 "around 0.92") → the manuscript uses the seed-0 value of Appendix A (held-out period reanalysis, target 0.95, qr_ogd re-acquisition recall 0.93, `\ctwoHeldReacqRecallQrOgdSeedZero`). Verdict 06 (2026-10-26). Presumed source: held-out period segment B (test_jun_b) seed 0, `notes/LOG.md`:619·1625 — [interpretation] (verdict 07, 2026-10-26).

## REVIEW (post hoc) deviations

Numbered separately from the confirmation deviations D1–D5. They concern the post hoc analyses responding to the external review (`results/porto_cctv_confirm2_posthoc/review/`).

### R1. REVIEW runs executed before the re-approval (verdict 01)

- **Content:** Run after the approval of REVIEW_PLAN revision 2 (1f74a93) and before verdict 01 (2026-10-20): 36/50 method runs, 2 refit trials (copy check, left-censored QR κ 0.005), 1 summary verification.
- **Handling:** Not deleted. It was checked that every run matches conditions 1–3 of revision 2 and code f8b9bc5 (`review/pre_reapproval_runs.csv`). The new methods were not aggregated and not viewed. The 14 waiting runs were cancelled by JD's decision (2026-10-19).
- **Record:** `review/PRE_REAPPROVAL.md`, `review/manifest_cache.csv`.

### R2. Concurrency of the 6.3/6.4 refit set from an assumed value rather than the measured RSS (verdict 03)

- **Content:** The 31 refits of instruction 02 v02 §6.3/6.4 were run with concurrency 12 (2026-10-21 13:06–21:07 EDT). The rule (CLAUDE.md §1 rule 7) is concurrency = min(12, floor(32 / measured RSS)). The concurrency was set from the assumed value of 0.7 GB in the rule table, and the measured maximum RSS was 3.27 GiB (12 × 3.27 = 39.3 > 32). In the same time window, 3 §7 aggregations (up to 6.13 GiB) were also running.
- **Impact:** In the same period, `free -g` used 19 GiB (13:06, 13:15 EDT). The exit codes of all 31 were 0, and the output hashes are in `review/runs_02.csv`. Not re-run.
- **Handling (verdict 03):** From then on, the concurrency is set after measuring the first unit with `/usr/bin/time -v`. The R3 re-run is the first application (first unit 3.06 GiB, concurrency 9).
- **Record:** `review/PRE_REAPPROVAL.md` section R2, report 02 §4, verdict 03 §1.

### R3. Cost computation of the replay of label sets (iii) and (iv): negative camera counts at τ > 2 (verdict 03, instruction 03 §1)

- **Content:** Line 170 of `posthoc_review_labels.py` (13303f6) computed the hop cost with `CostLookup.cost_per_hop(tau)` (`confirm2_analysis.py:82-84`). This lookup stores the sorted probabilities (0–0.954) of key i in one array, shifted by 2i. Therefore, for τ > 2, the search position runs into the values of later keys and the camera count becomes negative. For τ ≤ 2 it equals the definition (`VisibilityModel.cost`, `ccpilot/predictors.py:179-186`) (`review/diag03/lookup_domain.csv`).
  - (iii) mvp_log: `MVP.q_to_tau` (`ccpilot/multigroup.py:98-99`) gives τ = inf for q ≤ 0.
  - (iii) qr_ogd: τ = exp(log τ_QR + Σθ), and θ is clipped at ±3 per group (`posthoc_review_labels.py:129-130`). There are hops with τ > 2.
  - (iv): negatives occur in 5 runs of mvp_log t 0.90 (1,792 hops) and 8 runs of qr_ogd t 0.95–0.98 (120 hops).
- **Handling:** Only the cost computation was changed to `hop_cost` (τ capped at 1.5; since all probabilities are ≤ 1, the cost is 0 for τ > 1 = definition) (c7de4f7). The hits do not change. A 5-hop hand-computation test is `tests/test_review_hop_cost.py`. The 50 replays of (iii) and (iv) were re-run with the same settings and seeds. The earlier outputs are kept in `work/review_cache/runs_superseded/` (parquet, logs), and the earlier timing in `review/timing_superseded/`. Re-aggregated: B_aci (5 targets), B_refit (0.95, 0.93). The tables, macros and consequence_check were regenerated.
- **Scope:** The same `cost_per_hop` is also used by `posthoc_review_methods.py:203` (put) and `posthoc_review_refit.py:139`. The outputs of these two sets were outside the scope of instruction 03 §1 and were not opened at that time. Closed by the full check of report 04-1 (153 outputs, 1,253 columns, 0 negatives) (verdict 07).
- **Record:** `review/diag03/`, report 03.

## Note: revision before the confirmation run (already recorded in preregistration document v3)

- The computation of C2 was revised from "at most 1.20 in each evaluation segment" to "mean of the ratios of evaluation A and B at most 1.20". The confirmation experiment also passes under the criterion before the revision (A 1.183, B 1.171). The tag `prereg-v3` commit precedes the confirmation result commit.

### Internal record: history before the tag (confirmed by JD 2026-10-01, basis of C5-29 and C5-30 of manuscript chapter 5)

The first commit of the repository is the tag `prereg-v3` (`729b651`), so the order below cannot be checked with git. The basis is the research record (conversation, the v4 to v7 change notes of the README, revision history of PREREGISTRATION.md section 4-1). All of it is before the tag.

| Order | Content | Basis |
|---|---|---|
| 1 | The worst-group criterion 0.94 was introduced in the first preregistration draft (virtual-placement stage). | conversation (JD) |
| 2 | In the factor analysis of the exploratory period on the virtual placement (v5), branching was the strongest miss factor. | README v5, conversation |
| 3 | On the real CCTV placement (v6), factor analyses of the two exploratory periods were done. Branching and isolation were the largest factors. At this point there were 17 groups (README v4), and the cost of MVP (uniform scale) was about 1.11 to 1.18 times the oracle. | README v4·v6, PREREGISTRATION.md section 1, conversation |
| 4 | Branching and isolation were added to the groups (17 → 25, v7). At the same point, C1 was changed to the Wilson upper bound 0.94, and the C2 cost criterion 1.20 was newly set. | README v7 (preregistration v2), conversation |
| 5 | The two exploratory periods were re-evaluated with 25 groups and the selection rule was applied (mvp_log, mean cost ratio over five segments 1.191). | `select_primary.py` re-run (LOG 2026-09-29) |
| 6 | The C2 computation was revised from "per segment" to "mean of evaluation A and B" (after seeing the per-segment ratios 1.12 to 1.24 of 5). The confirmation experiment also passes under the criterion before the revision (A 1.183, B 1.171). | PREREGISTRATION.md section 4-1 (v3) |
| 7 | Tag (2026-09-28 17:04:24 −0400), start of the confirmation run (17:12:37). | git, file times of `work/porto_cctv_confirm/` (LOG 2026-09-30, POSTHOC.md integrity record) |

- The manuscript states only the order 1 to 5 (chapter 5: "0.94 from the first draft; 1.20 set after seeing the exploratory results of the earlier, smaller group configuration and before evaluating the final groups"). 6 is not stated in the manuscript.
- The cost ratio of 3 (1.11 to 1.18) and the order of 1, 2 and 4 cannot be recomputed from the result files of the repository (results from before the tag are not in the repository).

## Result to report alongside: test against the target 0.95 itself

The C1 criterion 0.94 is the target 0.95 with a margin of 1 percentage point. Applying the same test at 0.95 (preregistered definition, number of groups whose 95% Wilson upper bound is < 0.95), the confirmation experiment results are as follows. No method passes the 0.95 criterion, so the paper also gives the size of the shortfall (0.95 − recall).

| Method | Evaluation A | Evaluation B |
|---|---|---|
| mvp_log | 7 | 7 |
| qr_ogd | 3 | 4 |
| static | 12 | 19 |
| ACI(γ = 0.0005) | 10 | 8 |
| Mondrian (40 cells) | 10 | 20 |
| qr_groups | 13 | 24 |
