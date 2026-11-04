# Calibrating Recall Across Operational Situations in Cross-Camera Target Search — code, plans and results

This repository is the snapshot that accompanies the paper below. It holds the code, configuration files, analysis
plans fixed before the analyses they govern, the record of departures from those plans, and the result files from
which every number of the paper is generated. It has no version history; the full history is available to the editor
on request.

## Citing

> J. Lee and J. Lee, "Calibrating Recall Across Operational Situations in Cross-Camera Target Search," manuscript
> submitted to IEEE Access, 2026. [JOURNAL/YEAR/DOI to be updated on publication]

Repository snapshot: https://doi.org/10.5281/zenodo.23934654 (reserved; resolves after publication).

## Contents

| Path | What it is |
|---|---|
| `PREREGISTRATION.md` (+ `_en.md`) | Pre-registration of the earlier confirmation experiment (git tag `prereg-v3` in the authors' history) |
| `notes/instructions/PLAN_confirm2.md` (+ `_en.md`) | Analysis plan of confirmation experiment 2, revision 72 (the confirmation period of the paper) |
| `LOCK_confirm2.txt`, `LOCK_confirm2_addendum.txt` | Lock record of that plan: SHA-256 of the plan, configurations, code and data checks at the lock |
| `results/porto_cctv_confirm2_posthoc/review/REVIEW_PLAN.md` (+ `_en.md`) | Plan of the analyses added after the confirmation results were known (post hoc) |
| `DEVIATIONS.md` (+ `_en.md`) | Departures from the plans and corrections |
| `POSTHOC.md` | List of the post hoc analyses of the earlier evaluation |
| `ccpilot/` | Library: events and hops (`events.py`), visibility predictor (`predictors.py`), marginal calibration (`calibration.py`), group calibration incl. MVP and online quantile regression (`multigroup.py`), evaluation (`evaluate.py`) |
| `run_pilot.py`, `confirm2_*.py`, `heldout_reanalysis_execute.py`, `posthoc_*.py`, `exploratory/` | Pipeline, confirmation experiment 2, held-out re-analysis, post hoc analyses |
| `configs/` | All configuration files (`configs/confirm2/` = the 10 generated run files of confirmation experiment 2) |
| `results/` | Result files (CSV, JSON, parquet summaries, reports). `results/porto_cctv_confirm2/` = confirmation experiment 2 |
| `manuscript_generators/` | Scripts that turn the result files into the paper's number macros, tables and figures (`scripts/`), their outputs (`generated/`, each macro with its source file, filter, formula and commit), and the bundle of additional tables `supplementary_tables/supplementary_tables.pdf` cited by the paper |
| `environment.yml`, `environment.lock.yml` | Conda environment (the lock file is the exact environment used, linux-64) |
| `data/porto/porto_cctv.json` | Porto traffic-camera positions (third-party, CC0 1.0; see Data) |
| `docs/renumber/` | Cross-references of the bundle against the numbering of the paper (`bundle_to_paper.md`) |
| `LICENSE`, `LICENSE-docs` | MIT License (code), CC BY 4.0 (documents and results) |

Files in `_en.md` are English translations of documents written in Korean. The originals are authoritative and are
included unchanged; each translation states the SHA-256 of its original. Internal run reports under `results/` are
partly in Korean and are not translated. The locked analysis code keeps three Korean strings (see note 1).

The bundle `manuscript_generators/supplementary_tables/supplementary_tables.pdf` was compiled from an earlier
manuscript revision; its cross-references to supplementary table and section numbers follow that revision.
`docs/renumber/bundle_to_paper.md` maps them to the numbers of the paper.

Links to internal pages in the frozen documents (for example the first line of `PLAN_confirm2.md`) are not publicly
accessible; the frozen files are kept unchanged.

## Top-level scripts

The layout is that of the authors' working repository, kept unchanged so that the paths in `LOCK_confirm2.txt` and in
the result files resolve.

| Script | Role |
|---|---|
| `run_pilot.py` | Pipeline: data, events (hops and visibility sets) and evaluation for one configuration |
| `select_primary.py` | Pre-registered selection rule of the primary method (`PREREGISTRATION.md`, section 3) |
| `factor_analysis.py` | Factor analysis of misses on an exploratory period |
| `confirm2_lock_prep.py` | Lock preparation of confirmation experiment 2: data hashes and duplicate-trip exclusion counts |
| `confirm2_lock.py` | Writes `LOCK_confirm2.txt` from the staged lock commit (plan §11.2) |
| `confirm2_addendum.py` | Writes `LOCK_confirm2_addendum.txt` (camera-hash correction, `DEVIATIONS.md` D4) |
| `confirm2_taxi_map.py` | TAXI_ID per trip for the confirmation period (`DEVIATIONS.md` D5) |
| `confirm2_attributes.py` | Per-hop attributes of the alternative partitions (plan §8.1) |
| `confirm2_execute.py` | Executes confirmation experiment 2: data and events checked against the lock, then the 50 runs |
| `confirm2_run.py` | One evaluation run (configuration, target, evaluation seed) |
| `confirm2_analysis.py` | Analysis of confirmation experiment 2 (locked): shortfalls, cluster bootstrap, comparisons, verdicts, hindsight references, costs |
| `confirm2_h3_sensitivity.py` | Cost ratio to H3 with H3 refitted in every bootstrap replicate (plan §6.3) |
| `confirm2_figures.py` | Figures F1–F3 of the plan from the analysis output |
| `confirm2_numbers.py` | Number macros from the analysis output (plan §11.4) |
| `confirm2_report.py` | `results/porto_cctv_confirm2/REPORT.md`: numbers and verdicts from the result files |
| `heldout_reanalysis_execute.py` | Re-analysis runs of the earlier held-out period (plan §12) |
| `heldout_repro_check.py` | Reproduction check of that re-analysis |
| `posthoc_regrade.py` | Regrades the earlier confirmation run under the pre-registered group definitions |
| `posthoc_seeds.py` | Post hoc: evaluation-seed repetition of the earlier confirmation run |
| `posthoc_sensitivity.py` | Post hoc: sensitivity analyses of the earlier confirmation run (feedback share and other settings) |
| `posthoc_frontier.py` | Post hoc: cost-matched comparison (cost against worst-group recall) |
| `posthoc_cluster.py` | Post hoc: cluster bootstrap of group recall on the earlier held-out period |
| `posthoc_geometry.py` | Post hoc: sensitivity to the observation radius and the horizon T_max |
| `posthoc_group_oracle.py` | Post hoc: hindsight references that satisfy the group condition |
| `posthoc_scale_ablation.py` | Post hoc: ablation of `mvp_log` on the exploratory periods |
| `posthoc_qrogd_bound.py` | Post hoc: realized values of the `qr_ogd` inequality on the earlier held-out period |
| `posthoc_taumin_nature.py` | Post hoc: what the lower threshold tau_min is |
| `posthoc_v_trajectory.py` | Post hoc: whether negative ledger values accumulated during saturation cause later over-search |
| `posthoc_outage.py` | Post hoc stress test: camera outage |
| `posthoc_outage_aware.py` | Post hoc: outage-aware predictor under camera outage |
| `posthoc_outage_ceiling.py` | Post hoc: per-hop analysis of the outage-aware runs |
| `posthoc_outage_diag.py` | Post hoc: diagnosis of adaptation lag under camera outage |
| `posthoc_outage_suite.py` | Post hoc: outage suite across periods |
| `posthoc_outage_suite_report.py` | Post hoc: summary of the outage-suite runs |
| `posthoc_exit_split.py` | Post hoc: split of the hop loss under camera outage |
| `posthoc_region_diag.py` | Post hoc: diagnosis of groups below the bar under a region outage |
| `posthoc_oa_oracle_groups.py` | Post hoc: cost of outage-aware `mvp_log` relative to the hindsight oracle after an outage |
| `posthoc_custody_confirm2.py` | Post hoc: track custody on the confirmation runs |
| `posthoc_custody_decomp_confirm2.py` | Post hoc: decomposition of track custody by how a chain starts |
| `posthoc_review_common.py` | Post hoc (`REVIEW_PLAN.md`): shared helpers |
| `posthoc_review_p0.py` | Post hoc (`REVIEW_PLAN.md`) step P0: recomputed calibration scores and cost lookups, reproduction check |
| `posthoc_review_methods.py` | Post hoc (`REVIEW_PLAN.md`): per-run thresholds of the added methods (parts A, B without refits, C) |
| `posthoc_review_labels.py` | Post hoc (`REVIEW_PLAN.md`): label sets (iii) and (iv) |
| `posthoc_review_refit.py` | Post hoc (`REVIEW_PLAN.md`): daily-refitted group quantile regression under censored feedback, and the C refit |
| `posthoc_review_summary.py` | Post hoc (`REVIEW_PLAN.md`): estimates and cluster-bootstrap intervals for per-hop outcomes |
| `posthoc_review_report.py` | Post hoc (`REVIEW_PLAN.md`): estimates and intervals per part, and their collection |
| `posthoc_review_tables.py` | Post hoc (`REVIEW_PLAN.md`): aggregate tables, macros and the mechanical consequence check |
| `posthoc_review_lookups.py` | Post hoc (`REVIEW_PLAN.md`): look-ups and macros from stored results |
| `posthoc_review_b7.py` | Post hoc (`REVIEW_PLAN.md` appendix B7): consequences of label set (v) |
| `posthoc_review_diag03.py` | Post hoc (`REVIEW_PLAN.md`): diagnosis of the negative cost ratios of label set (iii) |
| `posthoc_review_diag04.py` | Post hoc (`REVIEW_PLAN.md`): sign check of the stored hop costs |
| `posthoc_review_prereapproval.py` | Post hoc (`REVIEW_PLAN.md`): inventory of the runs made before the plan's re-approval (deviation R1) |
| `posthoc_review_runs02.py` | Post hoc (`REVIEW_PLAN.md`): run table and cache manifest |
| `posthoc_review_runsR3.py` | Post hoc (`REVIEW_PLAN.md`): run table of the reruns of deviation R3 |

## Frozen documents

Check that a frozen file is unchanged with `sha256sum <file>`:

| File | SHA-256 |
|---|---|
| `notes/instructions/PLAN_confirm2.md` | `b23b9b748c54b6944f5ba9043119e6de8fe3af58e8a7a0a2ab825be9c7a0c4f7` (= `plan_sha256` in `LOCK_confirm2.txt`) |
| `PREREGISTRATION.md` | `58797642ef68b055df63e8abdd5578813b88fa30e1931b44e260947766ed36dd` |
| `LOCK_confirm2.txt` | `4b765eb7a5d230f00e4c538e4b0942ad5ba792afc1ae59cad977064c87fab206` |

`LOCK_confirm2.txt` lists the SHA-256 of every configuration and code file at the lock; the files in this snapshot can
be checked against it file by file (`sha256sum -c` on the listed lines). The tree hashes in its header refer to the
authors' git history and cannot be recomputed from this snapshot.

## Data

1. **Porto taxi trajectories** (ECML/PKDD 2015 challenge; not included), UCI Machine Learning Repository dataset 339,
   https://doi.org/10.24432/C55W25. Put `train.csv` at `data/porto/train.csv`.
2. **Porto traffic-camera positions** (included as `data/porto/porto_cctv.json`, Município do Porto, CC0 1.0):
   GeoJSON of the former Porto open-data portal, retrieved via the Internet Archive snapshot of 2025-07-09,
   https://web.archive.org/web/20250709151743/https://opendata.porto.digital/dataset/9320b636-ef46-4200-9138-f7bf162d249b/resource/17b0bdd2-fd58-4b81-a8e7-a4e6fb222154/download/ext-sistema-de-gestao-de-trafego-cctv-geojson.geojson
   (license CC0 1.0 on the current dataset page, https://dadosabertos.cm-porto.pt/dataset/sistema-de-gestao-de-trafego-cctv).
   SHA-256 `a0bd2e31799fd9542bfd6069b56bda66b0b85eac313a591971261f3c2b5b88d1`.

## Reproducing

```bash
conda env create -f environment.lock.yml      # or environment.yml (unpinned)
conda activate ccpilot
python run_pilot.py --config configs/synthetic.yaml --stage all     # smoke test on synthetic data (about a minute)
```

**Confirmation experiment 2** (plan §11; the confirmation period of the paper, July 1 to November 3, 2013):

```bash
python confirm2_execute.py          # data and events checked against the lock, then 50 runs (5 targets x 2 blocks x seeds 0-4)
python confirm2_analysis.py --block block1 <the 25 run directories of block 1> --block block2 <the 25 of block 2> \
    --taxi-map block1 <taxi_map.parquet> --taxi-map block2 <...> --attr block1 <attributes.parquet> --attr block2 <...> \
    --out <dir> --reachable      # taxi maps: confirm2_taxi_map.py; attributes: confirm2_attributes.py; settings: configs/confirm2_analysis.yaml
python confirm2_figures.py --analysis <dir> --out <dir>
python confirm2_numbers.py --analysis <dir> --out <dir>/confirm2_numbers.tex
```

The run files are `configs/confirm2/`, the runs write `results/porto_cctv_confirm2/runs/`, and
`results/porto_cctv_confirm2/run_log.txt` records every run command with its code commit. The exact invocation of
`confirm2_analysis.py` was not logged; the blocks, seeds, B, and threads are in
`results/porto_cctv_confirm2/analysis/analysis_log.json`. A full analysis took about 11 hours with 8 threads.

**Held-out re-analysis** (plan §12): `python heldout_reanalysis_execute.py`, then `confirm2_analysis.py` on its runs.

**Post hoc analyses** of the confirmation period: `posthoc_review_*.py` as specified in `REVIEW_PLAN.md`
(`posthoc_review_report.py --collect`, then `posthoc_review_tables.py`); of the earlier evaluation: `POSTHOC.md`.

**Numbers, tables and figures of the paper**: in `manuscript_generators/`, with this repository as `CCPILOT_REPO`,
`python scripts/make_numbers.py`, `make_confirm2_numbers.py`, `make_confirm2_tables.py`, `make_confirm2_appendix.py`,
`make_confirm2_appendixB.py`, `make_gate8_tables.py`, `make_fig1_2panel.py`. `make_numbers.py` also reads
`data/porto/train.csv` and the camera file.

Do not run `run_pilot.py` with `configs/porto_cctv_confirm.yaml`: it overwrites `results/porto_cctv_confirm/`, the
frozen results of the earlier confirmation experiment. Analyses of that period use the `posthoc_*.py` scripts.

## Notation in code and paper

- MVP buckets: the paper writes the bucket index as $\ell \in \{1, \dots, m\}$ ($m = 40$) and the ledger as
  $V_{G,\ell}$; the algorithm listing of the bundle (Algorithm R1) writes $i$ and $V_{G,i}$. In
  `ccpilot/multigroup.py`, `MVP.bucket(q)` returns the 0-based index ($\ell - 1$) used for `MVP.V[g, b]`, and
  `MVP.choose` uses the 1-based `i_star`.
- $\mathbb{1}[\cdot]$ (Algorithm R1) is the indicator function: 1 if the condition holds, 0 otherwise.
- The paper's "post-gap" hop (first hop after an exit within the same trip) is called "re-acquisition" (`reacq`,
  `hopkind = 2`) in the plans, code and result files.

## License

- Code (`.py`, `.sh` and configuration files): MIT License, see `LICENSE`.
- Documents, analysis plans, deviation records, translations, `docs/`, everything under `results/` and `figures/`,
  and the generated tables, figures and number files under `manuscript_generators/`: Creative Commons Attribution 4.0
  International (CC BY 4.0), see `LICENSE-docs`.
- Third-party data keep their own licenses: `data/porto/porto_cctv.json` is CC0 1.0 (Município do Porto); the taxi
  trajectories (not included) are distributed by the UCI Machine Learning Repository under its terms.

## Notes

1. `confirm2_analysis.py` is part of the locked code (`LOCK_confirm2.txt`) and is kept byte for byte. Line 57 holds a
   note string in Korean and English (H3NOTE, also written to the `note` column of `cost_ratios.csv`), and lines
   676–677 hold the three verdict words of statement S2, "나타난다" (appears), "반대였다" (was the opposite) and
   "검출되지 않았다" (was not detected), which appear in `results/porto_cctv_confirm2/analysis/claims_10_8.csv`.
   The table generator (`manuscript_generators/scripts/make_confirm2_tables.py`) reads this verdict word as a
   dictionary key.
