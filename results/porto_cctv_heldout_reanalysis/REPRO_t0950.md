# §12 재현 확인: 보류 기간 재분석, 목표 0.95 (2026-10-18)

- 비교: 재분석 `runs/t0950/s<k>/` 대 기존 시드 반복 `results/porto_cctv_confirm_posthoc/seeds_prereg25/seed_<k>/`, 평가 시드 0–4, 두 구간(test_jun_a, test_jun_b), 공통 (예측기, 방법, 구간) 행 10개 × 2구간. 스크립트 `heldout_repro_check.py`, 상세 `repro_t0950.csv`, `repro_t0950_hits.csv`.
- hop별 결과(`hits.parquet`): 공통 열 160쌍(시드 × 열) 중 160쌍이 비트 단위로 같다.
- 최악 그룹 이름: 100칸 모두 같다.
- 시드 0은 동결 결과 `results/porto_cctv_confirm/summary.csv`와도 공통 122행의 모든 열이 같다(차이 0).

| 열 | 비교 칸 | 차이 있는 칸 | 최대 절대 차이 |
|---|---|---|---|
| cost_mean_cam_s | 100 | 0 | 0 |
| cost_median_cam_s | 100 | 0 | 0 |
| coverage | 100 | 0 | 0 |
| coverage_detected | 100 | 0 | 0 |
| frac_below | 100 | 0 | 0 |
| n | 100 | 0 | 0 |
| n_groups_sig_below_bar | 100 | 50 | 1 |
| roll_p05 | 100 | 0 | 0 |
| target_used | 100 | 0 | 0 |
| worst_group_cov | 100 | 0 | 0 |
| worst_group_n | 100 | 0 | 0 |
| worst_group_ub95 | 100 | 0 | 0 |

- **n_groups_sig_below_bar 차이의 원인:** 기존 시드 반복은 사전 등록 25개 그룹 정의로 재집계했고(`posthoc_seeds.py --groups prereg_25`), 재분석은 동결 설정의 as-run 26개 그룹(첫 hop 여부 포함, 전체 없음)으로 집계한다(D1). hop별 결과는 같다.
