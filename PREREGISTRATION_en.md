<!-- English translation for the public snapshot (instruction 28 §3a, 2026-11-03). Translation only: the original
     PREREGISTRATION.md (in Korean) is authoritative and unchanged.
     Original SHA-256 58797642ef68b055df63e8abdd5578813b88fa30e1931b44e260947766ed36dd, last changed in commit b6195be, git tag prereg-v3 (frozen). -->

## 1. Background (what was learned in the exploratory phase)

- Exploratory data: Porto taxi 2013-11 to 2014-01, 2014-02 to 04. Analyzed with a virtual placement and with the real CCTV placement. All of it was used for method design, so it is treated as exploratory results.
- Average-based calibration (static, split conformal) and ACI mostly keep the average recall, but fall systematically short in specific condition groups (worst group about 0.88 to 0.90).
- Which conditions are hard depends on the camera placement. In the virtual placement, the exit speed was the largest factor; in the real CCTV placement, the isolation and the branching of the departure camera were.
- Cell-partition calibration fixes only the specified conditions. Among the methods that handle several groups at once, MVP kept the worst group at about 0.94 over all segments of the exploratory period.

## 2. Fixed items

| Item | Content |
|---|---|
| Confirmation data | Porto taxi 2014-05-05 to 2014-06-30 (never used in earlier analyses) |
| Split | training 05-05 to 06-01, calibration 06-02 to 06-08, evaluation A 06-09 to 06-20, evaluation B 06-21 to 06-30 |
| Configuration file | `configs/porto_cctv_confirm.yaml` — 0606a4a20906624cc9300c1192072fbd41d7c088b326ad55bf3bb4672703e9eb |
| Code | The hash of a code archive at the time of fixing is also recorded: `________________` |
| Cameras | Porto traffic-management CCTV (2025 data), 238 cameras → 176 sites after merging within a 50 m radius. One tunnel camera excluded |
| Target recall | 0.95 (α = 0.05) |
| Feedback | 30% of ordinary vehicle transitions, applied at the time the outcome is settled (arrival or t_exit + 600 s) |
| Groups (25) | all 1 + time of day 5 + hop kind 3 + exit speed 4 + exit zone 4 + branching 4 + isolation 4. The bin edges of speed, branching and isolation are the quartiles of the training period |
| Groups judged | groups with at least 200 samples in each evaluation segment |
| Primary predictor | `src_zone_hour_speed` (secondary: `src_zone_speed`) |
| Candidate methods | `mvp_groups`, `mvp_log`, `qr_groups`, `qr_ogd` |
| Comparison methods | `static`, `mondrian_hour_hop_speed`, `aci_g0005`, `mvp_global`, `oracle(post-hoc)`, `spatula_rule` |

## 3. Rule for selecting the primary method (applied before the confirmation experiment)

The primary method is selected **before the confirmation experiment**, from the results of the five evaluation segments of the two exploratory runs (`porto_cctv`, `porto_cctv_replication`), by the following rule.

1. Keep only the candidates with `n_groups_sig_below_bar = 0` (no group whose 95% confidence-interval upper bound is below 0.94) in all five segments.
2. Of these, keep only the candidates whose mean cost over the five segments is at most 1.20 times that of `oracle(post-hoc)`.
3. Of the remaining candidates, the one with the lowest mean cost over the five segments is the primary method, and the second is the secondary method.
4. If no candidate passes 1 and 2, the candidate with the lowest cost among those passing 1 is the primary method, and the criterion of C2 (1.20 times) is kept as it is, without a preregistration deviation.
5. (v3 addition) If there is no second candidate under rule 3, the secondary method is, among the other candidates passing rule 2, the one with the fewest segments violating rule 1, and on a tie the one with the highest lowest worst-group recall over the five segments.

**Selection result (2026-09-28, `select_primary.py`, primary predictor src_zone_hour_speed)**

| Candidate | Segments violating rule 1 | Lowest worst group | Mean cost / oracle | Result |
|---|---|---|---|---|
| mvp_log | 0 | 0.928 | 1.19 | **primary method** |
| qr_ogd | 1 | 0.920 | 1.19 | **secondary method** (rule 5) |
| qr_groups | 1 | 0.910 | 1.07 | — |
| mvp_groups | 0 | 0.937 | 1.95 | eliminated by rule 2 |

## 4. Hypotheses and decision criteria

| No. | Type | Content | Verdict |
|---|---|---|---|
| C1 | primary | Primary method: in every judged group, the upper bound of the 95% Wilson confidence interval of the recall ≥ 0.94 (`n_groups_sig_below_bar = 0`) | supported if met in both evaluation A and B |
| C2 | primary | Primary method: mean over evaluation A and B of the ratio (mean cost / mean cost of `oracle(post-hoc)`) ≤ 1.20 | supported if met |
| C3 | secondary | `static`: worst-group point estimate ≤ 0.93 (reproduction of the problem) | supported if met in both evaluation A and B |
| C4 | secondary | The secondary method (qr_ogd) meets C1 and C2 | judged in the same way as C1 and C2 |
| C5 | descriptive | Price of the conditional guarantee (primary method cost / oracle cost), worst-group point estimate and that group | reported as numbers |

The primary verdict is based on the primary predictor. The secondary predictor is reported only as a robustness check. The worst-group point estimate is also reported.

## 4-1. Revision history (before the confirmation experiment was run)

- **v3, 2026-09-28.** (1) Changed the computation of C2 from "at most 1.20 times in each evaluation segment" to "mean of the ratios of evaluation A and B at most 1.20 times". The rule for selecting the primary method (rule 2) judges by the ratio averaged over segments while C2 judged per segment, so the computations of the two criteria did not match. The criterion value (1.20) was not changed. For reference, the per-segment ratios of the selected method in the exploratory period were 1.12, 1.18, 1.22, 1.24, 1.21. (2) Added rule 5, which handles the case of no second candidate under rule 3, and determined the secondary method. (3) The criterion of C1 (confidence-interval upper bound 0.94) was not changed.

## 5. Decision rules by result

- **C1, C2 supported:** The selected multigroup calibration is fixed as the core method of the paper.
- **C1 supported, C2 not supported:** Reported as a trade-off between the conditional guarantee and the cost.
- **C1 not supported:** The groups below the bar and possible causes (sample size, delayed feedback, bucket resolution) are analyzed, but every later adjustment is stated as post hoc analysis.
- **C3 not supported:** Reported as the problem appearing weakly in the confirmation period, and the strength of the motivation is toned down.

## 6. Known limitations (stated in advance)

- The theoretical guarantee of MVP assumes immediate and complete feedback. This experiment has delayed and partial feedback, so it does not formally apply. The group-wise properties of `qr_ogd` were not formally proven either.
- The guarantee is the long-run empirical recall per group. It is not a guarantee for an individual target that deliberately avoids cameras.
- The camera positions (2025) and the taxi trajectories (2013 to 2014) are from different times.
- Detection and re-identification are assumed to be perfect. The 15-second GPS is interpolated linearly, and no map matching was applied.
- The feedback share of 30% is an assumption. A sensitivity analysis (10%, 100%) is reported separately after the confirmation experiment (stated as post hoc analysis).
- June 2014 may include World Cup matches and the Porto St. John festival (June 23 to 24). The dates need checking; including this period in evaluation B was decided in advance.
