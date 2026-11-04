<!-- English translation for the public snapshot (instruction 28 §3a, 2026-11-03). Translation only: the original
     notes/instructions/PLAN_confirm2.md (in Korean) is authoritative and unchanged.
     Original SHA-256 b23b9b748c54b6944f5ba9043119e6de8fe3af58e8a7a0a2ab825be9c7a0c4f7 (= plan_sha256 of LOCK_confirm2.txt),
     last changed in commit 6758bce (lock commit), git tag confirm2-plan. Line n of the translation body is line n of
     the original. The plan calls the first hop after an exit a "re-acquisition" hop; the paper calls it "post-gap". -->

<!-- Original: https://claude.ai/code/artifact/9c5e7ea2-67bf-4c77-ad75-2cd8093a4672 (rev 72). Exported on 2026-10-15. Final version approved by JD. After the lock this file is not modified. -->

# Confirmation experiment 2 plan (PLAN_confirm2, final version rev 72)

Oct 13, 2026 · @JD

## 0. Summary

The unused period of the Porto data (2013-07-01 to 11-03, 126 days) is split into two consecutive period blocks and run once, with all methods, comparators and parameters fixed. There is no pass mark. At several target recalls we report the per-group shortfall and confidence intervals (at each bound, the more conservative of taxi clusters and day clusters), the absolute cost, and the ratio to hindsight references.

- **What is checked**: whether online multi-group calibration (mvp_log, qr_ogd) reduces the worst-group shortfall in a new period compared with marginal calibration and offline group calibration (including a version refitted daily with the same feedback). How much it costs compared with hindsight references.
- **Core design**: evaluation period of 56 days (about 2.5 times the 22 days of the existing held-out evaluation segments). The two blocks are consecutive periods that share the same city, taxi population and settings, so they are not independent replications.
- **Claims**: for each sentence, the conditions for keeping, qualifying or deleting it are fixed in advance (§10.8). Numbers are used instead of adjectives.
- **Status**: pre-check values incorporated (§2), two independent reviews incorporated (§13.6). The Alex check items remaining before the lock are in §13.1.

The pre-check values that Alex fills in before the lock, the review items of David and the independent critic, and JD's decision record are collected in Section 13.

## 1. Purpose and claims

**Frame of the manuscript claims (redefined).** The existing manuscript's "achieves the specified recall per group" is not used. Even on the existing evidence alone (seeds 3/5, 0/5 at 900 seconds, re-acquisition around 0.92) this claim does not hold. Instead the frame of the four sentences below is set, and whether each sentence is kept, qualified or deleted is decided by the results under the conditions of §10.8. Adjectives such as "substantially", "similar" and "stably" are not used; numbers and intervals are used instead.

> **S1.** Online multi-group calibration [moves search to the hard situations that marginal calibration misses, and] reduces the shortfall of the re-acquisition group by [min–max difference] over the targets [range]. On the worst-group shortfall it is [classification of ΔD̄].
>
> **S2.** This difference [appears / was not detected / was the opposite] also compared with offline group calibration refitted daily with the same feedback (cumulative window, 7-day window).
>
> **S3.** The cost is [ratio] times the hindsight group quantile regression reference (H3) (point estimate; at target 0.95 the interval reflecting threshold uncertainty is [sensitivity interval]), and [ratio] times a single threshold matched to the same overall recall (H2) (95% interval).
>
> **S4.** In the rarest situation (e.g., track re-acquisition) a shortfall of [d̄ value and interval] remains.

**Questions to check**

| No. | Question | Estimates that answer it |
| --- | --- | --- |
| Q1 | When the target changes, how closely does the actual recall of each group follow the target | Per-target, per-group shortfall and intervals, shortfall of the two pre-specified groups, worst-group shortfall (§5) |
| Q2 | At the same target, is the worst-group shortfall of online multi-group calibration smaller than that of the comparators (static, ACI, Mondrian, qr_groups, qr_groups_refit, qr_groups_refit7) | Differences between methods and simultaneous intervals (§5.5) |
| Q3 | At the same absolute cost, which method has the higher worst-group recall | Cost curve F2. A **descriptive item**; a verdict sentence is written only when the dominance rule of §10.5 is satisfied |
| Q4 | How large is the cost of multi-group calibration compared with the hindsight references | Cost ratios to the four hindsight references and intervals (§6) |
| Q5 | Is the direction the same on partitions and intersections not used for calibration | Shortfall on alternative partitions, paired differences against the 25 groups (§8, §10.7) |
| Q6 | Do the two blocks give the same conclusion | Paired difference of D̄ between blocks and interval (§10.3) |

mvp_log and qr_ogd are reported on an equal footing, without a primary/secondary distinction. The difference between the two methods is only described, and no hypothesis that one is better is set.

## 2. Data, periods, split

**Candidate period.** Porto taxi trajectories from 2013-07-01 to 11-03 (126 days, 535,857 trips after filtering). The training period of exploratory 1 starts on 11-04, so there is no overlap. The camera layout (176 sites, snapshot of 239 cameras) and the preprocessing are the same as before.

**Pre-check results** (Alex, 2026-10-13, commit 072ebfc, `results/precheck_confirm2/`. In the new period only hop extraction, group attribute computation and counting were done; no method was run)

| Item | Value | Verdict |
| --- | --- | --- |
| Overlap with existing exploratory and held-out periods | None. All 126 days present | No dates to exclude |
| Duplicate TRIP_ID | 1 after filtering (2013-10-09, block 2 evaluation, 19 hops). 17 within the period in the raw data | Handling rule below |
| Days only flagged | 2013-08-15 public holiday (block 1 evaluation), 2013-10-27 end of daylight saving time (block 2 evaluation) | Included, flagged in the report |
| Re-acquisition hops in the block 1 evaluation segment | 1,779 | 1,500 or more → keep two blocks |
| Re-acquisition hops in the block 2 evaluation segment | 2,611 | 1,500 or more |
| Re-acquisition hops combined | 4,390 | — |
| Cells with fewer than 200 hops (25 groups, intersections, alternative partitions) | None. The smallest cell is I6 (0–6 h × re-acquisition), block 1 274, block 2 281. Re-acquisition × isolation, branching, speed Q4: block 1 507–834, block 2 685–1,278 | Nothing to flag |
| Taxis in the evaluation segment | block 1 427, block 2 426. Median hops per taxi 1,153 / 1,480.5, maximum 3,843 / 4,002 | Sufficient for the cluster bootstrap |
| Meaning of TAXI_ID | **Cannot be confirmed.** The UCI documentation describes the field as a "taxi driver" identifier while the overview says "442 taxis" | The recorded TAXI_ID is used as the cluster unit as is (§5.2) |

**Handling rules.**

- **Duplicate TRIP_ID (general rule, JD decision 2026-10-15)**: the existing preprocessing has no rule for duplicates (records with the same TRIP_ID enter as separate trips). In the new period, **all** records whose TRIP_ID is duplicated within the period are excluded. This is to avoid choosing which record to keep. At the raw-data stage there are 17 duplicates within the period; applying the rule removes 14 trips and 29 block 2 evaluation hops. The number of re-acquisition hops does not change (Alex). The held-out period had 2 duplicate pairs, and the frozen experiment treated them as separate trips. The manuscript states that the preprocessing of the two periods differs at this level (the reanalysis follows the frozen settings, so the separate-trip handling is kept).
- **The public holiday and the end-of-daylight-saving day** are not excluded.
- **Time zone**: time-of-day groups, date boundaries and period masks are all in local time (Europe/Lisbon) with daylight saving applied (2013-10-27 has 25 hours). The manuscript states "in local time".
- **Scope of the contamination check (Alex, 2026-10-13)**: the 11 configuration files and their entire git history (since the first commit 729b651 = prereg-v3), 10 folders of intermediate outputs in work/, all of results/, 16 archives of pre-preregistration versions, shell history. Nowhere is there a trace of use of 2013-07-01 to 11-03. Before the preregistration it is "according to the research record, cannot be confirmed with git". Runs with temporarily edited settings and explorations that opened the raw data inside a chat cannot be checked, and the shell history is incomplete because commands inside tmux are missing.
- **Indirect contamination paths**: (a) the re-acquisition state is determined only by the trajectory and T_max and does not depend on the policy. (b) The 176 sites are built only from the CCTV coordinate file and do not use trajectory data. The trip filter (fewer than 3 points, bbox, 50 m/s) has the same constants since v1, and the data looked at when they were set cannot be confirmed with git. The v1–v10 configurations all read only 2013-11-04 and later. (c) Period assignment is by trip start time. The 17 hops of trips that start on 11-03 and exit on 11-04 drop out of the block 2 evaluation segment, and no hop is duplicated across the two periods.

These values are sample statistics obtained without running any method. Recall and cost are not computed before the lock.

**Split: two blocks, same structure as before** (fixed: both blocks meet the re-acquisition criterion)

| Block | Training (4 weeks) | Calibration (1 week) | Evaluation (4 weeks) | Character |
| --- | --- | --- | --- | --- |
| 1 | 07-01 ~ 07-28 | 07-29 ~ 08-04 | 08-05 ~ 09-01 | Holiday season |
| 2 | 09-02 ~ 09-29 | 09-30 ~ 10-06 | 10-07 ~ 11-03 | Normal period |

