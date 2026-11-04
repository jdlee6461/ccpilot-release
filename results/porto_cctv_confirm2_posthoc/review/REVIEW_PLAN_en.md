<!-- English translation for the public snapshot (instruction 28 §3a, 2026-11-03). Translation only: the original
     results/porto_cctv_confirm2_posthoc/review/REVIEW_PLAN.md (in Korean, mostly English) is authoritative and unchanged.
     Original SHA-256 45926234a18747267f9b17e6d396002fb079c083fb0fec88920819c5814804e5, last changed in commit 0e79eb8.
     English lines are copied verbatim; the lines that contained Korean are translated. -->

# REVIEW_PLAN — external-review analyses on confirm2 (POST HOC)

- Revision 5 (2026-10-31; Sean instruction 17 §3(p) draft, approved by Sean in verdict 21 C and by JD in chat
  "G8-1 실행" (Korean: "run G8-1") on 2026-10-31 11:34 KST; instruction 18 §4): part B gains label set (v) (audit hops only; group-wise ACI,
  mvp_log, qr_ogd) and qr_groups_refit7 under (iv), with appendix B7 (result consequences of (v)). Text = the draft
  notes/instructions/REVIEW_PLAN_rev5_draft.md (c077417) unchanged. No definition of revisions 1-4 is changed.
  Written before any computation of the new variants.
- Revision 4 (2026-10-20, Sean instruction 02 §3; critique-02 verdict C7): label sets (iii) and (iv) of part B added
  (definitions, methods, skip rule, symmetry columns). No other definition changed. Written before any aggregation.
