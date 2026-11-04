# Post hoc analyses (English version for the public snapshot)
<!-- Rewritten in English from POSTHOC.md (SHA-256 78d2fc7c2b1047f20e352783a5f0becb88ba37042c11b1060801a89f2ac31933, commit ea77e49), instruction 28 §3a; the Korean original stays in the repository history of the authors. -->

After the preregistration (git tag `prereg-v3`, commit `729b651`, 2026-09-28 17:04 −0400), the confirmation experiment was run and recorded once, in commit `e77fb0a` (2026-09-28 17:33 −0400). **Every analysis after that is a post hoc analysis.** None of them changes the preregistered verdicts (C1–C4), and the paper reports them only as post hoc analyses. Detailed numbers and interpretation of each entry are in `notes/LOG.md`; differences from the preregistration are in `DEVIATIONS.md`.

Notation
- Periods: exploratory 1 (`porto_cctv`, 2013-11 to 2014-01), exploratory 2 (`porto_cctv_replication`, 2014-02 to 04), confirmation (`porto_cctv_confirm`, 2014-05 to 06)
- **Developed after confirmation**: a method or setting created or chosen after the confirmation-period results were seen. Using it as evidence in a method comparison would be post hoc tuning.

## Integrity record

- `PREREGISTRATION.md` and `configs/porto_cctv_confirm.yaml` are currently identical to tag `prereg-v3`.
  - `git diff prereg-v3 -- …` prints nothing.
  - The git blob of `PREREGISTRATION.md` is `a19f9f9` at both the tag and HEAD.
  - `.githooks/pre-commit` enforces this.
- **Configuration file:** the only commit that changed `configs/porto_cctv_confirm.yaml` is `729b651`. Its current sha256 (`0606a4a2…b672703e9eb`) equals the value written in the preregistration document.
- **Every commit that changed `PREREGISTRATION.md`** (`git log --follow -- PREREGISTRATION.md`, times −0400):

| Commit | Time | Relative to the confirmation run (`e77fb0a`, 17:33:02) | Change | State after the change |
|---|---|---|---|---|
| `729b651` | 2026-09-28 17:04:24 | before | First commit of the repository. Document added (74 lines). Tag `prereg-v3` points to this commit. | Tagged original (blob `a19f9f9`) |
| `3f696b4` | 2026-09-28 17:12:10 | before | One line of the "code" row of the table deleted. The deleted line was "also record the hash of the code archive at the time of fixing: `________________`", a blank whose hash had never been filled in. Commit message ".". | One line different from the tag. **The confirmation experiment was run in this state.** |
| `b71d6bc` | 2026-09-28 17:50:25 | after | When the post hoc sensitivity code was committed, an earlier draft of the document contained in the analysis package committed with it overwrote the document. Four lines of draft title and notes were added (primary method selected; to be fixed after recording the hash; draft before review by the authors), the configuration-file hash became a blank (`record the sha256sum result here before running: ________________`), and the "code" row deleted in `3f696b4` reappeared. | Draft before fixing |
| `b6195be` | 2026-09-28 19:51:00 | after | Restored to the tagged state. The four draft lines were removed and the configuration-file hash restored. The "code" row exists in the tag as well, so it was kept. | Same as the tag (blob `a19f9f9`) |

  - The changes after the tag did not touch the verdict criteria (hypotheses, metrics, C1–C4, selection rule). All three commits changed only the "code" row of the table, the configuration-file hash row, and the title and notes at the head of the document.
  - In the tagged document the code-hash field is blank (`________________`). The code at the time of fixing is identified by the tag commit `729b651` itself; no hash of a code archive was recorded separately.
- **Identifying the code of the confirmation experiment** (manuscript preparation, step 6, 2026-09-30):
  - The confirmation run command is `run_pilot.py --config configs/porto_cctv_confirm.yaml` (data, events and evaluation stages).
  - The tag commit `729b651` contains all code used for this run: `run_pilot.py`, the 12 modules of `ccpilot/` (`__init__`, calibration, cameras, evaluate, events, factors, geo, multigroup, plots, porto, predictors, synthetic), `environment.yml`, and `configs/`.
  - `git diff 729b651 e77fb0a -- ccpilot/ run_pilot.py environment.yml configs/` prints nothing, and no commit in between changed these files. The committed code at the time the confirmation results were committed is therefore the code of the tag.
  - Blob hashes at the tag:
    - `run_pilot.py` `537b4e6`, `environment.yml` `acd2daf`
    - `ccpilot/evaluate.py` `c38cf81`, `multigroup.py` `4a74bc4`, `predictors.py` `777129f`, `calibration.py` `742eb99`, `events.py` `1ed9aa3`
    - the rest: `git ls-tree 729b651 ccpilot/`
  - Limitation: whether the working copy had uncommitted changes at run time cannot be checked with git (same as the item below).
  - The reproduction check that re-ran the confirmation experiment post hoc with the default settings used code later than the tag. All added features are optional, and the summary and hop-level results equalled the frozen results. The run was not repeated with the tagged code itself.
