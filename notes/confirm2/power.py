"""confirm2 precheck A4: pass probability of candidate judgement rules (normal approximation).

    python notes/confirm2/power.py

Uses only existing held-out results (results/porto_cctv_confirm_posthoc/cluster_ci/, posthoc_cluster.py) and the
hop counts of the candidate splits (notes/confirm2/split_group_counts.csv). Nothing is computed on the candidate
period beyond those counts.

Model per group G (mvp_log, 25-group definition): the group recall estimate is p_hat ~ N(p, s_h^2 + s_seed^2),
s_h^2 = DE * p(1-p) / n_G. The rule's bound is computed from s_h only (a cluster bootstrap captures hop sampling,
not the evaluation seed):
  R1  upper end of the two-sided 95% interval >= 0.94 :  p_hat + 1.960 s_h >= 0.94
  R2  one-sided 95% lower bound >= 0.94                :  p_hat - 1.645 s_h >= 0.94
  R3  point estimate >= 0.94                           :  p_hat >= 0.94
  R4  one-sided 95% lower bound >= 0.93                :  p_hat - 1.645 s_h >= 0.93
Every group is set to the same true recall p (worst case: all 25 groups at p). Joint probability = product over
groups and segments, i.e. assumes independence between groups (they overlap; see precheck.md).

Design-effect variants (DE per group, mvp_log, held-out seed 0):
  ind    DE = 1
  obs    DE = max(taxi DE, day DE), each averaged over segments A and B (as measured on 10-12-day segments)
  proj   taxi DE projected with a constant intra-taxi correlation: DE' = 1 + (DE_taxi - 1)(m' - 1)/(m - 1),
         m = hops per taxi (n_G / 436 taxis in the held-out period; the same taxi count is assumed), then
         max with the day DE
Seed variants: none, or s_seed = mvp_log seed-to-seed SD of the group (held-out seeds 0-4, RMS over A and B).
Segments: k = 1 (whole evaluation range) or k = 2 (two halves, n_G / 2 each; both must pass).
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "results/porto_cctv_confirm_posthoc/cluster_ci"
OUT = ROOT / "notes/confirm2"
N_TAXI = 436
PS = [0.95, 0.945, 0.94, 0.93]
RULES = {"R1": (0.94, -1.960), "R2": (0.94, 1.645), "R3": (0.94, 0.0), "R4": (0.93, 1.645)}


def pass_prob(p, n, de, s_seed, bar, z):
    s_h = np.sqrt(de * p * (1 - p) / n)
    s_t = np.sqrt(s_h ** 2 + s_seed ** 2)
    return norm.cdf((p - z * s_h - bar) / s_t)        # P(p_hat - z s_h >= bar)


def main():
    R = pd.read_csv(CI / "cluster_ci.csv")
    R = R[R.method == "mvp_log"]
    D = R.groupby("group").agg(n_held=("n", "mean"), de_taxi=("taxi_de", "mean"), de_day=("day_de", "mean"))
    SD = pd.read_csv(CI / "seed_sd.csv")
    SD = SD[SD.method == "mvp_log"].groupby("group").sd.apply(lambda s: np.sqrt((s ** 2).mean()))
    D["seed_sd"] = SD
    N = pd.read_csv(OUT / "split_group_counts.csv").pivot(index="group", columns="split", values="eval_hops")
    D = D.join(N)
    D["de_obs"] = D[["de_taxi", "de_day"]].max(axis=1)
    m_held = D.n_held / N_TAXI
    rows = []
    for split in N.columns:
        for k in (1, 2):
            n = D[split] / k
            m_new = n / N_TAXI
            de_proj = np.maximum(1 + (D.de_taxi - 1) * (m_new - 1) / (m_held - 1), D.de_day)
            for dev, de in (("ind", 1.0), ("obs", D.de_obs), ("proj", de_proj)):
                for sv in ("none", "seed"):
                    ss = D.seed_sd if sv == "seed" else 0.0
                    for p in PS:
                        for rule, (bar, z) in RULES.items():
                            pr = pd.Series(pass_prob(p, n, de, ss, bar, z), index=D.index)
                            rows.append({"split": split, "segments": k, "de": dev, "seed_var": sv, "p": p,
                                         "rule": rule, "p_reacq": float(pr["hopkind=2"] ** k),
                                         "p_joint": float(np.prod(pr.to_numpy()) ** k)})
    P = pd.DataFrame(rows)
    P.to_csv(OUT / "power.csv", index=False)
    D.round(5).to_csv(OUT / "power_inputs.csv")
    pd.set_option("display.width", 250)
    print(D.round(4).to_string())
    main_ = P[(P.de == "obs") & (P.seed_var == "none")]
    print(main_.pivot_table(index=["split", "segments", "p"], columns="rule", values=["p_reacq", "p_joint"]).round(3).to_string())


if __name__ == "__main__":
    main()