- Each block has the same training–calibration–evaluation structure and spacing as the existing three periods. A single long evaluation that uses the predictor unchanged for months would mix in a new condition, predictor aging.
- Block 2 does not use the evaluation period of block 1 for training. However, the two blocks are **two consecutive period blocks** that share the same city, the same taxi population (427, 426 taxis) and the same settings, not two independent replications. They are also earlier in time than the exploratory periods (from 2013-11) on which the settings were chosen. The scope of the claims is limited to "a different period of the same city and the same taxi population".
- **The primary estimates pool the evaluation hops of the two blocks (56 days)**, and per-block estimates are reported alongside.

**Handling of the holiday season (August).** Not excluded. The block 1 evaluation segment almost coincides with August, so block 1 versus block 2 becomes a "holiday season versus normal period" comparison. The interpretation rule is fixed in advance: if the two blocks reach different conclusions, both are reported, the difference is not attributed to season with certainty, and neither block is dropped from the primary result. The block 1 predictor is trained on July traffic, so the change in August is a natural distribution-shift test for online calibration.

**Expected precision** (pre-check values)

In the existing static result for exploratory period 1 (target 0.95, seed 0), the taxi design effect of the re-acquisition group was 1.03–1.07, i.e., almost no cluster effect (Alex). Below are 95% interval half-widths assuming recall equals the target and applying a design effect of 1.07. The per-block values at target 0.95 agree with Alex's report (±0.0105, ±0.0087); the rest were computed by Sean in the same way.

| Sample | hops | t = 0.90 | t = 0.95 | t = 0.98 |
| --- | --- | --- | --- | --- |
| Re-acquisition, block 1 | 1,779 | ±0.014 | ±0.011 | ±0.007 |
| Re-acquisition, block 2 | 2,611 | ±0.012 | ±0.009 | ±0.006 |
| Re-acquisition, combined | 4,390 | ±0.009 | ±0.007 | ±0.004 |
| Smallest cell I6, block 1 | 274 | ±0.037 | ±0.027 | ±0.017 |
| I6, combined | 555 | ±0.026 | ±0.019 | ±0.012 |

- These half-widths do not include seed variation. The design effect was estimated for static with taxi clusters. The actual widths are determined by the bootstrap of §5.2.
- **Design effects of the trial run (exploratory period 1, target 0.95, mvp_log, taxi / day)**: re-acquisition 1.03–1.07 / 0.92, isolation Q4 1.84–1.91 / 4.5–4.6, all 4.3–4.6 / 10.1–11.8. For qr_ogd, isolation Q4 is 1.87–1.88 / 3.3–4.2. That is, for the online methods the larger the group, the larger the day-level correlation, so the day-cluster interval will mostly be the one used. The re-acquisition group, the verdict estimate, has almost no cluster effect. The half-widths in the table above cannot be applied to groups other than re-acquisition.
- Block 1 has about 64 re-acquisition hops per day and block 2 about 93, fewer in August and more in autumn than the planning estimate (about 85 per day).
- In small cells such as intersection I6 the half-width is about ±0.02–0.04. Therefore only the direction of intersections is read (§10.7), and shortfall wording states the upper bound alongside (§10.2).

**Split change rules** (according to the pre-check values, applied only before the lock)

1. If contamination is found, the contaminated dates are removed and the same 4-week, 1-week, evaluation structure is applied to the remaining period.
2. If a block has fewer than 1,500 re-acquisition hops, the two blocks are replaced by a single long evaluation (training 07-01 to 07-28, calibration 07-29 to 08-04, evaluation 08-05 to 11-03) and the evaluation is reported split by month. 1,500 was set before the pre-check. At a design effect of 1.07 the half-width at n = 1,500 is about ±0.011 at t = 0.95 and about ±0.016 at t = 0.90 (the sample size corresponding to a half-width of ±0.02 is about 460–930). Both blocks exceeded the criterion, so this rule was not applied.
3. If any of the 25 groups has fewer than 200 combined evaluation hops, that group is still used for calibration and only its estimate is flagged in the report (the pre-check found no such case).

## 3. What is fixed

**Principle: nothing is changed except dates and targets.** The base configuration `configs/porto_cctv_confirm2.yaml` copies the frozen `configs/porto_cctv_confirm.yaml` (sha256 `0606a4a2…`) and changes only the period entries. The code takes only one target per configuration, and one run computes all methods together (Alex). Therefore 5 targets × 2 blocks = 10 configuration files are generated from the base configuration, and the files differ only in target and period. Seeds are specified in the same way as in the existing post hoc repetitions (seeds 0–4). Alex records the diff between the frozen configuration and each file and the sha256 of every file in the lock commit, and confirms that there is no difference other than period and target.