- **Code from the tag to the confirmation-run commit:** `git diff --stat 729b651 e77fb0a` shows 21 changed files.
  - 20 are additions of the confirmation results (`results/porto_cctv_confirm/`).
  - The remaining 1 is the one-line deletion in `PREREGISTRATION.md` (`3f696b4`).
  - Code (`ccpilot/`, `*.py`), configuration (`configs/`) and environment (`environment.yml`) did not change.
  - Limitation: git shows only committed states. Whether there were uncommitted working-copy changes at run time cannot be checked with git.
- **Timeline of the confirmation run** (file times from the local file system, −0400):

| Time | Evidence | Event |
|---|---|---|
| 17:04:24 | commit `729b651` | preregistration tag |
| 17:12:10 | commit `3f696b4` | blank code-hash row of the preregistration document deleted |
| 17:12:37 | creation time of folder `work/porto_cctv_confirm/` | **confirmation run starts** (line 24 of `run_pilot.py` creates this folder right after start) |
| 17:12:53 – 17:13:38 | creation times of files in `work/porto_cctv_confirm/` | data and event stages (trajectories → cameras → sightings → transitions → truth → meta) |
| 17:13:38 | creation time of folder `results/porto_cctv_confirm/` | evaluation stage starts |
| 17:25:54 | last modification time of a result file | evaluation ends |
| 17:33:02 | commit `e77fb0a` | confirmation results committed |

  - File times are values recorded by the operating system and are not cryptographic evidence. If a folder was deleted and created again, only the last creation time remains.
- **Confirmation results:** the only commit that changed `results/porto_cctv_confirm/` is `e77fb0a`. The reproduction check that re-ran the confirmation experiment with the default settings gave identical summary and hop-level results (`notes/LOG.md`, 2026-09-29, 2026-09-30).

## List

