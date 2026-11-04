"""POST HOC (external review, instruction 04 §1): sign check of every stored hop cost that passed the uncapped cost lookup.

    python posthoc_review_diag04.py

Read only; nothing is rerun and no frozen file is changed. Writes review/diag04/:
  cost_sign_all.csv     every run output in work/review_cache/runs/ x cost column: run id, method/variant, block, target,
                        seed, hops, negative / zero / NaN cost hops, minimum, and the tau > 1.5 count (thresholds are not
                        stored in these outputs: "not stored")
  frozen_inputs.csv     confirmation-2 frozen results (results/porto_cctv_confirm2/runs/, analysis predictor): per block,
                        range of the stored per-hop score and taumin0.002 (the thresholds H1, H2, H4 and a_min take are
                        stored scores or taumin), largest probability in the block's cost lookup, and per method in the
                        analysis set the negative-cost hop count of the evaluate.py cost columns over the 25 runs
"""
import re

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

import posthoc_review_common as C

OUT = C.OUT / "diag04"
RUN = re.compile(r"(block\d)_t(\d{4})_s(\d)(?:__(.+))?\.parquet$")


def review_runs():
    R = []
    for f in sorted((C.CACHE / "runs").glob("*.parquet")):
        b, t, s, suf = RUN.match(f.name).groups()
        cols = [c for c in pq.read_schema(f).names if c.startswith("cost|")]
        X = pd.read_parquet(f, columns=cols)
        for col in cols:
            c = X[col].to_numpy(np.float64)
            R.append({"run_id": f.stem, "file": suf or "methods", "method": col[5:], "block": b, "target": int(t) / 1000,
                      "seed": int(s), "hops": len(c), "n_neg": int((c < 0).sum()), "n_zero": int((c == 0).sum()),
                      "n_nan": int(np.isnan(c).sum()), "cost_min": float(np.nanmin(c)), "n_tau_gt_1p5": "not stored"})
    return pd.DataFrame(R)


def frozen_inputs():
    A = yaml.safe_load(open("configs/confirm2_analysis.yaml"))
    p = A["predictor"]; methods = A["proposed"] + A["comparators_main"]
    R = []
    for b in C.BLOCKS:
        dirs = sorted(d for d in C.RUNS.glob(f"{b}/t*/s*") if d.is_dir())
        H = pd.read_parquet(dirs[0] / "hits.parquet", columns=[f"score|{p}", f"taumin0.002|{p}"])
        z = np.load(dirs[0] / f"cost_lookup_{p}.npz")
        pmax = max(float(z[f"v{int(k)}"].max()) for k in z["kid"])
        neg = {m: 0 for m in methods}; hops = 0
        for d in dirs:
            X = pd.read_parquet(d / "hits.parquet", columns=[f"cost|{p}|{m}" for m in methods])
            hops += len(X)
            for m in methods:
                neg[m] += int((X[f"cost|{p}|{m}"].to_numpy() < 0).sum())
        sc = H[f"score|{p}"].to_numpy(); tm = H[f"taumin0.002|{p}"].to_numpy()
        R.append({"block": b, "predictor": p, "runs": len(dirs), "hops_per_run": len(H), "score_min": float(sc.min()),
                  "score_max": float(sc.max()), "taumin_min": float(tm.min()), "taumin_max": float(tm.max()),
                  "lookup_p_max": pmax, "hops_all_runs": hops, **{f"neg_cost|{m}": neg[m] for m in methods}})
    return pd.DataFrame(R)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = review_runs(); D.to_csv(OUT / "cost_sign_all.csv", index=False)
    print("files", D.run_id.nunique(), "rows", len(D), "neg hops", D.n_neg.sum(), "nan hops", D.n_nan.sum(),
          "min", D.cost_min.min())
    print(D.groupby("file").agg(files=("run_id", "nunique"), cols=("method", "size"), neg=("n_neg", "sum"),
                                nan=("n_nan", "sum"), cmin=("cost_min", "min")).to_string())
    F = frozen_inputs(); F.to_csv(OUT / "frozen_inputs.csv", index=False)
    print(F.T.to_string())


if __name__ == "__main__":
    main()