| Item | Fixed content |
| --- | --- |
| Simulation | 176 sites, observation radius 50 m, Δ = 5 s, T_max = 600 s (B = 120), candidate radius R_cand, perfect detection |
| Predictor | The original predictor (conditional on source site, exit zone, time of day and speed; not outage-aware). For each block, trained on that block's 4 training weeks with the same code and smoothing parameters (λ, ε₀, σ_g) |
| Groups | 25: all 1, time of day 5 (0–6–10–16–20–24 h), track state 3 (continuing, start, re-acquisition), exit speed 4, exit zone 4, branching 4, isolation 4. Quartile boundaries in the same way as the existing code (computed on the block's training segment). Exit zone definition in §8.1 |
| Feedback | Random 30% (ρ = 0.3); the outcome arrives at resolution time (arrival or t_exit + 600 s) |
| mvp_log | Log scale m = 40, a_min = 0.002, normalized form (configuration file). r = 1000 and η = 0.0319 (theoretical value for 25 groups) are not in the configuration file; they are code defaults and theoretical values, so they are fixed by the code commit |
| qr_ogd | Offline quantile regression + online group correction θ. Learning rate as in the existing configuration |
| ACI | The primary ACI is aci_g0005 of the configuration (γ = 0.0005). The other two variants are computed in the same run; they are not used for verdicts in the main text and are shown in the appendix in the same format |
| Initial state | mvp_log: warm start on the whole calibration period of the block (weight 1). ACI: starts from the window of the last 2,000 calibration scores. qr_ogd: starts at θ = 0. static, Mondrian, qr_groups: fitted on the calibration period (as before) |
| Environment | `environment.lock.yml` and the code commit at the time of the lock. Sorting of evaluation hops is the existing code as is (not a stable sort). That results are deterministic for the same input was confirmed by the reproduction of exploratory period 1 (0 differences in 122 summary rows) |

Alex checked the values above against the frozen configuration and confirmed that all agree (2026-10-13). Fitting procedures (Alex, precheck_report2.md A6): static is the split conformal quantile (the ⌊α(n+1)⌋-th) of the calibration-period scores, and the same τ is used for all evaluation hops. Mondrian uses the same quantile in each of the 40 cells of time of day × first hop or not × speed quartile, and cells with fewer than 200 calibration hops use the global τ. qr_groups is a linear quantile regression at quantile level α of the log score on an intercept + baseline-category indicator variables of the 6 attributes, with at most 80,000 hops sampled from the calibration period, solved with HiGHS.

**Compared methods**

| Class | Method | Uses the target | Seed-dependent | Role |
| --- | --- | --- | --- | --- |
| Average target, offline | static (split conformal) | Yes | No | Main comparator |
| Average target, online | ACI (aci_g0005) | Yes | Yes | Main comparator |
| Group-aware, offline | Mondrian (cells of the existing configuration) | Yes | No | Main comparator |
| Group-aware, offline | qr_groups | Yes | Yes (sampling) | Main comparator |
| Group-aware, periodic refit | **qr_groups_refit (new, cumulative window)** | Yes | Yes | Main comparator |
| Group-aware, periodic refit | **qr_groups_refit7 (new, last-7-days window)** | Yes | Yes | Main comparator |
| Group-aware, online | qr_ogd | Yes | Yes | Proposed method |
| Group-aware, online | mvp_log | Yes | Yes | Proposed method |
| Fixed rule | CityTrac-style (cumulative probability target without calibration) | Nominal target | No | Table only |
| Fixed rule | Spatula-style | None (one point) | No | Figure only |

**Definition of qr_groups_refit and qr_groups_refit7 (fixed and pushed before the trial run).** These comparators separate whether an improvement comes from group calibration, from online updating, or from the 30% feedback labels of the evaluation period.

- Model and parameters: the same as qr_groups (same quantile regression formulation, group attributes, sampling). The sampling cap is the 80,000 of the frozen configuration, so the cumulative window is fitted on 80,000 rows even as the data grow (Alex checked). The same seeds are used.
- Refit time: every day at 00:00 during the evaluation period (in the code's time base).
- Fitting data, cumulative window (refit): the whole calibration period of the block and all feedback hops whose outcome has been resolved up to that time. The calibration week is fully labeled and only 30% of the evaluation period arrives, so until the end of the evaluation the calibration week makes up a substantial part of the data.
- Fitting data, 7-day window (refit7): labeled hops whose outcome was resolved in the 7 days just before the refit time. Early in the evaluation this window overlaps the calibration period; from the 8th evaluation day only feedback from the evaluation period remains. A variant that reacts faster to distribution shift.
- Resolution rule and feedback mask are the same as for the other methods with the same seed.
- No tuning: "daily" and "7 days" are values fixed in advance as operationally natural periods. The definition and implementation are committed and pushed **before** the trial run on exploratory period 1, and the trial-run results are committed as they are and shown in the appendix. The period, window or parameters are not changed after seeing the trial results. The manuscript states as a limitation that only one period and two windows were tested.

**Other rules.**

- The four hindsight references (H1–H4, §6.2) are fitted after seeing the outcomes of the evaluation hops, so they are not methods but reference points for cost.
- The other two ACI variants are shown in the appendix in the same format. There is no sentence in the research record giving the reason why γ = 0.0005 was chosen as the primary variant (Alex checked). The manuscript states only that it is the comparison variant fixed in the preregistration, and shows all three variants in the appendix.
- The outage-aware predictor, the log-scale ablation variant and the a_min variants are not included in this experiment. Group-wise ACI, running ACI separately in each Mondrian cell, is not included either, and is stated in the limitations of the manuscript.
- The tuning history per method, Alex's table (precheck_report2.md A9), is shown in the appendix of the manuscript. All of it predates the preregistration and cannot be checked with git; the number of attempts is the number of recorded variants.
- **Sampling cap of the qr_groups family**: qr_max_n = 80,000 of the frozen configuration applies to qr_groups, qr_groups_refit and qr_groups_refit7 alike. The cumulative window is fitted on 80,000 rows even as the data grow. It is a frozen value, so it is not changed, and the manuscript states it.
- **Implementation rules of the refit comparators (Alex, pushed before the trial run)**: a feedback hop is resolved at the arrival time if detected at the τ applied to that hop, otherwise at t_exit + 600 s (the same rule as ACI, MVP, qr_ogd). Calibration hops are resolved at the arrival time. The refit is at 00:00 (Europe/Lisbon) of each evaluation date and applies to the primary predictor only. refit7 uses the calibration and feedback hops resolved in (T − 7 days, T]. These rules are adopted as they are.
- **The CityTrac-style rule** was not in the frozen confirmation configuration and existed only in the exploratory configurations and post hoc scripts. In confirmation 2 it is put in the configuration, and its nominal targets are the five values of §4.
- Items not in the existing code (qr_groups_refit, qr_groups_refit7, H2, recording of detection time, option to exclude duplicate TRIP_IDs) were implemented as options such that the earlier results are reproduced at the defaults (§13.8).

## 4. Target set

**Target set: 1 − α ∈ {0.90, 0.93, 0.95, 0.97, 0.98}**

| Target 1 − α | Miss rate α | Ratio of miss rate to the previous value |
| --- | --- | --- |
| 0.90 | 0.10 | — |
| 0.93 | 0.07 | 0.70 |
| 0.95 | 0.05 | 0.71 |
| 0.97 | 0.03 | 0.60 |
| 0.98 | 0.02 | 0.67 |

**Rationale.** The targets were set on the scale of the miss rate, not of recall. The spacing is almost geometric, with the miss rate shrinking by about 0.6–0.7 each step, so it evenly covers the range where cost rises steeply at high recall. 0.95 was included so that the results can be compared with the existing ones. This set does not decide "which target is right". The target is an input chosen by the operator, and this experiment shows the per-group shortfall and the cost at each target.

**The same set is used for all methods.** static, ACI, Mondrian, qr_groups, qr_groups_refit, qr_ogd, mvp_log and the hindsight references H1–H4 are run and computed separately at each of the five targets. The online methods are independent runs per target (several targets are not extracted from one run).

**Two exceptions.**

- The CityTrac-style rule has no calibration, so the same five values are entered as nominal cumulative probability targets, and the difference between the actual recall and the nominal target is reported as is.
- The Spatula-style rule takes no target, so it appears only as one point in the cost–recall plane.

**Upper-limit check.** The highest target mvp_log can express is 1 − a_min = 0.998. 0.98 is below it, but at miss rate 0.02 the ratio to a_min = 0.002 is 10, so behavior near the lower limit may enter the results. The share of hops that reached a_min is reported with the 0.98 results.

**0.98 is included (decision §13.2).** Because the steep cost increase at high targets is the operationally most important range. Instead, since at miss rate 0.02 the shortfall confidence intervals of small groups such as re-acquisition become relatively wide and behavior near a_min may enter, the a_min reach share above is reported alongside.

**What is not used.** 0.94 was part of the pass mark used in the trial settings, so it is not put in the target set and is not used in result sentences either.

## 5. Primary estimands

**No pass mark is set.** The primary result of this experiment is not "pass/fail" but the per-target, per-group shortfall and its uncertainty. Values such as 0.94 and 1.20 are used neither in tables nor in sentences.

**5.1 Per-group shortfall and seed handling**

For target t = 1 − α, group G, method m and seed s,

> d_G^s(t) = t − R_G^s(t),  D^s(t) = max_G d_G^s(t)

- R_G^s(t) is the share of evaluation hops in group G with seed s in which the target was found. It is computed over all hops of the evaluation period, not only the 30% that received feedback. The hop definition and the resolution rule (arrival or t_exit + 600 s) follow the existing code.
- **Compute per seed first and average afterwards.** The group shortfall is d̄_G(t) = mean_s d_G^s(t), and the worst-group shortfall is D̄(t) = mean_s D^s(t). Taking the maximum of seed-averaged recalls is always less than or equal to the average of the per-seed maxima, which would favor seed-dependent methods over the seed-independent static. What an operator actually experiences is also the result of one seed.
- Seed-independent methods have a single value.
- Positive means short of the target, negative means above the target. Negative values are not truncated either (max(0, ·) is not used; the worst-group shortfall and differences between methods are also computed from untruncated values).
- The primary estimate is the 56-day value pooling the evaluation hops of the two blocks; per-block values are reported alongside.

**5.2 Confidence intervals: two cluster bootstraps, the more conservative at each bound**

- Percentile intervals. The main comparisons (ΔD̄ of §5.5 and the two group differences) use B = 10,000 replicates, the rest B = 2,000. This is because the lower bound of a 99% interval is determined by a few values at the extremes, and at B = 2,000 the classification could change from random numbers alone. Cost ratios, which require refitting the hindsight references, keep 2,000 replicates.
- In each replicate the per-seed values are recomputed on the resampled sample and then averaged over seeds. The 5 seeds are not resampled.
- Two clustering schemes are specified in advance.
  - **Taxi clusters**: resample by the recorded TAXI_ID. The pooled estimate draws the same taxi jointly across the two blocks.
  - **Day clusters**: resample by the date of the hop's exit time, separately within each block (28 per block). For the online methods all taxis share the same calibration state, so correlation may appear across days rather than taxis.
- **For interpretation (§10) the more conservative side is used at each bound.** Of the two cluster intervals, the smaller lower bound and the larger upper bound are taken. Percentile intervals are asymmetric, so a wider interval can have a higher lower bound. Finer clusters such as taxi×day are not used.
- Limitations: day clusters are few (28 per block), so the percentile interval may come out narrower than it should. The bootstrap reflects only the sampling uncertainty of the evaluation hops; it does not include the uncertainty from resampling training and calibration data, nor seed variation. Seed variation is reported separately in §9.3.
- In the trial run before the lock (exploratory period 1), Alex reports the design effects of the two clusterings for the re-acquisition, isolation Q4 and all groups of mvp_log and qr_ogd.

**5.3 Two primary estimands**

1. **Shortfall of the two pre-specified groups**: d̄_G(t) of re-acquisition and isolation Q4, and their differences against the comparators. The groups were not chosen from the results, so there is no selection bias. These two groups were chosen because their shortfall was large in earlier results, and the manuscript states this.
2. **Worst-group shortfall D̄(t)**: a summary over the 25 groups. The maximum of 25 noisy estimates tends to exceed the true value, and groups with small samples are more easily picked as the worst. Also, when the shortfalls of several groups are similar, the bootstrap maximum is biased upward, so the better calibrated a method is, the more inflated its D̄ may look. Therefore D̄(t) is read only as a conservative summary, and the share of times each group was the worst and its sample size are stated alongside.

The shortfall of the all group, i.e., the shortfall of the average recall, is reported alongside.

**5.4 Secondary indicators**

- Number of groups clearly below the target: the number of groups whose one-sided 95% upper bound of recall is below the target. No multiple-comparison correction; used only as a descriptive indicator.
- **Reachable upper bound U_G**: per block and group, 1 − (share of structural-miss hops). A structural miss is a hop for which the predictor gave probability 0 to the actual next camera. The share of hops whose probability is below the minimum threshold of mvp_log is stated alongside.
- If U_G is below the target, the shortfall is split in two: (t − U_G) is the limit of the predictor's candidate set, and (U_G − R_G) is the part by which the method fell short even of that bound. Only the former is described as a predictor limit.
- U_G requires the predictions and outcomes of the new period, so it is computed **only after the lock**.

**5.5 Comparison between methods**

- Main comparisons: for each of mvp_log and qr_ogd, against the six comparators (static, ACI, Mondrian, qr_groups, qr_groups_refit, qr_groups_refit7), (a) the difference in the shortfall of the re-acquisition group, (b) the difference in the isolation Q4 shortfall, (c) ΔD̄(t) = D̄_comparator(t) − D̄_m(t). Built from the same bootstrap samples (paired resampling).
- ΔD̄ is a difference of two maxima, so against static the bias works against the proposed method, but against the group-aware comparators its direction is unknown. Therefore the verdict on the claim sentences (§10.8) uses (a), which has no selection bias, and (c) is shown alongside.
- **Simultaneous intervals over the five targets**: the intervals of the main comparisons are 99% per target (Bonferroni over the five targets). No separate correction is made over comparators and methods (each comparison asks a different question).
- **Seed agreement**: for each cell classified as "improvement" or "worsening", the main-text table states whether the per-seed differences all have the same sign (e.g., 5/5). It is not used as a verdict condition.
- The difference between mvp_log and qr_ogd is reported in the same way but is not used as the basis for a ranking claim (§10.6).
- For the CityTrac-style rule only D̄(t) and its interval are put in the table.

## 6. Cost

**6.1 Absolute cost**

- The unit is camera-seconds per hop (camera·s). Definition in the code (Alex checked): within T_max, all (candidate camera, 5-second slot) pairs whose predicted probability is at least τ are counted, regardless of whether the target was detected, and multiplied by 5 seconds. **The search does not stop when the target is found.**
- So this cost is not the search time actually spent but the size of the search plan fixed in advance for each hop, and the manuscript describes it as **"an upper bound on the actual operating cost"**. The same definition is used for all methods. However, the savings from stopping after detection may differ between methods, so it is not written that the ranking of methods is the same for operating cost.
- **Secondary indicator: cost cut at the detection time.** If the result files have no per-hop detection time, only the record field is added before the lock, and it is checked that the reproduction result of exploratory period 1 (122 summary rows) is unchanged. Adding an output field is not a change of method.
- For each target and method, the mean cost over all evaluation hops is reported. The same table states the mean cost per group and the median and 90th percentile of the cost over all hops. Intervals are built from the same bootstrap samples as §5.2.

**6.2 Four hindsight references**

| Symbol | Name | Definition | What it asks | Use |
| --- | --- | --- | --- | --- |
| H1 | hindsight single threshold | One threshold for all evaluation hops. The largest threshold at which the overall recall is at least t | How much more is spent compared with the cost of matching only the average | Table |
| H2 | single threshold matched to the achieved level | One threshold. The largest threshold at which the overall recall is at least **the overall recall that the method actually achieved** (separately per method and seed, computed for the comparators too) | The additional cost of allocating search by group at the same average recall | Wording |
| H3 | hindsight group-conditional rule (hindsight group quantile regression) | Same definition as reference (b) in the appendix of manuscript M1. The same design as qr_groups (log score, intercept + baseline-category indicator variables of the 6 attributes, 19 coefficients) fitted on all evaluation hops of the block without subsampling. The objective is the check loss at quantile level α = 1 − t, Σ[αu⁺ + (1−α)u⁻], with constraints x'β + u⁺ − u⁻ = y, u⁺, u⁻ ≥ 0. Solved with HiGHS interior point + crossover. An exact optimum would guarantee group recall ≥ t, but in practice it is approximate (held-out period minimum 0.949925, at most 4.55 hops short per group) | Cost compared with a rule fitted per group in hindsight | Wording (main) |
| H4 | simple rule that brings every group to t or above | Reference (a) in the appendix of manuscript M1. For each group, find the largest threshold τ_G at which the recall is at least t; a hop uses the minimum of the τ_G of the groups it belongs to | The cost of the simplest rule that guarantees every group in hindsight | Table |

- H4 treats hops that belong to several groups with the most lenient threshold and so over-searches. Therefore it is not used as the reference for wording and appears only in the table. No reference is called "optimal" or a "lower bound".
- The cost table also has columns for the overall recall and the worst-group shortfall that each of the four references actually achieved. This is so that the reader can see at once whether a ratio divides things with different achieved levels.
- All four references are fitted after seeing the evaluation results, so none is a method that could actually be used.

**6.3 Unit of computation**

- Thresholds are fitted per block on that block's evaluation hops, and the pooled cost adds the two blocks. Because the predictor differs per block, there is no guarantee that the probability scales are the same.
- H1, H2 and H4 are refitted in every bootstrap replicate.
- **H3 (JD decision, 2026-10-14)**: refitting in every replicate would take about 316 hours per block and target (284 s per fit × 2,000 × 2 kinds of cluster), which is infeasible. Decision: (a) in the main analysis the H3 threshold is fixed at the full-sample value, and the interval of the ratio reflects only the sampling variation of cost with that threshold taken as given. Because of this the interval of the ratio to H3 may be narrower than it should be, and the manuscript states this as a limitation. (b) As a sensitivity analysis, only at target 0.95, pooled, taxi clusters, it is refitted in every replicate with B = 100 and how much the interval widens is reported (about 8 hours). 0.95 was chosen for continuity with the earlier results and is not a primary target.
- Ratio = mean cost of the method ÷ mean cost of the reference (same target, same evaluation hops). For seed-dependent methods the ratio is computed per seed and averaged.

**6.4 Reading rules**

- Cost is always read together with shortfall. A method that fell short of the target did not do the same job even if its cost is low. In the tables, the D̄(t) and overall recall of the method are placed next to its cost cell.
- Cost-matched comparisons are shown with the cost curves of §7. No numbers interpolated between target points are produced.
- The cost ratios of the earlier experiment were all relative to the hindsight oracle (H1-type; may be lower by one order statistic because of the finite-sample correction). The mean over seeds 0–4 in the held-out period is mvp_log 1.155, qr_ogd 1.186. "Seed mean 1.27" could not be located in the repository, so it is not used in the manuscript. The periods also differ, so they are not compared directly with these results.

## 7. Figures

The format of the figures is fixed before the lock, and the axes or highlighted items are not changed after seeing the results. The figure code is first drawn on exploratory-period results in the trial run before the lock (§11). All values in the figures are computed per seed and then averaged as in §5.1, and intervals are the more conservative of the two clusterings at each bound.

**F1. Per-group calibration curves (main figure)**

- One small panel per method: static, ACI, Mondrian, qr_groups, qr_groups_refit, qr_groups_refit7, qr_ogd, mvp_log, CityTrac-style.
- x-axis: target 1 − α (0.90–0.98), y-axis: actual recall. The diagonal y = x is drawn as the reference line.
- All 25 groups are drawn as light gray lines, and only the two pre-specified groups (re-acquisition, isolation Q4) are highlighted in color. Even if another group comes out worse in the confirmation results, the highlighted items are not changed.
- Interval bands are drawn for the two highlighted groups and for all. The reachable upper bounds (§5.4) of the two highlighted groups are shown as dotted lines. If the bound exceeds the y-axis maximum, the axis is not extended; instead of the dotted line the caption states "the reachable upper bounds of the highlighted groups are all at least [value]".
- All panels have the same axis ranges.

**F2. Cost curves (main figure)**

- x-axis: mean camera·s per hop (absolute; log scale. Costs are compared as ratios and rise steeply at high targets, so equal ratio differences appear as equal distances. JD decision 2026-10-15), y-axis: worst-group recall t − D̄(t). Each method is a line joining the five targets.
- **Panel A (average-target family)**: static, ACI, CityTrac-style, H1, Spatula-style (one point).
- **Panel B (group-aware family)**: Mondrian, qr_groups, qr_groups_refit, qr_groups_refit7, qr_ogd, mvp_log, H3, H4.
- The two panels have the same axis ranges. static is overlaid on panel B as a light line.
- At each point the intervals of cost and worst-group recall are shown as cross bars.
- H2 is a different reference for each method, so it is not drawn as a curve and appears only in the table.

**F3. Worst-group shortfall against target (secondary figure, main text or appendix)**

- x-axis: target, y-axis: D̄(t) and interval. The two proposed methods and five main comparators.
- A zero line is drawn, but no other reference line (pass mark).

**Per-block figures**

- F1 and F2 are redrawn separately for block 1 (August–September) and block 2 (October–November) and put in the appendix. The main text has the pooled 56-day figures.

**What is not drawn**

- Reference lines or shaded areas such as 0.94 and 1.20.
- Highlighting of groups chosen after seeing the results.

## 8. Alternative partitions and intersections

**Purpose.** The 25 groups are a partition chosen by the researchers. This section checks whether the shortfall stays small also on partitions the methods did not use for calibration, i.e., how much the results depend on the choice of group definitions (Q5). All methods calibrate only with the 25 groups, and the partitions below are used **for evaluation only**.

**8.1 Alternative partitions (fixed in advance)**

| Partition | Cells | Relation to the existing 25 groups | Boundaries |
| --- | --- | --- | --- |
| Time of day, 1 hour | 24 | Subdivides the 5 time-of-day cells | 0–1–…–24 h |
| Time of day, 3 hours | 8 | Misaligned with the existing boundaries (6, 10, 16, 20 h) | 0–3–6–…–24 h |
| Exit zone, 8 directions | 8 | Subdivides the 4 directions | Exit direction angle in 45° steps, starting from the same reference angle as the existing 4 directions |
| Exit speed, quintiles | 5 | Quintiles instead of quartiles | Computed on the block's training segment |
| Branching, quintiles | 5 | Same as above | Same as above |
| Isolation, quintiles | 5 | Same as above | Same as above |

- Exit zone (Alex checked): determined by the position angle from the camera center to the exit point. 0° is east, counterclockwise. The 4 directions are east −45° to 45°, north 45° to 135°, west 135° to 225°, south 225° to 315°. The 8 directions are 45° cells splitting each of the 4 directions in two (boundaries −45°, 0°, 45°, …), so they nest inside the original 4 directions. This definition is followed (JD decision 2026-10-15). The counts of the first pre-check were made with a different definition (center angles 0°, 45°, …); recounted with this definition, the smallest cell is 49,521. Which side boundary values go to follows the existing code.
- Quintile boundaries are computed by the same code path as the quartiles, on the same training segment.
- The pre-check found that every alternative partition cell and every intersection has at least 200 hops per block (§2).

**8.2 Intersections (fixed in advance, 6)**

| No. | Intersection | Reason for choosing |
| --- | --- | --- |
| I1 | Re-acquisition × isolation Q4 | Combination of the two axes with large shortfall in earlier results |
| I2 | Re-acquisition × branching Q4 | Re-acquisition hops with many candidates |
| I3 | Re-acquisition × exit speed Q4 | Re-acquisition hops moving away fast |
| I4 | Start × isolation Q4 | Isolated segment of track-start hops |
| I5 | Exit speed Q4 × isolation Q4 | Combination of two difficulties unrelated to track state |
| I6 | 0–6 h × re-acquisition | Re-acquisition in the time of day with few samples |

- Intersections are not added after seeing the results. Intersections that come to mind after seeing the results are recorded separately as post hoc analyses (POSTHOC) and are marked so in the manuscript as well.
- **Sample size of the intersections.** The pre-check found that every intersection has at least 200 hops per block (minimum I6: 274 / 281). However, the half-width is about ±0.02–0.04, so only the direction is read (§10.7).

**8.3 Reporting**

- Per partition: per-cell shortfall and 95% interval (appendix table), number of cells, number of hops in the smallest cell.
- Partition summary: the maximum shortfall among cells with at least 200 hops and its 95% interval (same approach as §5.3). Cells with fewer than 200 hops are excluded from the maximum and listed separately.
- Intersections: shortfall and 95% interval for each intersection, number of hops.
- All values are computed with the same target set, the same methods and the same bootstrap samples as the primary estimates. The main text has only one partition summary table at target 0.95; the other targets go in the appendix.

**8.4 Limits of interpretation**

The alternative partitions overlap the original partition (1-hour cells fall inside the existing time-of-day cells). Therefore even if the shortfall comes out small here, it is not evidence that "it is calibrated on arbitrary groups"; it is written only as "it did not break down substantially on pre-specified neighboring partitions".

## 9. Seeds

**9.1 What seeds do and do not do**

- The seed changes the randomness inside the methods, that is, which hops receive feedback (ρ = 0.3) and the sampling inside the methods. Running several seeds shows the size of this variation.
- Adding seeds **does not reduce the uncertainty of the sample of evaluated hops.** All seeds evaluate the same hops, so seeds are not treated as independent samples to narrow the intervals. Confidence intervals come only from the two cluster bootstraps of §5.2.

**9.2 What is fixed**

| Item | Content |
| --- | --- |
| Run unit | 5 targets × 2 blocks × seeds. One run computes all methods together |
| Seeds | 0–4 (5). The same seed list for every block and target |
| Methods that depend on the seed | ACI, qr_groups, qr_groups_refit, qr_groups_refit7, qr_ogd, mvp_log (and H2, which is matched per method) |
| Methods that do not depend on the seed | static, Mondrian, CityTrac-style, Spatula-style, H1, H3, H4. They give the same value for every seed, so the value of seed 0 is used. If the values differ, it is treated as a bug and §11.3 applies |

- Feedback mask (checked by Alex): within one run, all feedback methods use the same mask. The mask is determined by the order of the evaluated hops, and the sort is not a stable sort, so the mask can differ if the set of hops differs. In the trial run, the target 0.95 and 0.90 runs with the same seed had exactly the same mask (30.0%), resolution times and hop order. The mask overlap of seeds 0 and 1 is 9.0%, equal to the expected value under independence. The sorting code is not changed.
- The bootstrap random seed is fixed separately from the method seed.

**9.3 Reporting**

- The primary estimand is the mean of the shortfalls computed per seed (§5.1).
- **The main-text table has a seed-range column**: per target, the minimum–maximum over seeds of the worst-group shortfall D^s(t) and of the mean cost. This is the variation an operator running with a single seed would experience.
- For every cell classified as "improvement" or "worsening" in the main comparison, the number of seeds whose difference has the same sign (e.g. 5/5) is given (§5.5).
- The ratio of the seed range to the bootstrap interval width is given alongside. Judgment sentences such as "negligible" are not written.

**9.4 Computation and reduction rules**

- Run time (Alex's estimate): in exploratory period 1, one run took 767 seconds; scaling this by the number of hops of the new period gives about 2.1 hours for one seed (10 runs) and about 10.7 hours for five seeds (50 runs). This is for sequential execution and excludes the data preparation step needed once per block. Re-estimate after the trial run (Alex, 2026-10-14): with the refit comparators included, one evaluation takes about 7,100 seconds alone (qr_groups_refit 4,305 seconds, qr_groups_refit7 2,048 seconds). The 50 runs of the new period take about 100 hours sequentially and about 20 hours with 6 concurrent runs. The analysis takes about 7,000 seconds per block and target (5 seeds, excluding the H3 refit).
- Alternative partitions and intersections re-aggregate the results of the same runs, so there are no additional runs.
- Splitting the runs to execute in parallel is allowed. Since the results are deterministic for the same input, parallel execution does not change the results. The number of seeds, the target set and the blocks are not reduced because of computation.
- **Rationale for the number of seeds.** In the earlier confirmation experiment, the pre-registered run used only seed 0, and the post hoc repetition used seeds 0–4 (checked by Alex). With one seed, seed variation cannot be reported. 0–4 is the same as the post hoc repetition and, since it includes seed 0, can also be set against the pre-registered result (passed both reviews, confirmed by JD (2026-10-14)).

## 10. Interpretation wording per outcome

**Principle.** The frame of the claims (§1) is not changed after seeing the results. Whether each sentence is kept, qualified or deleted is decided by the conditions of §10.8. Classification applies only to differences between methods; there is no classification of the shortfall itself (D̄, d̄). Classifying the shortfall would require a new criterion of "how much is allowed", and that is exactly a pass mark. All intervals use, of the two clusters, **the more conservative one at each bound** (the smaller value for the lower bound, the larger value for the upper bound), and the main comparison uses 99% simultaneous intervals over the five targets (B = 10,000).

**10.1 Classification of differences between methods** (mvp_log and qr_ogd each × five comparators × five targets)

| Class | Condition | Pre-specified wording |
| --- | --- | --- |
| Improvement | The 99% interval of ΔD̄(t) is above 0 | "At target t, [method] reduced the worst-group shortfall relative to [comparator] by [value] (99% interval […])." |
| Not distinguished | The 99% interval of ΔD̄(t) contains 0 | "At target t, the difference in worst-group shortfall between [method] and [comparator] was [value] (99% interval […]), within sampling uncertainty." |
| Worsening | The 99% interval of ΔD̄(t) is below 0 | "At target t, the worst-group shortfall of [method] was larger than that of [comparator] by [value] (99% interval […])." |

- The same classes and wording are used for all three estimands (re-acquisition difference, isolation Q4 difference, ΔD̄). The verdict on the claim sentences uses the re-acquisition difference (§5.5, §10.8), and the other two are reported alongside. If the classes of the re-acquisition difference and of ΔD̄ disagree, that fact is stated in the same sentence.
- All three classes are written in the main text with equal weight. They are not moved to an appendix.

**10.2 Wording for the shortfall itself**

- D̄(t) and d̄_G(t) are always written as "shortfall [value] (95% interval [lower, upper])".
- If the whole interval is below 0, write "exceeded the target".
- Otherwise, "the shortfall may be as large as [upper bound]" must be included in the same sentence. "Not distinguished from the target" is not written without the upper bound, and "achieved" and "guarantees" are not written. This rule also applies to the wording of §10.7 and §10.8 (S4).
- For a group whose reachable upper bound U_G (§5.4) is below the target, the shortfall is written in two parts: "Of the shortfall [value], [t − U_G] is the limit of the predictor's candidate set, and [U_G − R_G] is the part by which the method fell short even of that upper bound." The whole shortfall is not attributed to the predictor's limit.

**10.3 Summary across targets**

- The five targets are not combined into one verdict. If the class differs by target, that range is written as it is. Example: "It was an improvement at t ≤ 0.95 and not distinguished at t ≥ 0.97."
- The summary sentences of the abstract and conclusion must include the upper-bound value of the shortfall. Only the best results of different targets are not picked out.

**10.4 Between the two blocks**

- The comparison between blocks is judged not by whether the classes are the same but by the between-block difference of D̄(t) and its interval. Because block 1 has fewer samples, the classes may differ from a difference in power alone.
- With taxi clusters, the same taxis are drawn jointly in both blocks, so the difference is paired. With day clusters, the dates of the two blocks differ, so the difference is drawn independently per block. The more conservative bound of the two intervals is used.
- If the interval of the difference contains 0, write "the difference between blocks was within sampling uncertainty" even if the classes differ.
- If it does not contain 0, both values are written in the main text and discussed as period dependence. The August holiday season is not asserted as the cause ("one possible explanation").
- Time-of-day groups are in local time (Europe/Lisbon, with daylight saving time), so there is no cell to mark separately in the between-block comparison (§2).

**10.5 Cost wording**

- "At target t, [method] used on average [value] camera·s per hop (an upper bound on the operational cost). This was [ratio] times the hindsight group quantile regression reference (H3) (point estimate; at target 0.95, interval [sensitivity interval] reflecting the threshold uncertainty) and [ratio] times the single threshold matched to the same overall recall (H2) (95% interval […])." The fixed-threshold interval of H3 was 5–12 times narrower than the refit interval in the trial run, so it is not written in the main text and is placed only in the appendix. The ratios to H1 and H4 are given only in the tables. The H2 ratio is also given for the comparators in the same table.
- D̄(t) and the overall recall are written in the same sentence or the next sentence. If the ratio is below 1, first check with D̄(t) whether this is because the method found less, and write that fact as well.
- **Comparison at the same cost (Q3)**: dominance rule — a target point of method A dominates a target point of method B if the upper bound of A's cost interval is below the lower bound of B's cost interval and the lower bound of A's worst-group recall interval is above B's upper bound.
  - The dominance relations between the proposed methods and each comparator are given in a **two-way table** in the appendix.
  - "Finds better at the same cost" is written only when there is a pair in which the proposed method dominates that comparator **and there is no dominance at all in the opposite direction**. Otherwise F2 is only described.

**10.6 Between the two online methods**

- mvp_log and qr_ogd are treated as equals. The difference between them is written only with values and intervals, and no ranking sentences are written.

**10.7 Alternative partitions and intersections**

- For each partition, the judgment is based on the paired difference interval of "maximum shortfall of the partition summary − D̄(t) over the 25 groups" (same method).
  - If it contains 0: "In the pre-specified neighboring partitions, the shortfall was not distinguished from that over the 25 groups (the difference is at most [upper bound])." The limitation of §8.4 is written alongside.
  - If it is above 0: "In the partitions not used for calibration, the shortfall was larger by [value]. The scope of calibration is limited to the specified groups." Even in this case, the groups are not redefined and rerun.
- For intersections I1–I6, only values and intervals are reported, and only the direction is read. The half-widths are of the order of ±0.02–0.04, so they are not used in classification sentences. When writing the shortfall, the upper-bound rule of §10.2 is followed.

**10.8 Conditions for keeping, qualifying or deleting the claim sentences**

Applied to mvp_log and qr_ogd separately, on the pooled 56 days. **The verdict estimand is the difference of the re-acquisition group shortfall** (pre-specified, no selection bias), and the classification follows §10.1 (99% simultaneous intervals, conservative bounds). The class of ΔD̄ is reported alongside in the same sentence, and if the two disagree, that fact is stated. "Majority" means three or more of the five targets.

| Sentence | Condition for keeping and how it is written | If not met |
| --- | --- | --- |
| S1 core (reduction of the shortfall relative to marginal calibration) | "Improvement" at a majority of targets against both static and ACI. The sentence gives the range of targets that were "improvement" and the minimum–maximum difference over that range. If there is a "worsening" at any target, it is stated in the same sentence | If met only against static, qualify to "than offline marginal calibration (static)". If only one method meets it, only that method is the subject. If neither meets it, delete S1 and state only the facts with the wording of §10.1 |
| S1 mechanism clause ("by moving search to hard situations") | In the two pre-specified groups (re-acquisition, isolation Q4), the lower bound of the 95% interval of the method's mean cost ÷ static's mean cost is above 1 at a majority of targets | Delete the mechanism clause |
| S1 addition (relative to offline group calibration) | Not added if "improvement" at a majority against both Mondrian and qr_groups | Append to S1 "relative to offline group calibration ([the comparator concerned]) it was not distinguished (or was the opposite)" |
| S2 (relative to offline group calibration refitted daily) | "Improvement" at a majority against **both** qr_groups_refit and qr_groups_refit7 → "appears" | If either is "worsening" at a majority, "was the opposite". Otherwise write "was not detected", and state that the difference of S1 is not distinguished from the part that comes from using the feedback labels of the evaluation period |
| S3 (cost) | Always written as the ratio to H3 (point estimate and the sensitivity interval at target 0.95) and the ratio to H2 (95% interval). No adjectives | — |
| S4 (shortfall in the rarest situation) | The lower bound (conservative bound) of the 95% interval of the re-acquisition d̄ is above 0 at a majority of targets → "remains", with value and interval | Qualify to "In the earlier evaluation, re-acquisition recall stayed around 0.92, but in the confirmation period the shortfall was [value] (95% interval […], at most [upper bound])". The premise is changed to "in the earlier evaluation" |

- Whenever a sentence is deleted or qualified, that fact is stated in the main text. In S4, if U_G is below the target, the decomposition wording of §10.2 is written alongside.
- No sentence is saved by a criterion outside this table (e.g. the result at one particular target).
- If a bug is confirmed (§11.3), this table is applied both to the results of the locked code and to the results of the corrected version. Only sentences that meet the conditions in both are kept; sentences on which they disagree are qualified, and that fact is stated in the main text.

**10.9 Wording not used**

- Generalizations that this one experiment cannot support, such as "was verified", "proved", "in all situations".
- Adjectives without numbers, such as "greatly", "similar", "stably", "efficient", "cheap".
- "At the same cost" without the dominance rule.
- 0.94, 1.20, or the corresponding pass/fail expressions.

## 11. Procedure

**11.1 Before the lock (Alex)**

1. Copy the base configuration `configs/porto_cctv_confirm2.yaml` from the frozen configuration, changing only the periods, and create with a generation script 10 configurations that differ only in the target (5 targets × 2 blocks). Keep the diff against the frozen configuration as `results/porto_cctv_confirm2/config_diff.txt`. The reanalysis configuration `configs/porto_cctv_heldout_reanalysis.yaml` is also created at this point (§12).
2. One analysis configuration file records the seed list, the bootstrap random seed, B (10,000 for the main comparison, 2,000 otherwise), the two clustering schemes, and the interval levels (95%, 99% for the main comparison).
3. Implement the newly needed code: qr_groups_refit, qr_groups_refit7, H2, recording of the detection time per hop (if absent), shortfall per seed then mean (§5.1), the day-cluster bootstrap and conservative bounds, the reachable upper bound, classification and the evaluation of the §10.8 conditions, the two-way dominance table, figures F1–F3, tables, and `numbers.tex` macros.
4. **After committing and pushing the definitions and implementation of 3**, do the trial run. Run the same code end to end on exploratory period 1 to check that the figures and tables are produced, and report the run time and the design effects of the two clusterings. If the detection-time recording was added, also check that the existing 122 summary rows are reproduced unchanged. The outputs of the trial run are committed as they are and included in the appendix. The definitions or parameters of the methods or comparators are not changed after seeing these results. No method is run on the new period.
5. Fill in the remaining check items of §13.1, and export the plan reflecting all decisions of §13 as `PLAN_confirm2.md`.
6. Push the pre-check commit 072ebfc before the lock. Computational optimization (JD decision 2026-10-15): the thread-count limit is applied. The optimization of reusing per-block repetition results for the pooled estimate is applied only if it preserves the joint resampling of the taxi clusters for the pooled estimate (§5.2) and the outputs are bit-identical on the same trial input. If they are not identical, it is not applied.

**11.2 Lock**

- One commit contains all of the following: `PLAN_confirm2.md`, the base configuration and the 10 generated configurations, the generation script, the reanalysis configuration, the analysis configuration, `environment.lock.yml`, the analysis and simulation code, the outputs of the exploratory period 1 trial run, and `LOCK_confirm2.txt`.
- `LOCK_confirm2.txt` records: the sha256 of each of the above files, the code tree hash (e.g. `git rev-parse HEAD^{tree}`), the sha256 of the raw data CSV and of the preprocessed trip and per-block hop tables, and the push times of 072ebfc and of the comparator implementation commit.
- Attach the tag `confirm2-plan` and push it to the remote repository **before the run**.
- Add the above plan, configurations, script, reanalysis configuration, analysis configuration and `LOCK_confirm2.txt` to the FROZEN list of the pre-commit hook. The results folder is added right after the run-completion commit.
- After the tag, not even one blank line of the plan is changed. If something must be fixed, create a new tag (`confirm2-plan-r2`) before the run and record that fact.

**11.3 Run**

- Run once. The run command, start and end times, code commit and configuration hashes are recorded automatically in `results/porto_cctv_confirm2/run_log.txt`.
- **No summary or aggregation is run before all 50 runs have finished.** This prevents the asymmetry of looking harder for bugs after seeing intermediate results.
- If the run stops midway (memory, power, etc.), rerun with the same command without changing code or configuration. Record both the interruption and the rerun.
- **Errors that die without results** (the new code repeatedly stopping on the new period): may be fixed only while no summary or aggregation has ever been run. Record the fix in `DEVIATIONS.md`, attach a new tag, and rerun.
- **If a bug is found** (during or after the run): notify JD, and record in `DEVIATIONS.md` the fix, when it was found, and the results seen up to then. **The results of the locked code are the primary results.** The results of the corrected version are marked as a deviation and reported together. §10.8 is applied to both results, and only sentences that meet the conditions in both are kept. If, because of the bug, the locked code computed something different from the plan's definitions, that fact is stated in the main text.

**11.4 After the run**

- Right after the results commit, add the results folder to FROZEN and push the tag `confirm2-results`.
- Every analysis not in the plan is recorded in `POSTHOC.md` with date and reason, and marked as "post hoc analysis" in the manuscript.
- Anything done differently from the plan is recorded in `DEVIATIONS.md` regardless of size.
- Numbers in the manuscript enter only through `numbers.tex` macros. They are not transcribed by hand.

**11.5 Roles**

| Stage | Responsible |
| --- | --- |
| Plan draft | Sean |
| Producing the pre-check values (§13.1) | Alex (without running methods on the new period) |
| Incorporating the pre-check values | Sean |
| Independent review | David, and a separate independent critic chat (receives only the plan and the list of periods already used, not the numbers of earlier results) |
| Approval | JD |
| Lock, run, record | Alex |
| Checking the results | Sean (checks the numbers against the result files, checks that the §10 wording is applied) |

## 12. Reanalysis of the earlier held-out period

**Nature.** The earlier held-out period (data 2014-05-05 to 2014-06-30, of which the evaluation segments are 06-09 to 06-30) is a period whose results have already been seen. The reanalysis here is therefore not a confirmation but an **additional analysis**, and in the manuscript it is also marked as "a reanalysis in the new evaluation format of the held-out period already used". The classes of §10 are not changed or reinforced by these results.

**What is kept the same**

- The comparators of §3 (including qr_groups_refit), the target set of §4, the estimands and bootstrap of §5, the cost and the hindsight references H1–H4 of §6, the figure format of §7, the alternative partitions and intersections of §8, and the seed list of §9.
- The training, calibration and evaluation periods and the remaining settings follow the frozen `configs/porto_cctv_confirm.yaml`. The new configuration `configs/porto_cctv_heldout_reanalysis.yaml` copies the frozen configuration, adds only targets, seeds and analysis items, and keeps the diff.

**What is not touched**

- The frozen files (`PREREGISTRATION.md`, `configs/porto_cctv_confirm.yaml`, `results/porto_cctv_confirm/`) are only read. The results are written separately to `results/porto_cctv_heldout_reanalysis/`.

**Reproduction check**

- Among the target 0.95 results of the reanalysis, the values for the same method and same seed as the earlier results must equal the earlier result files. Alex keeps a table comparing the two values; if there is a difference, the cause is found and recorded in `DEVIATIONS.md`. If the difference is not explained and the reanalysis is therefore not used, that fact and the reason are written in the appendix.

**Order**

- Run after the lock of §11, after the results commit of the confirmation run is complete. Since the held-out period is already known, the order does not prevent contamination, but this order is set so that the interpretation is not swayed by seeing the reanalysis before reading the confirmation results.

**Place in the manuscript**

- The reanalysis is placed **only in the appendix**. Placing it side by side with the confirmation results in the main text could dilute weak confirmation results. The main text has only one sentence: "The results of reanalysing the already used held-out period in the same format are in the appendix."

## 13. To be decided before the lock

**13.1 Items checked by Alex**

Done (2026-10-13, commit 072ebfc): contamination check (no date overlap), re-acquisition hops per block (1,779 / 2,611), hop counts of groups, intersections and alternative partitions, precision and taxi design effect, number of taxis, cost definition, exit-zone angles, feedback mask, earlier number of seeds, run time, comparison with the frozen configuration, held-out period dates. The values are reflected in §2, §3, §6.1, §8.1 and §9.

Remaining checks (until the lock):

- [x] Scope of the contamination check (§2)
- [x] The re-acquisition state does not depend on the policy (§2)
- [x] Camera placement uses only the CCTV coordinates. The data seen when the trip filters were set: **cannot be confirmed**. Boundary trips by start time, 17 hops excluded (§2)
- [x] Time of day is in local time (Europe/Lisbon) (§2)
- [x] Duplicate TRIP_ID: no earlier rule → all duplicate records within the period are excluded (general rule). The difference from the held-out period is written in the manuscript (§2)
- [x] The feedback masks of the same seed and different targets are exactly the same (§9.2)
- [x] Fitting of static, Mondrian and qr_groups, list of comparator code, qr_max_n = 80,000 (§3)
- [x] H3 definition and approximation properties (§6.2); refitting at every repetition is infeasible → fixed + sensitivity analysis (§6.3, JD decision)
- [x] The reference of the earlier ratios is of H1 type. "1.27" cannot be identified → not cited (§6.4)
- [x] Per-hop detection-time recording added, difference 0 in reproducing the 122 rows
- [x] No sentence giving the rationale for the ACI γ (cannot be confirmed); tuning history table written (§3)
- [x] Trial run after pushing the implementation (dcc7f9f, b5e10e6), results 7d954a1 (§13.8)
- [x] 072ebfc push: 2026-10-13 14:38:24 −04:00
- [x] Aligning the FROM_PLAN values of the analysis configuration (5 targets, shortfall definition, CityTrac-style target, §10.8, dominance definition) and the sign convention with the plan, implementing the H3 sensitivity analysis, figures F1–F3, numbers.tex (Alex)

**13.2 Decisions**

| Item | Decision | Rationale |
| --- | --- | --- |
| Evaluation structure | Two blocks (28 days each), the pooled 56 days as the primary estimand | A single long evaluation mixes in predictor ageing. The two blocks are two consecutive periods, not independent replications |
| Target set | {0.90, 0.93, 0.95, 0.97, 0.98} | The steep cost increase at high targets is an important range. The reachable upper bound is reported alongside |
| Seeds | 0–4 (5), computed per seed then averaged | With one seed, the variation cannot be seen. The maximum after averaging over seeds favors seed-dependent methods. **Confirmed by JD (2026-10-14)** |
| Comparators | static, ACI, Mondrian, qr_groups, **qr_groups_refit (new)**, all in the main comparison | With static alone, the source of an improvement (group calibration, online updating, additional labels) cannot be separated. Adding comparators is not a change of the proposed methods (JD) |
| Hindsight references | H1–H4. Wording with H3 (primary) and H2, tables with all four | Using only H4 as the reference favors the proposed methods because of over-searching. H3 is the reference of manuscript M1 |
| Main comparison interval | 99% simultaneous interval over the five targets (Bonferroni) | Choosing one primary target conflicts with the aim of removing magic numbers |
| Bootstrap clusters | Taxi clusters and day clusters, the more conservative at each bound | Correlation of the online methods may appear by date. Taxi × day is not used |
| Classification of the shortfall itself | None. Only estimates and upper bounds are written | Classifying would need a tolerance δ, which becomes a new pass mark |
| Claim sentences | Conditions for keeping, qualifying or deleting of §10.8 | A confirmation without a falsification condition is not a confirmation |
| Name of the hindsight group-conditional rule | Used for H3 (hindsight group quantile regression) | David's point 1 |
| Notation of the bootstrap cluster unit | The recorded TAXI_ID | Whether it is the driver or the vehicle cannot be confirmed |
| Duplicate TRIP_ID | All records with a duplicated TRIP_ID within the period are excluded (general rule, JD 2026-10-15) | Passed both reviews |
| Re-acquisition-specific policy | Not included | It would be a change of the proposed methods |
| Reanalysis of the earlier held-out period | Appendix only | Prevents dilution of the confirmation results |

Decisions added after the independent critic's second review (2026-10-13):

- The verdict estimand of the claim sentences is the difference of the re-acquisition group shortfall. ΔD̄ is reported alongside (§10.8).
- Intervals use, of the two clusters, the more conservative one at each bound. B for the main comparison is 10,000 (§5.2).
- The comparator qr_groups_refit7 (most recent 7-day window) is added. S2 is written as "appears" only when it is an improvement against both refit variants (§3, §10.8).
- Group-wise ACI is not included and is written among the limitations (§3).

**13.3 What the second review looks at (independent critic, changed sections only)**

1. Do the conditions of §10.8 actually make the claims falsifiable? Is the "majority" criterion appropriate?
2. Do the seed handling of §5, the rule of the wider of the two clusters, and the 99% simultaneous intervals solve the problems raised?
3. Are H1–H4 and the wording rules of §6 fair?
4. Is the definition of qr_groups_refit (daily, cumulative window, no tuning) fair as a comparator? Was a weak comparator built in favor of the proposed methods?
5. Are the lock list and the bug rules of §11 sufficient?

**13.4 Approval record**

| Stage | Date | Note |
| --- | --- | --- |
| Sean draft | 2026-10-13 | Pre-check report not yet received |
| JD decisions, round 1 | 2026-10-13 | Evaluation structure, 0.98, taxi clusters, independent critic, etc. |
| Alex pre-check 1 | 2026-10-13 | Commit 072ebfc (push 14:38:24) |
| David independent review | 2026-10-13 | Based on rev 30. Required 3, recommended 4, for reference 4 |
| Independent critic, first review | 2026-10-13 | Based on rev 30. Required before the lock 9 |
| JD decisions, round 2 | 2026-10-13 | Hindsight references H1–H4, 99% simultaneous intervals, qr_groups_refit added |
| Sean, first incorporation | 2026-10-13 | rev 40, §13.6 |
| Independent critic, second review | 2026-10-13 | Based on rev 40. Required before the lock 5 |
| Sean, second incorporation | 2026-10-13 | rev 49, §13.7 |
| Alex pre-check 2, implementation, trial run | 2026-10-14 | dcc7f9f, b5e10e6, 7d954a1 (§13.8) |
| JD decisions, round 3 | 2026-10-14 | Seeds 0–4 confirmed, H3 fixed + sensitivity analysis |
| Alex finishing the analysis code |  | Done 2026-10-14 to 15. ddae528 (FROM_PLAN and sign convention, pushed before the trial), c2ad171 (analysis, figures, macros), 94cf171 (trial outputs) |
| JD approval |  |  |
| Alex lock (tag, hashes) |  |  |
| JD decisions, round 4, and final approval | 2026-10-15 | Plan definition of the 8 directions, general rule for duplicate TRIP_ID, H3 main-text wording (point estimate + sensitivity interval), F2 log axis, F1 upper-bound explanation rule, conditions for the computational optimization. This version is exported as PLAN_confirm2.md and locked |

**13.5 Order up to the lock**

1. Alex does the remaining checks of §13.1 and the new code implementation and trial run. No method is run on the new period. If the re-acquisition definition depends on the policy, stop here.
2. The independent critic's second review is finished (§13.7). Only the incorporation results (§13.6) are shared with David.
3. Sean incorporates Alex's values and the second review. Items not incorporated have their reasons written in §13.6.
4. JD approves.
5. Alex locks according to §11.2, pushes the tag, and runs once.

**13.6 Record of incorporating the independent reviews** (two reviews based on rev 30)

| Point | Source | Handling | Place of incorporation or reason |
| --- | --- | --- | --- |
| The hindsight group reference favors the proposed methods | David 1, critic 4-1 | Incorporated | H1–H4, wording with H3 and H2 (§6.2, §10.5) |
| Computation unit of the hindsight references | Critic 4-2 | Incorporated | Per block, refitted at every repetition (§6.3) |
| Definition of the hindsight threshold | David 6 | Incorporated | "the largest threshold that gives t or more" (§6.2) |
| Day-level correlation | David 2, critic 3-4 | Incorporated | The wider of taxi and day clusters (§5.2). Weekly clusters not adopted because there are too few clusters (4 per block) |
| Scope of the contamination check and indirect paths | David 3, critic 2-1 | Incorporated | §2, §13.1 (checked by Alex) |
| Block comparison method | David 4, critic 3-2 | Incorporated | Paired difference interval (§10.4) |
| Reachable upper bound | David 5 | Incorporated | §5.4, F1, §10.2 |
| 072ebfc push | David 7, critic 1-4 | Incorporated | §11.1, §11.2 |
| Time of day UTC | David 8, critic 2-4 | Incorporated | UTC stated, time-of-day cells marked in the block comparison (§2, §10.4) |
| Fairness of the cost definition | David 9, critic 4-3 | Incorporated | "upper bound on the operational cost"; if detection times exist, the truncated cost as an auxiliary metric (§6.1) |
| Structure of classification 1 | David 10, critic 3-2 | Incorporated in modified form | Instead of 1a/1b, the classification of the shortfall itself was removed. δ is not set because it would become a new pass mark. The wording for exceeding the target is kept (§10.2) |
| Conflict between the premise and the confirmation result | David 11 | Incorporated | S4 condition (§10.8) |
| Per-seed range column | David (seed item) | Incorporated | §9.3 |
| No falsification condition | Critic 1-1 | Incorporated | §1, §10.8 |
| Verdict rule of Q3 | Critic 1-2 | Incorporated | Lowered to a descriptive item, only the dominance rule allowed (§10.5) |
| Undefined judgment words | Critic 1-3 | Incorporated | §10.7, §9.3 |
| Lock targets, outdated sentences | Critic 1-4 | Incorporated | §11.2, §0 |
| Primary result under bug handling | Critic 1-5 | Incorporated | §11.3 |
| ACI variants | Critic 1-6 | Incorporated | All three variants in the appendix (§3) |
| Place of the held-out period reanalysis | Critic 1-7 | Incorporated | Appendix only (§12) |
| Same city and taxi population | Critic 2-2 | Incorporated | "two consecutive period blocks", scope of the claims limited (§2) |
| Tuning level of the comparators | Critic 2-3 | Incorporated | Tuning history table (§3) |
| Maximum after averaging over seeds | Critic 3-1 | Incorporated | Computed per seed then averaged (§5.1). The 5 seeds are not resampled; the range is reported separately |
| Bootstrap of the maximum | Critic 3-3 | Partly incorporated | The two pre-specified groups as joint primary estimands (§5.3). Simultaneous upper bounds per group not adopted because the gain is small relative to the complexity |
| No primary target | Critic 3-5 | Incorporated | 99% simultaneous interval (§5.5) |
| Rationale sentence for 1,500 | Critic 3-6 | Incorporated | §2 |
| The main comparison is against the weakest reference | Critic 5-1 | Incorporated | All five comparators in the main comparison, qr_groups_refit added (§3, §5.5) |

**13.7 Record of incorporating the independent critic's second review** (based on rev 40)

| Point | Handling | Place of incorporation or reason |
| --- | --- | --- |
| 1-1 Verdict estimand not decided | Incorporated | Verdict by the re-acquisition group difference, ΔD̄ alongside (§5.5, §10.8) |
| 1-2 Value and target of S1 not decided | Incorporated | Range of improved targets and minimum–maximum, worsening reported alongside (§1, §10.8) |
| 1-3 Comparisons without a verdict rule | Incorporated | Condition for the mechanism clause, additional wording for Mondrian and qr_groups, the "was the opposite" branch of S2 (§10.8) |
| 1-4 Reachable bound and reporting the upper bound | Incorporated | Decomposition of the shortfall, upper-bound rule in §10.7 and S4, computed only after the lock (§5.4, §10.2) |
| 2-1 Asymmetry problem of "the wider one" | Incorporated | The more conservative at each bound (§5.2, §10) |
| 2-2 B = 2000 insufficient for 99% intervals | Incorporated | B = 10,000 for the main comparison (§5.2) |
| 2-3 Seed variation | Incorporated | Number of sign agreements reported, not a verdict condition (§5.5, §9.3) |
| 2-4 Outdated sentences | Incorporated | §9.1, §2, §10.4 (day clusters are not paired) |
| 3-1 H3 definition | Incorporated (content by Alex) | Definition written as sentences in the plan, achieved-recall and shortfall columns per reference, reference of 1.27 checked (§6.2, §6.4, §13.1) |
| 3-2 H2 in S3 | Incorporated | §1, §10.5; H2 is also computed for the comparators |
| 3-3 One-directional dominance rule | Incorporated | Two-way table; sentence forbidden if there is opposite dominance (§10.5) |
| 3-4 Recording detection times | Incorporated | If absent, a recording item added before the lock (§6.1) |
| 4-1 Weakness of the cumulative window | Incorporated | qr_groups_refit7 added, S2 based on both variants, sampling cap checked (§3, §10.8) |
| 4-2 Locking the definitions before the trial run | Incorporated | Trial run after the implementation commit and push, outputs in the appendix (§3, §11.1) |
| 4-3 Group-wise ACI | Not adopted | Written among the limitations. ACI and the two refit variants were judged sufficient as online comparators (§3) |
| 5-1 Disagreement between the locked and corrected results | Incorporated | §10.8 applied to both (§10.8, §11.3) |
| 5-2 Contradiction in the ACI variant sentences | Incorporated | Fixed table in §3 |
| 5-3 Omissions in the lock list | Incorporated | Reanalysis configuration and trial-run outputs added, rule for errors that die without results (§11.2, §11.3) |
| 5-4 Numbers of earlier results | Incorporated | Numbers removed from the H4 description (§6.2) |

**13.8 Trial run record and observations (exploratory period 1, to be made public)**

Time order (−04:00, Alex's report):

1. 10-13 12:54 Run-time measurement with the existing methods only (before implementing the refit comparators)
2. 10-13 16:19 Supplementary instruction received → 16:27:52 implementation dcc7f9f pushed (comparator definitions fixed before the trial run)
3. 16:28 First trial run, interrupted by a power cut → 10-14 10:18 restarted, 12:17 detection-time check failed → recording code fixed, b5e10e6 pushed
4. 12:18 Three runs started concurrently, 14:29 finished → 15:22 results 7d954a1 pushed

Observations (target 0.95, 2 seeds, summary of Alex's report):

- The runs are the three (target, seed) = (0.95, 0), (0.95, 1), (0.90, 0), and the analysis used the 2 seeds of target 0.95. These are reference values not used for any verdict.
- mvp_log improved on static, ACI, Mondrian and qr_groups in all of (a)(b)(c), with 2/2 seeds agreeing.
- **mvp_log was worse than qr_groups_refit7.** (a) The re-acquisition shortfall was larger by 0.0107 (99% conservative interval [0.0016, 0.0174]). (c) is in the same direction. The (a) difference against qr_groups_refit was +0.0041 [−0.0066, 0.0117], not distinguished. qr_ogd is also on the side of not distinguished or worsening against the two refit variants.
- Cost (seed mean, camera·s/hop): mvp_log 394.3, qr_groups_refit 376.7, qr_groups_refit7 396.4, static 311.3. Ratio to H1: mvp_log 1.154 [1.106, 1.204], qr_groups_refit7 1.160.
- Recall / worst-group shortfall of H1–H4: H1 0.9500 / 0.0581, H3 0.9501 / 0.0002, H4 0.9643 / 0.
- The methods, comparators and verdict conditions are not changed after seeing these observations. The trial-run outputs are included in the appendix as they are. The exploratory period is data already used, so this is not contamination of the new evaluation period.
- Implementation note: Alex's implementation computes the difference as (method − comparator), so negative is improvement. This is the opposite sign to the plan's ΔD̄ = D̄_comparator − D̄_m (positive is improvement), so the final tables follow the plan's sign.