| # | Commit | Date | Analysis | Period | Script | Results | Note |
|---|---|---|---|---|---|---|---|
| 1 | `b71d6bc`, `afa46f2` | 09-28 | Sensitivity: feedback share and delay, detection errors | confirmation | `posthoc_sensitivity.py` | `results/porto_cctv_confirm_posthoc/<scenario>/`, `sensitivity_summary.csv` | |
| 2 | `a095304` | 09-28 | CityTrac-style baseline added; evaluation seeds repeated (0–4) | confirmation | `posthoc_seeds.py` | `…_posthoc/seeds/` | CityTrac-style baseline added after confirmation |
| 3 | `63e2e34`, `14b78be` | 09-29 | Cost-matched comparison (worst group against cost curve) | confirmation | `posthoc_frontier.py` | `…_posthoc/frontier/` | |
| 4 | `07c45c3` | 09-29 | Camera outage stress test (none, rand10·20·30, region 800 m) | confirmation | `posthoc_outage.py` | `…_posthoc/outage/` | |
| 5 | `750165d` | 09-29 | Confirmation experiment regraded with the 25 preregistered groups | confirmation | `posthoc_regrade.py` | `results/porto_cctv_confirm_regrade/` | D1 |
| 6 | `8590244` | 09-29 | `--regrade` option of the selection rule; D1 and D2 recorded | — | `select_primary.py` | `DEVIATIONS.md` | |
| 7 | `71036b0` | 09-29 | Regrading of the exploratory periods and recheck of the primary-method selection | exploratory 1·2 | `posthoc_regrade.py`, `select_primary.py` | `results/porto_cctv_regrade/`, `results/porto_cctv_rep_regrade/` | selection unchanged |
| 8 | `0b3321a` | 09-29 | Diagnosis of slow adaptation under outage: saturation, V·N snapshots, start-date comparison, warm-start ablation | confirmation | `posthoc_outage_diag.py` | `…_posthoc/outage_diag/` | warm-start ablation is diagnostic only |
| 9 | `c04b69a` | 09-29 | Decomposition of hop losses under outage (lost origin, exit conversion, reconnection) | confirmation | `posthoc_exit_split.py` | `…_posthoc/exit_split/` | |
| 10 | `deb9c90` | 09-29 | Outage-aware predictor (one-step composition) | confirmation | `posthoc_outage_aware.py`, `ccpilot/predictors.py` | `…_posthoc/outage_aware/` | **developed after confirmation (new method)** |
| 11 | `6bf4ebd` | 09-29 | Outage-aware hop analysis; mvp_log τ_min ceiling | confirmation | `posthoc_outage_ceiling.py` | `…_posthoc/outage_aware/hop_analysis/` | |
| 12 | `73e3519` | 09-29 | Ablation of log-scale resolution versus upper bound a_min (normal, outage) | exploratory 1·2 | `posthoc_scale_ablation.py` | `results/porto_cctv(_rep)_posthoc/scale_ablation/` | variants chosen after confirmation |
| 13 | `0c11fd1` | 09-29 | Random outages repeated (5 site seeds) | confirmation | `posthoc_outage_aware.py --out-sub` | `…_posthoc/outage_aware/seeds/`, `seeds_summary.csv` | counts of groups below the bar use the 26-group definition (recomputed with 25 in #18) |
| 14 | `f484051` | 09-30 | Fixed region rule and site list (recorded before running) | all periods | `ccpilot/posthoc.py` | `notes/LOG.md` | **chosen after confirmation** |
| 15 | `d46cfd2` | 09-30 | Nature of τ_min (cells with zero observations); Pr[σ < τ_min] per group | confirmation | `posthoc_taumin_nature.py` | `…_posthoc/taumin_nature/` | |
| 16 | `221ae36` | 09-30 | Seed repetition and cost-matched comparison recomputed with the 25-group definition | confirmation | `posthoc_seeds.py --groups prereg_25`, `posthoc_frontier.py --groups prereg_25` | `…_posthoc/seeds_prereg25/`, `frontier_prereg25/` | D1 completed |
| 17 | `43fd1cb` | 09-30 | Fixed-region (20 sites) outage, causes of region shortfalls, upper-bound control, V trajectory | all periods | `posthoc_outage_suite.py`, `posthoc_outage_suite_report.py`, `posthoc_region_diag.py`, `posthoc_v_trajectory.py` | `…/outage_suite/`, `…/region_diag/`, `…/v_trajectory/` | |
| 18 | `2bfbd9f` | 09-30 | Random outages repeated (rand10·20·30 × 5 site seeds, two predictors, a_min 0.001 and 0.005 variants) | exploratory 1·2, confirmation | `posthoc_outage_suite.py`, `posthoc_outage_suite_report.py` | `results/<period>_posthoc/outage_suite/`, combined `results/porto_cctv_confirm_posthoc/outage_suite/all_periods_summary.csv` | 25-group definition, two cost ratios, a_min ceiling comparison. In exploratory 1 the outage start overlaps the year-end holidays |
| 19 | `323a6eb` | 09-30 | Review tables (random-outage tables per seed for three periods, a_min ceiling comparison, resolution-matched upper-bound control); outage-aware mvp_log against the hindsight oracle by group and by hop category | confirmation (comparison), exploratory 1·2 (tables) | `posthoc_review_tables.py`, `posthoc_oa_oracle_groups.py` | `results/porto_cctv_confirm_posthoc/review/` | predictor refitted only (checked to match saved results) |
| 20 | paper `dd7b5cb`, `d396738` | 09-30 | Manuscript verification analyses: convexity of cost in the miss level, qr_ogd offset clipping and inequality (116 runs over three periods, predictors reconstructed), per-group miss rate of the qr_groups calibration data, outage verdicts under the 26- versus 25-group definitions | all periods | paper `scripts/verify_todos.py`, `scripts/check_claims.py` | paper `generated/checks/` | all reconstructions match the saved hop results. The paper is a separate repository |
| 21 | paper `50f9f6f` | 10-01 | Internal review item M5: hop-chain track custody (k = 1–5) against the independence assumption, by start state | confirmation (seed 0) | paper `scripts/make_tables.py` (`tab_custody`) | paper `generated/data/tab_custody.csv` | additional analysis. Chain definition and values equal the frozen `custody_by_hops.csv` |
| 22 | `906c800` | 10-01 | Internal review item M1: hindsight references that satisfy the group condition: (a) per-group minimum-threshold rule, (b) hindsight group quantile regression (fitted on all data) | confirmation (seed 0, no outage) | `posthoc_group_oracle.py` | `…_posthoc/group_oracle/` | additional analysis. Predictor refitted only (scores, static cost and oracle checked to match). Optional argument `lp_method` in `qr_group_taus` (default behaviour unchanged) |
| 23 | `28aeead` | 10-01 | Internal review item M3: observation radius 30 and 75 m (merge radius set equal), T_max 300 and 900 s sensitivity | confirmation period (held out), events reconstructed per setting | `posthoc_geometry.py`, `configs/porto_cctv_confirm_geom_*.yaml` (new files) | `…_posthoc/geometry/` | additional analysis. Primary predictor, reduced method set, seed 0. Run time 260–286 s per setting |
| 24 | `f748f9e` | 10-01 | Internal review item M3, extension: evaluation seeds 0–4 for the four geometry and time settings (ACI, qr_ogd, mvp_log; static and oracle do not depend on the seed) | confirmation (held out) | `posthoc_geometry.py --seeds 1 2 3 4`, `--summarize-seeds` | `…_posthoc/geometry/<setting>/seeds/`, `geometry_seeds.csv`, `geometry_seed_pass.csv` | additional analysis. The default setting uses the earlier seed repetition (#16). About 4 min per seed |
| 25 | `458641b`, `c3b77a2` | 10-02 | confirm2 pre-check B1: cluster-bootstrap intervals of group recall (taxi, day), design effect, per-group standard deviation over evaluation seeds 0–4 | confirmation (held out) | `posthoc_cluster.py`, `notes/confirm2/taxi_map.py` | `…_posthoc/cluster_ci/` | additional analysis. Saved hop results only. Taxi IDs recovered by replaying the raw data (all start times match) |
| 26 | `c3b77a2` | 10-02 | confirm2 pre-check B2: realized value of the qr_ogd inequality (offset replay, evaluation seeds 0–4) | confirmation (held out) | `posthoc_qrogd_bound.py` | `…_posthoc/qr_ogd_bound/` | additional analysis. Replayed from the saved hits, feedback masks and arrival times |
| 27 | `ab5fdcc`, the commit that added this entry | 10-18 | Confirmation 2 track custody: same definition as Table 18 of the earlier manuscript (`evaluate.custody_table`), chain start group (all, track start, re-acquisition) × k = 1–5 × 10 methods × blocks and pooled, seed mean and seed range, conservative 95% taxi and day cluster intervals (B = 2,000, second version), paired differences between methods | confirmation 2 (blocks 1·2) | `posthoc_custody_confirm2.py` | `results/porto_cctv_confirm2_posthoc/custody/` | **decided after the confirmation 2 results were seen** (the authors, 10-17). Stored outside the frozen directory |
| 28 | the commit that added this entry | 10-18 | Decomposition of chains starting at re-acquisition: conditional hit rate of hops 2–5, hop cost ratio, conditional hit rate on common chains (hop 1 hit by both methods) and survival at k = 5, target 0.95, pooled and per block, 95% paired taxi-cluster differences | confirmation 2 | `posthoc_custody_decomp_confirm2.py` | `results/porto_cctv_confirm2_posthoc/custody/decomp_*.csv` | **decided after the confirmation 2 results were seen** (internal review of manuscript draft v3, item 4.3; common-chain condition set by the authors) |

## Common caveats for the summary of conclusions

- Verdict definition: counts of groups below the bar in the outage analyses #8–#13 use the as-run 26-group definition; #16–#18 use the preregistered 25-group definition. The two definitions differ by at most one group in the outage experiments (checked in #18).
- Cost: from #17–#18 on, cost is reported as two ratios: one against the hindsight oracle of the same predictor and the same run, the other against the hindsight oracle of the no-outage condition in the same period and segment.
- Noise between scenarios: the sort of evaluation hops is not stable, so the feedback sample differs slightly between runs (mvp_log cost difference before the outage about 0.6%). Not fixed, to keep the confirmation experiment reproducible.
- Authors' decision (2026-09-30): two-step composition and a remedy for the first 48 hours are not developed. The paper mentions them only as limitations and future work.

## Code and infrastructure work (does not change analysis results)

| Commit | Content |
|---|---|
| `ee92655` | CLAUDE.md, pre-commit hook protecting the preregistration artifacts, work log |
| `e17fbb0` | Post hoc scripts refactored to a common helper (`ccpilot/posthoc.py`). Checked byte-identical to the earlier results |

All features added to the core library (`ccpilot/evaluate.py`, `multigroup.py`, `predictors.py`) are optional and do not change behaviour at their default values.
- `eval.mvp_diag`, `warm_weight`
- `eval.outage.aware_predictors`
- `eval.save_scores`
- MVP `floor_level`
- separated row mapping of `score()`

Reproduction check results are in `notes/LOG.md`.
