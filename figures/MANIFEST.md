# 논문 그림 후보

실행별 그림은 git에서 제외했다(`.gitignore`: `results/*_posthoc/**/*.png`, `results/*_regrade/**/*.png`). 이 폴더에는 논문 후보 그림의 **복사본**만 둔다. 최종 선택은 David와 JD가 한다.

- 모두 분석용 초안 스타일이다. 라벨 겹침, 색 체계, 글꼴을 논문 양식으로 맞추려면 다시 그려야 한다.
- 출처 커밋은 원본 그림을 마지막으로 커밋한 해시다. 원본 파일은 로컬 `results/`에 남아 있다.
- `--analyze-only` 명령은 git에서 제외된 로컬 parquet(실행별 hop 결과·스냅숏)가 있어야 동작한다. 없으면 `--analyze-only` 없이 실행해 다시 만든다(약 10분).
- 장애 인지 예측기, 세 기간 무작위 장애, 고정 region, 탐색 기간 절제는 아직 그림이 없다(표만 있음). 필요하면 `outage_suite/all_periods_summary.csv`에서 그린다.

| 파일 | 내용 | 원본 | 출처 커밋 | 구분 | 재생성 명령 |
|---|---|---|---|---|---|
| `main/fig1_conditional_coverage_confirm.png` | 확인 실험(사전 등록 실행): 주 예측기의 그룹별 탐지율, 방법별 | `results/porto_cctv_confirm/conditional_src_zone_hour_speed.png` | `e77fb0a` | as-run 26개 그룹 축 | `python run_pilot.py --config configs/porto_cctv_confirm.yaml --stage eval (실행 금지: 동결 폴더를 덮어씀. 그림은 확인 커밋의 산출물)` |
| `main/fig2_cost_matched_test_a.png` | 비용 대비 최악 그룹·전체 탐지율 곡선, 평가 A (사전 등록 25개 그룹) | `results/porto_cctv_confirm_posthoc/frontier_prereg25/frontier_test_jun_a.png` | `221ae36` | 사후 | `python posthoc_frontier.py --config configs/porto_cctv_confirm.yaml --groups prereg_25` |
| `main/fig2_cost_matched_test_b.png` | 같은 곡선, 평가 B | `results/porto_cctv_confirm_posthoc/frontier_prereg25/frontier_test_jun_b.png` | `221ae36` | 사후 | `python posthoc_frontier.py --config configs/porto_cctv_confirm.yaml --groups prereg_25` |
| `main/fig3_outage_recovery_0621.png` | 카메라 장애(none, rand10, region 6개 지점) 후 6시간 단위 평균·최악 그룹 탐지율 | `results/porto_cctv_confirm_posthoc/outage_diag/fig_recovery_20140621.png` | `0b3321a` | 사후, 기본 예측기 | `python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml --analyze-only` |
| `main/fig4_saturation_mvp_log.png` | mvp_log 최상위 버킷 포화 비율(장애 시작 06-21, 06-12) | `results/porto_cctv_confirm_posthoc/outage_diag/fig_saturation_mvp_log.png` | `0b3321a` | 사후 | `python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml --analyze-only` |
| `supp/figS1_custody_confirm_a.png` | 확인 실험: hop 수에 따른 추적 유지율, 평가 A | `results/porto_cctv_confirm/custody_test_jun_a.png` | `e77fb0a` | 사전 등록 실행 | `확인 커밋의 산출물` |
| `supp/figS2_rolling_coverage_confirm.png` | 확인 실험: 이동 창 탐지율 | `results/porto_cctv_confirm/rolling_coverage.png` | `e77fb0a` | 사전 등록 실행 | `확인 커밋의 산출물` |
| `supp/figS3_warm_ablation_mvp_log_0621.png` | warm start 절제(가중치 1, 0.1, 0), mvp_log. 원인 진단용이며 방법 수정 아님 | `results/porto_cctv_confirm_posthoc/outage_diag/fig_warm_mvp_log_20140621.png` | `0b3321a` | 사후, 진단용 | `python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml --analyze-only` |
| `supp/figS4_warm_ablation_mvp_global_0621.png` | warm start 절제, mvp_global | `results/porto_cctv_confirm_posthoc/outage_diag/fig_warm_mvp_global_20140621.png` | `0b3321a` | 사후, 진단용 | `python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml --analyze-only` |
| `supp/figS5_outage_start_compare.png` | 장애 시작일(06-21, 06-12)별 평균 탐지율 | `results/porto_cctv_confirm_posthoc/outage_diag/fig_start_compare.png` | `0b3321a` | 사후 | `python posthoc_outage_diag.py --config configs/porto_cctv_confirm.yaml --analyze-only` |