- Revision 3 (2026-10-20, Sean instruction 01 v02 §3, verdict 01 Q2-1): wording, tables and an appendix only; **no
  definition is changed** relative to revision 2 (1f74a93). Added: direction wording of A(2) (§3.1), the input-symmetry
  table of B (ii) (§3.2), the comparison pairs (§3.3), the B additional-target rule with its target (§3.4), and the
  appendix "result consequences" (§3.5; v02 of Sean's document). Written before any aggregation of the new methods.
- Status: **plan only, nothing run.** Execution starts after Sean approves this file (approval to be recorded at the end of this file and in notes/LOG.md).
- Written 2026-10-19 by Claude Code from Sean's instruction "외부 검토 대응 분석" (Korean: "analyses responding to the external review") (handover memo "외부 검토 대응" (Korean: "response to the external review")) and the
  feasibility note `results/exploratory_postconfirm2/review_feasibility.md` (commit b3992ac).
- **POST HOC.** Every result is a post-hoc addition on the confirm2 period. The §10.8 judgement wording (improvement /
  non-inferior / classes, "claim supported") is **not applied**; results are described (point estimates and intervals only).
- Data: confirm2 period only (block1: train 2013-07-01..07-29, cal 07-29..08-05, eval 08-05..09-02; block2: train
  09-02..09-30, cal 09-30..10-07, eval 10-07..11-04). The unused 2014 periods (2014-01-06..02-02, 2014-04-28..05-04)
  are not read or processed in any way.
- Frozen / locked files are read only: PREREGISTRATION.md, configs/porto_cctv_confirm.yaml, results/porto_cctv_confirm/,
  PLAN_confirm2.md, configs/porto_cctv_confirm2.yaml, configs/confirm2/*, configs/confirm2_analysis.yaml,
  configs/porto_cctv_heldout_reanalysis.yaml, LOCK_confirm2.txt, results/porto_cctv_confirm2/.
- Code: new scripts `posthoc_review_*.py` only. `ccpilot/` and `confirm2_analysis.py` are not modified; functions are
  imported, and where a variant is needed a post-hoc copy of the function lives in the new script (default behaviour of
  the copy is checked against the original where it applies).
- Outputs: `results/porto_cctv_confirm2_posthoc/review/` (this file, csv files, REPORT.md, review_numbers.tex).
  Large intermediate files (calibration scores, cost lookups) go to `work/review_cache/` (git-ignored).

## Common definitions (all parts)

| Item | Definition |
|---|---|
| Runs | 2 blocks x 5 targets t in {0.90, 0.93, 0.95, 0.97, 0.98} x evaluation seeds 0-4 (= the 50 confirm2 runs), unless a part says otherwise |
| Stored inputs | per run `hits.parquet` (evaluation scores of the 5 predictors, group columns, `feedback`, `t_res_hit`, `t_res_miss`, hit/cost columns), `cost_lookup_src_zone_hour_speed.npz`, `run_config.yaml` |
| Groups | the 25 pre-registered groups (`prereg_25`: all + hgroup 5 + hopkind 3 + speed_bin 4 + zone 4 + entropy_bin 4 + nn_bin 4); a group is judged if n >= 200 in the scope |
| Group deficit | d_G = t - R_G (not truncated; negative = above target), per seed, then mean over seeds 0-4 |
| **D̄** | worst-group deficit: max over judged groups of d_G, per seed, then mean over seeds (confirm2 `worst_deficit`) |
| **Re-acquisition d** | d_G for G = hopkind=2 (confirm2 `group_keys.reacquired`) |
| **Cost relative to H2** | mean cost of the method / mean cost of H2, where H2 = the largest single threshold on the same predictor's evaluation scores whose overall recall is >= the method's realised overall recall (per method and seed); per seed, then mean over seeds (confirm2 definition). Costs from the cost lookup of that predictor (`CostLookup.cost_per_hop`) |
| Cost-ratio differences (added 389d349, verdict 03) | in the difference output, the paired difference of the cost relative to H2 (`cost_ratio_H2_diff` = ratio of the comparator − ratio of the reference, same seeds, same bootstrap replicates, same intervals); a description added to the outputs, no definition changed |
| Scopes | block1, block2, combined (both blocks pooled), as in the confirm2 analysis |
| Intervals | cluster bootstrap, 95%, B = 2,000, clusters taxi (joint over blocks) and day (resampled within block), conservative combination (lower = min of the two, upper = max of the two); multinomial weights as in `confirm2_analysis.py` (code copied, not modified); bootstrap seed 20261013 (`configs/confirm2_analysis.yaml` seeds.bootstrap); H2 refitted in every replicate |
| Differences | for description only: Δ = D_comparator - D_method for method in {mvp_log, qr_ogd} (confirm2 sign convention, positive = improvement of the method), same intervals |
| Predictor | `src_zone_hour_speed` (confirm2 primary) unless part C |
| Comparison pairs (rev 3) | all with the "Differences" convention Δ = D_comparator − D_reference, for D̄, re-acquisition d and isolation-Q4 d, and the cost relative to H2 of each side; same intervals. **A:** each new baseline (A1_mondrian_small, A2_aci_groups, A3_qr_groups_inter) against the QR family (qr_groups, qr_groups_refit) and against the online methods (mvp_log, qr_ogd); the stored main comparators (static, mondrian_hour_hop_speed, aci_g0005) are listed alongside. **B:** online (mvp_log, qr_ogd) against refit (qr_groups_refit) within the same label set ((i): stored online values vs Bi_refit_a; (ii): Bii_mvp_log, Bii_qr_ogd vs Bii_refit_a), at t = 0.95; ACI variants (Bi_aci, Bii_aci, full aci_g0005) against the online methods of the same label set, all targets. **C:** per predictor, group methods (qr_groups, mvp_log, qr_ogd; qr_groups_refit where run) against marginal methods (static, aci_g0005) |

## P0. Recompute calibration scores and cost lookups; reproduction check

1. For each block, read `work/porto_cctv_confirm2/` directly (transitions, truth, cameras; no CSV re-read) with the block's
   locked run configuration `configs/confirm2/porto_cctv_confirm2_<block>_t0950.yaml` (read only; splits, model and strata
   settings are identical across targets). This bypasses the `confirm2_run.py` guard by design (Sean approval).
2. Rebuild strata (`_add_strata`, `_add_spatial`), fit the 5 `VisibilityModel`s on the training split, score the
   calibration hops (s_cal, observed = true labels, p_det = 1) and the evaluation hops; save s_cal and the calibration
   hops' group columns, and the cost lookups of the 4 non-primary predictors.
3. Reproduction check (**bit-for-bit; any difference stops the work and is reported**):
   - recomputed evaluation scores = stored `score|<predictor>` for all 5 predictors, both blocks;
   - recomputed primary cost lookup = stored `cost_lookup_src_zone_hour_speed.npz` (keys and arrays);
   - for all 50 runs: hits of `static`, `qr_groups` and `mvp_log` (primary predictor) recomputed from s_cal + stored
     evaluation scores + stored `feedback` / `t_res_*` = stored hit columns; the same for `src_zone_speed` (stored there too).
4. Timing: one run (block1, t = 0.95, seed 0) of every new computation below is timed before the rest is started.

## A. Simple baselines (all 50 runs; primary predictor)

### A(1) Small Mondrian
- Cells: track state (hopkind 0 = later hop, 1 = first hop of trip, 2 = re-acquired) x {entropy_bin = 3 (branching Q4)} x
  {nn_bin = 3 (isolation Q4)} = 12 cells.
- Merging, based on calibration-period hop counts: re-acquired (hopkind = 2) is always one cell. Within hopkind 0 and
  within hopkind 1, all cells with < 200 calibration hops are merged into one cell; if that merged cell still has < 200
  hops it is merged into the largest cell of the same track state. A cell that still has < 200 hops (only possible for
  the re-acquired cell) uses the global threshold (`mondrian_taus` rule).
- Threshold per cell: split-conformal `conformal_tau` on the cell's calibration scores at level alpha = 1 - t.
- Reported: final number of cells and the merges per block (calibration counts per original cell).
- No feedback; independent of the seed (the 5 seeds give identical results, reported once per seed for uniformity).

### A(2) Group-wise ACI (one variant)
- One ACI state per group of the 25 (alpha_t^G and a sliding window of 2,000 scores); gamma = 0.0005, alpha clip
  (-0.5, 1.0), window 2,000 (as `aci_g0005`). Initial window per group: its last 2,000 calibration scores in time order
  (all calibration scores if the group has < 50 calibration hops, as in `aci_taus`).
- Group threshold tau_G = `conformal_tau(window_G, alpha_t^G)` (TAU_MIN if alpha_t^G <= 0).
- **Applied threshold: the most permissive value over the hop's groups, read as the threshold that searches the most,
  i.e. the minimum tau_G over the 7 groups containing the hop** (each group's own threshold is then met or exceeded;
  confirmed by Sean 2026-10-19).
  Direction (rev 3): the minimum τ_G over the groups containing the hop, i.e., the most permissive threshold (the most
  search).
- Feedback: the stored `feedback` mask and resolution times (hit: `t_res_hit`, miss: `t_res_miss`, decided by the applied
  threshold); at resolution every group containing the hop updates alpha_t^G with err = 1{score < applied threshold} and
  appends the hop's score to its window.

### A(3) qr_groups with intersections
- `qr_group_taus` design (log score, intercept + reference-coded indicators of the 6 dimensions) plus 6 indicators for the
  intersections I1-I6 (`confirm2_analysis.INTER`: I1 hopkind=2∧nn_bin=3, I2 hopkind=2∧entropy_bin=3, I3 hopkind=2∧speed_bin=3,
  I4 hopkind=1∧nn_bin=3, I5 speed_bin=3∧nn_bin=3, I6 hgroup=0∧hopkind=2); same LP (`highs`), at most 80,000 calibration
  rows subsampled with the evaluation seed, quantile level alpha. Fitted on the calibration period only (no feedback).
- Results for I1-I6 are reported separately from the 25 groups (D̄ uses the 25 groups only).

## B. Censored feedback (primary predictor)

- Censoring: of the feedback hops (stored `feedback` mask), only those found under the threshold in force for them
  (score >= tau) reveal their score; a missed feedback hop reveals only "score < tau" (its miss indicator).
- Variants:
  - (i) censoring only;
  - (ii) censoring + random audit: a 5% sample of **all** evaluation hops, drawn per run with the evaluation seed as
    `rng = default_rng(seed); rng.random(n)` (discarded: this first draw is the stored feedback mask) then
    `audit = rng.random(n) < 0.05` (second draw, so the audit is independent of the feedback sample); an audited hop
    reveals its score whether hit or miss, at its resolution time (hit: `t_res_hit`, miss: `t_res_miss`), and is used as
    a labelled feedback hop even if it is not in the feedback mask.
  - (iii) (rev 4; critique-02 verdict C7) no label for failed searches: a feedback hop (F) gives a label (hit = 1, score
    revealed) only if it is in the search set (score >= tau in force). A missed feedback hop is not distinguished from
    an exit and gives no label at all (neither score nor miss indicator). No audit.
  - (iv) (rev 4) (iii) + random audit 5%: the audit set A is the same draw as in (ii); an audited hop gives a full label
    (hit/miss indicator and score) whatever the outcome, at its resolution time (hit: `t_res_hit`, miss: `t_res_miss`).
  - Methods under (iii) and (iv) (rev 4): ACI (`aci_g0005`), group-wise ACI (A2 definition), mvp_log, qr_ogd, all 50
    runs; static, qr_groups and intersection QR use no feedback (unchanged); refit (`qr_groups_refit`) under (iv) only,
    t = 0.95, seeds 0-4, both blocks. Refit is not run under (iii): the refit uses only labelled scores of feedback
    hops (`posthoc_review_refit.py:67-68`, mode 'labelled'; the original `multigroup.py:273-274` uses the score of every
    resolved feedback hop), never the miss indicator, so its input under (iii) is the same as under (i) (a) (detected
    feedback hops plus calibration hops), and its input under (iv) is the same as under (ii) (a).
  - Update rule of the online methods under (iii) and (iv) (rev 4): a hop without a label is skipped — no state update
    (no alpha_t / theta / V, N change, no window append); it counts as "no observation". A labelled hop updates as in the
    full-feedback definition (miss indicator from the applied threshold; ACI window receives its score).
- Methods:
  - `mvp_log`, `qr_ogd`: (i) stored results reused (their updates use only the miss indicator, which censoring keeps).
    (ii) recomputed with the feedback set fb_mask ∪ audit (all 50 runs), so that the online methods and the refit
    receive the same feedback (Sean, 2026-10-19); updates still use only the miss indicator.
  - `static`, `mondrian_hour_hop_speed`, `qr_groups`: no feedback; stored results.
  - ACI (`aci_g0005`, all 50 runs): alpha_t is updated from the miss indicator of every feedback hop (and audited hop in
    (ii)); the window receives only revealed scores (hits of the feedback hops; in (ii) also every audited hop). Bias
    accepted.
  - Refit (`qr_groups_refit` only, t = 0.95, seeds 0-4, both blocks, (i) and (ii); 20 refit runs), (a) labelled rows
    only: at each daily refit time T the fit uses every calibration hop plus the feedback hops that are hits and resolved
    by T (and in (ii) the audited hops resolved by T); otherwise as `qr_refit_taus` (80,000-row subsample with the seed,
    `highs`). Bias accepted.
  - (b) left-censored QR, **trial only, if time remains**: t = 0.95, seed 0, both blocks, (i) only; Chernozhukov-Hong
    three-step at every refit time: (1) logit of P(uncensored | x) on the feedback hops resolved by T (same design);
    (2) QR on calibration hops plus feedback hops with fitted P > 1 - alpha + kappa, censored hops entering at their
    censoring value log tau; (3) QR on calibration hops plus feedback hops with x'beta_2 > log tau + delta.
    Constants delta = 0 and kappa in {0.005, 0.02} (two runs per block, sensitivity to kappa reported; Sean,
    2026-10-19); reported with runtime and the share of feedback hops kept in steps 2 and 3.
- Key output: whether the order online (mvp_log, qr_ogd) vs refit changes on D̄ and re-acquisition d at t = 0.95
  (described, not judged).
- Input symmetry of the label sets (rev 3). F = stored feedback mask (fb_mask), A = audit sample (5% of all evaluation
  hops), D = hops detected under the threshold in force for them. "Events" = hops whose miss indicator is fed back at
  resolution; "scores" = hops whose score is revealed.

  | Method | Label set (i) | Label set (ii) | In part B? | Label set (iii) (rev 4) | Label set (iv) (rev 4) |
  |---|---|---|---|---|---|
  | static | no feedback (calibration only) | no feedback (calibration only) | stored, listed | unchanged (no feedback) | unchanged (no feedback) |
  | ACI (`aci_g0005`) | events F; scores F ∩ D | events F ∪ A; scores (F ∩ D) ∪ A | yes, all targets | labels F ∩ D | labels (F ∩ D) ∪ A |
  | group-wise ACI (A2) | — | — | not in B (part A only, full feedback F) | labels F ∩ D | labels (F ∩ D) ∪ A |
  | qr_groups | no feedback (calibration only) | no feedback (calibration only) | stored, listed | unchanged (no feedback) | unchanged (no feedback) |
  | refit (`qr_groups_refit`) | events F; scores F ∩ D | events F ∪ A; scores (F ∩ D) ∪ A | yes, t = 0.95 | not run (same input as (i)) | scores (F ∩ D) ∪ A (same input as (ii)) |
  | refit7 (`qr_groups_refit7`) | — | — | not in B (plan: refit only) | — | — |
  | mvp_log | events F (miss indicator only) | events F ∪ A (miss indicator only) | yes; (i) = stored values | labels F ∩ D | labels (F ∩ D) ∪ A |
  | qr_ogd | events F (miss indicator only) | events F ∪ A (miss indicator only) | yes; (i) = stored values | labels F ∩ D | labels (F ∩ D) ∪ A |
  | intersection QR (A3) | — | — | not in B (part A only, no feedback) | unchanged (no feedback) | unchanged (no feedback) |

  In (iii) and (iv) every method that uses feedback receives the same labelled hops (F ∩ D, plus A in (iv)); the
  audit set A is the same for refit, ACI, group-wise ACI and the online methods (rev 4).
  Every method of part B that uses feedback receives the same events in a label set (F in (i), F ∪ A in (ii)); the
  methods that read scores (ACI, refit) receive the same revealed scores. mvp_log and qr_ogd read only the miss
  indicator, which is known for every event.
- Additional-target rule (rev 3; critique-01 verdict C3), fixed before any result: (1) result sentences of B are
  restricted to "at target 0.95"; (2) if in label set (i) or (ii) the order online vs refit on re-acquisition d differs
  from confirm2 (confirm2: refit >= online, i.e. refit has the smaller deficit), the refit of that label set is run at
  one additional target; if the order is the same, no additional run. **Additional target = 0.93**: in the confirm2
  analysis (`results/porto_cctv_confirm2/analysis/main_estimands.csv` @ 1a806b3, scope combined,
  estimand reacq_deficit_diff, proposed mvp_log, comparator qr_groups_refit7) |Δ| is 0.0095, 0.0105, 0.0077, 0.0055,
  0.0053 at t = 0.90, 0.93, 0.95, 0.97, 0.98; the largest is at 0.93. (For reference, with comparator qr_groups_refit
  the largest |Δ| is at 0.90, 0.0107; the rule uses refit7.)

## B (rev 5). Label set (v): audit hops only

- **Definition.** Let A be the audit set of (ii) and (iv): the same draw, `rng = default_rng(seed)`, first draw
  `rng.random(n) < 0.3` (the stored feedback mask F, checked), second draw `audit = rng.random(n) < 0.05`.
  - Under (v), only audited hops give labels. An audited hop gives a full label (hit or miss indicator and its score)
    at its resolution time (hit: `t_res_hit`, miss: `t_res_miss`).
  - A feedback hop outside A gives no label, whether found or missed. Hops found by the search but not audited are not
    used.
  - Update rule as in (iii) and (iv), rev 4: a hop without a label is skipped (no state update, no window append).
- **Methods** (primary predictor `src_zone_hour_speed`, all 50 runs: 2 blocks × 5 targets × seeds 0-4), with the frozen
  settings unchanged and no tuning:
  - `mvp_log`: m = 40, a_min = 0.002, eta = theory, warm start on the calibration week.
  - `qr_ogd`: gamma 0.005, clip 3, base = `qr_groups`.
  - group-wise ACI: the part A(2) definition.
  - Implementation: the functions of `posthoc_review_labels.py` with the push condition `audit[i]`; mode "full" must
    still reproduce the stored hits bit for bit (as in rev 4).
- **Relation to inverse-probability weighting (one line).** Under (iv), a non-audited feedback hop is labelled only if
  it was found, so its inclusion depends on the outcome, and no weight can recover the misses. An audited hop is
  included with the constant probability 0.05, independent of the outcome and of x. Its inverse-probability weight is
  therefore the constant 20, which only rescales the step size. Audit-only updating with the step sizes unchanged is
  the unweighted form of that estimator, and no separate weighted variant is run.
- **`qr_groups_refit7` under (iv)**, to separate the anchor of the cumulative refit (review M E4). The rows are:
  - the calibration hops resolved in (T − 7 days, T];
  - the feedback hops that are hits (F ∩ D) and every audited hop (A), resolved in (T − 7 days, T];
  - each with its observed score. This is the `posthoc_review_refit.py` mode 'labelled' with window 7 days.
  - Otherwise as `multigroup.qr_refit_taus`: 80,000-row subsample with the seed, `highs`.
  - By the argument of rev 4, its input equals refit7 under (ii); refit7 under (iii) equals refit7 under (i).
  - Runs: t = 0.95, seeds 0-4, both blocks (10 runs). Further targets only under the additional-target rule of rev 3,
    with 0.93 as the additional target.
- **Pre-count of audited hops** (stored feedback masks, evaluation hops; `exploratory/gate8/audit_counts.csv`, read
  before any run). The expected values are 5% of the evaluation hops.

  | Block | Evaluation hops | Audited hops, seeds 0-4 | Post-gap hops | Audited post-gap hops, seeds 0-4 (expected) |
  |---|---|---|---|---|
  | 1 | 534,713 | 26,476–26,848 | 1,779 | 75–96 (88.95) |
  | 2 | 667,972 | 33,221–33,615 | 2,611 | 109–146 (130.55) |

  Under (v), the post-gap group therefore receives about 75–146 labels per block and run, against 496–796 feedback
  outcomes applied to it under full feedback (`exploratory/qrogd_clip`, T_G of `hopkind=2`).
- **Estimands** (as in part B; five targets, primary target 0.95):
  - D̄;
  - post-gap d (hopkind = 2) and isolation-Q4 d;
  - cost relative to H2;
  - absolute cost (camera·s per hop, mean over evaluation hops).
  - Intervals: taxi and day cluster bootstrap, 95%, B = 2,000, the conservative bound at each end.
  - Paired differences of each method under (v) against the same method under full feedback and under (iv), and of
    each online method under (v) against `qr_groups_refit7` under (iv) and `qr_groups_refit` under (iv) (t = 0.95).
- **Also reported**, as a description of how much the online state moved: the number of label updates per group and
  run, and the largest |θ_G| of `qr_ogd` per group and run.

## C. Predictor sensitivity

- Predictors: `src`, `src_zone`, `src_zone_hour`, `src_zone_speed`, `src_zone_hour_speed`.
- From stored results (all 50 runs): `static`, `aci_g0005`, `mondrian_hour_hop_speed` for all 5 predictors; `qr_groups`,
  `mvp_log`, `qr_ogd` for `src_zone_speed` and the primary; `qr_groups_refit` for the primary.
- New (all 50 runs): `qr_groups`, `mvp_log`, `qr_ogd` for `src`, `src_zone`, `src_zone_hour`, with the frozen settings
  (multigroup dims, mvp_log m = 40, a_min = 0.002, eta theory; qr_ogd gamma 0.005, clip 3; qr_max_n 80,000).
- New refit: `qr_groups_refit` for `src_zone_speed` only, t = 0.95, seeds 0-4, both blocks (10 runs).
- Cost relative to H2 with each predictor's own cost lookup (P0).

## Order and reports

1. P0 + reproduction check -> report (stop if any check fails).
2. Timing of one run of each new computation -> report.
3. A, B (ACI), C without refits -> report.
4. Refits: B (a) (20 runs), C (10 runs); then (b) trial if time remains -> report.
- Each step: csv files in review/, REPORT.md section, notes/LOG.md entry, commit `Post-hoc (review): ...`.
- Macros in `review_numbers.tex` (prefix `\rev...`, source comment with file, filter, column and ccpilot commit), written
  only after the report of the step they come from.

## Estimated cost (from the feasibility note)
- P0 < 1 h; A + B (ACI) + C without refits: about 35-45 CPU hours, a few hours wall-clock in parallel.
- Refits: about 1.7 h each with `highs`; 30 refit runs ≈ 50 CPU hours, about 5-10 h wall-clock (6-10 in parallel,
  memory to be checked on the first run).

## Appendix R. Result consequences (rev 3; Sean, `sean/REVIEW_결과별_귀결_v02.md` (Korean file name: "result consequences"), attached verbatim; replaces v01 on JD's instruction 2026-10-20)

````markdown
# REVIEW post hoc additional analyses — manuscript consequences by result v02 (2026-10-20, Sean; v01 + B5, B6, verdict critique02 C7)
Written before the aggregates are computed. Alex starts the aggregation only after committing this file as an appendix section of a revision of REVIEW_PLAN.md. Every result is marked POST HOC, and the §10.8 verdict words ("confirmed", "add", "opposite", etc.) are not used. The basis of comparison is "the re-acquisition d, the worst-group D̄ and the cost relative to H2 at the same target", and differences are reported with 95% intervals over the taxi and day clusters (B=2,000, conservative bounds). The direction of a sentence is set only when the interval does not contain 0.

## A. Fair simple baselines (small Mondrian, group-wise ACI, intersection QR)
- A1. If the worst-group D̄ of the small Mondrian or of group-wise ACI is **not distinguished** from the QR family (qr_groups, qr_groups_refit) at the same target (difference interval contains 0) and the cost relative to H2 is not distinguished either: remove from VI-B, VII and the contribution sentences every implication that "the overlapping-group, quantile-regression machinery is needed", and write "any calibration that conditions on the operational groups — including a small Mondrian partition and per-group ACI — closes most of the shortfall". The central message ("whether groups are calibrated makes a large difference") is kept.
- A2. If the two baselines are **significantly worse** than the QR family (D̄ difference interval excludes 0, smaller on the QR side): keep the current sentences + one sentence "simpler group-aware baselines reduce but do not close the shortfall". If they are cheaper, say so in the same sentence.
- A3. If a baseline is **significantly better** than the QR family: report it as it is, and write "a simpler method sufficed in this evaluation" in VII. Reduce the mentions of the QR family in the contribution sentences.
- A4. Intersection QR (I1–I6 as groups): if the intersection shortfall disappears (upper bound of the interval of each I ≤ 0.01), write in the operational guidance of VII "intersections that matter operationally can be added as groups"; if it remains, keep the limitation. Report I1–I6 separately and state in the table that this is a self-evaluation (evaluating a method that includes the intersections on those intersections).

## B. Censored-feedback sensitivity ((i) scores censored, miss indicators available, (ii) (i) + 5% audit, (iii) no labels for failed searches, (iv) (iii) + 5% audit)
- B0. In (i), mvp_log and qr_ogd use only the miss indicators, so their results equal those under full feedback. This means the censoring does not apply to them, and it is not used as evidence of robustness. B1 and B2 are sentences about the QR family (score censoring) and the refit; the censored results of the online methods are discussed only under (iii) and (iv).
- B1. If the order online versus refit (target 0.95) is **the same** as in confirm2 (refit ≥ online): keep the S2 sentence, add to VII "the ordering was unchanged under censored feedback (target 0.95)". No additional run.
- B2. If the order **changes** (online significantly better): the S2 verdict sentence (full feedback, pre-specified) is not changed. Write in VII "under censored feedback, at target 0.95, the online methods were [better]; this is a sensitivity result, not a pre-specified comparison", run the refit at the one additional target of verdict critique01 C3, and write the results of both targets together. In the abstract only one phrase ("the ordering depended on the feedback model").
- B3. If, under censoring alone (i), the worst-group D̄ of all group methods becomes **larger by 0.02 or more** than under full feedback: write limitation (a) strongly as "an audit of unlabeled searches is required", and put the audit share into the operational guidance. If smaller than that, limitation (a) keeps its current wording.
- B4. The left-censored QR (b, two values of κ) is a seed-0 trial, so it is not used in conclusion sentences, only in a supplementary-material table.
- B5. (iii) no labels for failed searches, no audit: if the worst-group recall of the online methods falls 0.05 or more below the target (by the interval upper bound), write limitation (a) as "without any audit of failed searches, the online methods do not hold the target", and put into the operational guidance "a mechanism that audits, or checks the outcome of, failed searches is essential". If less than 0.05, only the number: "degraded by [x] pp".
- B6. (iv) no labels + 5% audit: if the worst-group D̄ of the online methods is within 0.02 of full feedback (interval included), "a 5% audit of failed searches was sufficient in this evaluation"; if it exceeds that, "a 5% audit was not sufficient" with the numbers. Either way, the order against the refit (iv) follows the B1 and B2 rules, limited to target 0.95.

## C. Predictor sensitivity (5 predictors, all conditioning more simply than the primary predictor)
- C1. If, for all five predictors, the worst-group D̄ of the group methods (qr_groups, mvp_log, qr_ogd) is smaller than that of static and ACI (difference interval excludes 0, same direction): "the group-versus-marginal gap was not specific to the predictor among the five conditioning levels we tried". Nothing is said about stronger predictors (limitation (c) kept).
- C2. If the direction changes or is not distinguished for some predictors: report in a table for which predictors that happens, and in VII only "the gap narrowed [or reversed] for the weakest predictors". No effect on the contribution sentences (the pre-specified comparison uses the primary predictor).
- C3. The results of the refit (one alternative predictor, t=0.95) are not used in the S2 sentence (one predictor, one target).

## Common
- In every case, the abstract sentences on the pre-specified results (S1, S2, S3, S4) do not change. Post hoc results get at most one phrase in the abstract.
- Even if a result of the new analyses goes in the opposite direction to the §10.8 verdicts, the verdict table (claims_10_8.csv) is not changed. Only as an "additional analysis" subsection in the body.
- If a situation not covered by these consequences arises, mark next to that sentence that it was decided after seeing the results.
````

## Approval
- [x] Sean approval 2026-10-19 (via JD). Answers: (1) group-wise ACI applies the smallest tau_G (as written);
  (2) audit drawn as written, and in (ii) mvp_log and qr_ogd are recomputed with feedback fb_mask ∪ audit, (i) reuses the
  stored values; (3) (b) trial with delta = 0 and kappa = 0.005 and 0.02. Plan revised accordingly (this commit).
- Revision 3 (2026-10-20): Sean instruction 01 v02 §3 (verdict 01 Q2-1, critique-01 verdict C3/C6); no definition changed.
- Revision 3, appendix R replaced by Sean's v02 (2026-10-20, JD): no definition changed; the plan body still defines label sets (i) and (ii) only.
- Revision 4 (2026-10-20): Sean instruction 02 §3; label sets (iii), (iv) added; other definitions unchanged.

## Order and resources (rev 5; estimates from earlier part B runs)

1. JD G8-1 approval and Sean approval of this text. Commit as REVIEW_PLAN rev 5.
2. Copy check: mode "full" equals the stored hits bit for bit (mvp_log, qr_ogd) and the cached A2 hits (group-wise
   ACI). Stop on any difference.
3. Label set (v), 50 runs:
   - Reference: rev 4 (iii)/(iv) runs (same script, 4 methods × 2 label sets) took 273–489 s per run (median 464 s,
     50 runs, 6.2 CPU-hours) with a maximum RSS of 3.23 GiB, 10 in parallel.
   - Expected: (v) has 3 methods × 1 label set, ≤ 8 min per run. Concurrency min(12, floor(32/3.3)) = 9, about
     50 min wall-clock.
4. `qr_groups_refit7` under (iv), 10 runs:
   - Reference: the stored refit7 took 2,048–2,292 s per run; the (ii)/(iv) cumulative refit took 4,319–7,182 s at
     3.27 GiB.
   - Expected: about 40–80 min wall-clock with 9 in parallel. With the additional target 0.93, the same again.
5. Aggregation with `posthoc_review_summary.py` (label B_v; B = 2,000, 95%):
   - Reference: the B_aci aggregation used 6.6 GB for the first unit, 4 in parallel; one target about 10–20 min.
6. Report, then macros (`\ctwoRevV...`) after the report. Every step:
   - `free -g`, `nproc` and the anglova_full check before the run;
   - `/usr/bin/time -v` around each run;
   - a `notes/LOG.md` entry and a `Post-hoc (review): ...` commit.

## Appendix B7. Result consequences of label set (v) (fixed before any run; B6 rule applied to (v))

Notation:
- D̄(v), D̄(full), D̄(iv): the worst-group shortfall of an online method (`mvp_log`, `qr_ogd`; group-wise ACI reported
  alongside) under (v), under full feedback, and under (iv), at target 0.95.
- "Within 0.02" means that the upper bound of the paired interval of D̄(v) − D̄(full) is at most 0.02.

| Case | Condition (both online methods unless stated) | Abstract (iv) sentence | Operational implication 1 | VII interpretation sentence |
|---|---|---|---|---|
| B7a | D̄(v) − D̄(full) within 0.02 | add: "updating on the 5% audit alone kept the worst-group shortfall within [upper bound] pp of full feedback (additional analysis)" | "an online update should use only labels that are sampled independently of the search outcome (the audit)" | "in this evaluation the degradation under (iv) came from pooling outcome-selected labels with audited ones; updating on the audit alone was sufficient" |
| B7b | not B7a, and D̄(iv) − D̄(v) interval excludes 0 (v better) | "updating on the 5% audit alone reduced the worst-group shortfall to [value] pp ([interval]) but did not reach full feedback (additional analysis)" | "use audit labels only; a 5% audit was not sufficient in this evaluation" | "excluding outcome-selected labels reduced but did not remove the degradation" |
| B7c | interval of D̄(iv) − D̄(v) includes 0 or v worse | "neither the pooled labels nor the 5% audit alone held the worst group (additional analysis)" | "with a 5% audit, the online schemes did not hold the target; a larger audit or full labels are required" | "the degradation was not caused by the pooling alone" |
| B7d (with any case) | median label updates of the post-gap group per run < 200 (pre-count: 75–146) | — | — | add: "with about [N] audited post-gap hops per block, the online state of the rarest group was updated rarely; its result under (v) reflects the warm start more than the updates" |
| mixed | the two online methods fall in different cases | each method stated with its own case; no pooled sentence | the weaker case | each method stated |

- Refit7 under (iv): the order against the online methods under (iv) and (v), at t = 0.95, follows B1/B2 (unchanged).
  The refit7 result does not enter the S2 sentence (prespecified, full feedback).
- If G8-1 is not run: per verdict 20 A #11, the (iv) interpretation sentence becomes "a property of the tested pooling
  scheme; audit-only updating was not tested".
- Common rules of appendix R apply:
  - the abstract's prespecified sentences S1-S4 are unchanged;
  - post-hoc results get at most one clause in the abstract;
  - claims_10_8.csv is not changed;
  - a situation not covered here is marked as decided after the result.

## Approval (rev 5)
- Sean: verdict 21 C (2026-10-31, "Sean 승인" (Korean: "Sean approves")).
- JD: chat message "G8-1 실행" (Korean: "run G8-1"), 2026-10-31 11:34 KST.
- Committed before any (v) or refit7 (iv) run.
