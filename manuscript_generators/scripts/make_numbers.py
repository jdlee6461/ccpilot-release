"""Generate paper/generated/numbers.tex: every number used in the manuscript, as LaTeX macros.

    python scripts/make_numbers.py          (run from paper/; `make numbers` does this)

Rules (instructions step 2):
  * values are read from the confirmation config, the code (defaults and constants) and result files only;
  * every macro carries a comment with its source: file, row filter, column, formula, and the ccpilot commit that
    last changed the source file (not HEAD, so repeated runs give identical output);
  * rounding: recall 3 decimals, cost ratios 2 decimals, percentages 1 decimal, counts integers;
  * also writes generated/numbers_manifest.csv (name, value, raw value, source) for check_claims.py.
"""
import csv
import inspect
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))   # work copy outside ccpilot: CCPILOT_REPO=/home/user/ccpilot
sys.path.insert(0, str(REPO))
from ccpilot.multigroup import MVP, _K_eps  # noqa: E402

CONFIG = "configs/porto_cctv_confirm.yaml"
MACROS = []   # (name, text value, raw value, source comment)


def commit_of(path):
    out = subprocess.run(["git", "log", "-1", "--format=%h", "--", path], cwd=REPO, capture_output=True, text=True)
    return out.stdout.strip() or "untracked"


def commit_of_paper(path):
    out = subprocess.run(["git", "log", "-1", "--format=%h", "--", path], cwd=PAPER, capture_output=True, text=True)
    return out.stdout.strip() or "untracked"


def add(name, text, raw, source, path=None):
    assert name.isalpha() and name[0].islower(), name
    assert name not in {m[0] for m in MACROS}, name
    src = source + (f" | commit {commit_of(path)}" if path else "")
    MACROS.append((name, text, raw, src))


def r3(x):
    return f"{x:.3f}"


def r2(x):
    return f"{x:.2f}"


def pct(x):
    return f"{100 * x:.1f}"


def main():
    cfg = yaml.safe_load(open(REPO / CONFIG, encoding="utf-8"))
    ex, ev = cfg["eval"], cfg["events"]
    mvp_cfg = next(v for v in ex["multigroup"]["mvp_variants"] if v["name"] == "mvp_log")
    mvp_def = {k: v.default for k, v in inspect.signature(MVP.__init__).parameters.items()
               if v.default is not inspect.Parameter.empty}
    C = f"{CONFIG}"

    # ---------------------------------------------------------------- settings
    add("targetRecall", f"{ex['target_recall']:.2f}", ex["target_recall"], f"{C}: eval.target_recall", CONFIG)
    add("alphaTarget", f"{1 - ex['target_recall']:.2f}", 1 - ex["target_recall"], f"{C}: 1 - eval.target_recall", CONFIG)
    add("candRadius", f"{ex['candidate_radius_m']:g}", ex["candidate_radius_m"], f"{C}: eval.candidate_radius_m (metres)", CONFIG)
    add("shrinkLambda", f"{ex['model']['lam']:g}", ex["model"]["lam"], f"{C}: eval.model.lam", CONFIG)
    e0 = ex["model"]["eps"]; e0exp = int(round(np.log10(e0)))
    assert abs(e0 - 10.0 ** e0exp) < 1e-15
    add("shrinkFloor", f"\\ensuremath{{10^{{{e0exp}}}}}", e0, f"{C}: eval.model.eps", CONFIG)
    add("smoothWidthBins", f"{ex['model']['sigma_bins']:g}", ex["model"]["sigma_bins"], f"{C}: eval.model.sigma_bins (bins)", CONFIG)
    add("binWidth", f"{ev['bin_s']:g}", ev["bin_s"], f"{C}: events.bin_s (seconds)", CONFIG)
    add("horizon", f"{ev['t_max_s']:g}", ev["t_max_s"], f"{C}: events.t_max_s (seconds)", CONFIG)
    add("feedbackFraction", f"{ex['aci']['feedback_fraction']:g}", ex["aci"]["feedback_fraction"], f"{C}: eval.aci.feedback_fraction (rho)", CONFIG)
    add("aciWindow", f"{ex['aci']['window']:g}", ex["aci"]["window"], f"{C}: eval.aci.window (W)", CONFIG)
    aci = {v["name"]: v for v in ex["aci_variants"]}
    add("aciGamma", f"{aci['aci_g0005']['gamma']:g}", aci["aci_g0005"]["gamma"],
        f"{C}: eval.aci_variants[name=aci_g0005].gamma (variant kept in post-hoc runs)", CONFIG)
    add("aciGammaAlt", f"{aci['aci_g001']['gamma']:g}", aci["aci_g001"]["gamma"], f"{C}: eval.aci_variants[name=aci_g001].gamma", CONFIG)
    mcells = ex["mondrian"]["mondrian_hour_hop_speed"]
    add("minCellHops", f"{ex['min_group_n']:d}", ex["min_group_n"], f"{C}: eval.min_group_n (Mondrian fallback and group reporting minimum)", CONFIG)
    q = ex["multigroup"]["qr_max_n"]; qexp = int(np.floor(np.log10(q))); qman = q / 10 ** qexp
    assert qman == int(qman)
    add("qrSubsampleMax", f"\\ensuremath{{{int(qman)}\\times10^{{{qexp}}}}}", q, f"{C}: eval.multigroup.qr_max_n", CONFIG)
    add("mvpBuckets", f"{mvp_cfg.get('m', mvp_def['m']):d}", mvp_cfg.get("m", mvp_def["m"]), f"{C}: mvp_variants[mvp_log].m", CONFIG)
    add("mvpR", f"{mvp_cfg.get('r', mvp_def['r']):d}", mvp_cfg.get("r", mvp_def["r"]),
        "ccpilot/multigroup.py: MVP.__init__ default r (not set in config)", "ccpilot/multigroup.py")
    add("mvpEpsilon", f"{mvp_cfg.get('eps', mvp_def['eps']):g}", mvp_cfg.get("eps", mvp_def["eps"]),
        "ccpilot/multigroup.py: MVP.__init__ default eps (not set in config)", "ccpilot/multigroup.py")
    a_min = mvp_cfg["a_min"]
    add("aMin", f"{a_min:g}", a_min, f"{C}: mvp_variants[mvp_log].a_min", CONFIG)
    og = ex["multigroup"]["qr_ogd"]
    add("qrOgdGamma", f"{og['gamma']:g}", og["gamma"], f"{C}: eval.multigroup.qr_ogd.gamma", CONFIG)
    add("qrOgdClip", f"{og['clip']:g}", og["clip"], f"{C}: eval.multigroup.qr_ogd.clip (offsets clipped to [-clip, clip])", CONFIG)

    # group structure from the confirmation run's per-hop results
    H = pd.read_parquet(REPO / "results/porto_cctv_confirm_regrade/hits.parquet",
                        columns=["hgroup", "hopkind", "speed_bin", "zone", "entropy_bin", "nn_bin", "grp_all", "hopfirst"])
    dims = ex["multigroup"]["dims"]
    levels = {d: H[d].nunique() for d in dims}
    HP = "results/porto_cctv_confirm_regrade/hits.parquet"
    n_groups = 1 + sum(levels.values())
    add("numGroups", f"{n_groups:d}", n_groups, f"{C}: eval.multigroup.dims + 'all'; levels counted in {HP} (test hops)")
    add("groupsPerHop", f"{1 + len(dims):d}", 1 + len(dims), f"{C}: 1 + len(eval.multigroup.dims)", CONFIG)
    add("numAttributes", f"{len(dims):d}", len(dims), f"{C}: len(eval.multigroup.dims)", CONFIG)
    prod = int(np.prod(list(levels.values())))
    add("productCells", f"{prod:d}", prod, f"product of levels of {dims} in {HP}: " + "*".join(str(levels[d]) for d in dims))
    mond = int(np.prod([H[c].nunique() for c in mcells]))
    add("mondrianCells", f"{mond:d}", mond, f"{C}: eval.mondrian.mondrian_hour_hop_speed={mcells}; product of levels in {HP}")

    # ---------------------------------------------------------------- derived (code formulas)
    m = mvp_cfg.get("m", mvp_def["m"]); eps = mvp_cfg.get("eps", mvp_def["eps"]); alpha = 1 - ex["target_recall"]
    add("mvpBucketWidth", f"{1 / m:.3f}", 1 / m, "1/m")
    add("alphaMinusBucket", f"{alpha - 1 / m:.3f}", alpha - 1 / m, "alpha - 1/m (uniform scale, one bucket below the target miss level)")
    add("alphaPlusBucket", f"{alpha + 1 / m:.3f}", alpha + 1 / m, "alpha + 1/m (one bucket above)")
    add("logBucketFactor", f"{a_min ** (1 / m):.3f}", a_min ** (1 / m), "a_min^(1/m)")
    K = _K_eps(eps)
    add("kEps", f"{K:.2f}", K, "ccpilot/multigroup.py: _K_eps(eps) = sum_{n<1e6} f(n)^-2 + integral tail 1/(eps ln(1e6)^eps)", "ccpilot/multigroup.py")
    eta_g = np.sqrt(np.log(n_groups * m) / (2 * K * n_groups * m)); eta_1 = np.sqrt(np.log(m) / (2 * K * m))
    add("etaGroups", f"{eta_g:.4f}", eta_g, "sqrt(ln(|G| m) / (2 K_eps |G| m)), |G| = numGroups (ccpilot/multigroup.py MVP eta='theory')")
    add("etaGlobal", f"{eta_1:.4f}", eta_1, "same with |G| = 1 (mvp_global)")
    c = np.sqrt(4 * K * n_groups * m * np.log(n_groups * m))
    add("mvpConstC", f"{c:.0f}", c, "c = sqrt(4 K_eps |G| m ln(|G| m)), natural log")
    f = lambda n: np.sqrt((n + 1) * np.log(n + 2) ** (1 + eps))
    for word, n in [("TenFour", 1e4), ("TenSix", 1e6), ("TenSeven", 1e7)]:
        v = c * f(n) / n
        add(f"mvpBoundAt{word}", f"{v:.2f}", v, f"c f(n)/n at n = {n:.0e}, f(n) = sqrt((n+1) ln^(1+eps)(n+2)), natural log")

    # ---------------------------------------------------------------- ablation, exploratory periods, no outage
    rows = []
    for label, per in [("First", "porto_cctv"), ("Second", "porto_cctv_rep")]:
        p = f"results/{per}_posthoc/scale_ablation/scale_ablation_summary.csv"
        T = pd.read_csv(REPO / p)
        T = T[T["mode"] == "normal"].groupby("method")["cost_over_oracle"].mean()
        rows.append((label, p, T))
    variants = [("UnifNoCap", "unif_nocap"), ("UnifCap", "unif_cap002"), ("LogCap", "mvp_log"),
                ("LogNoCap", "log_cap1e6"), ("LogNoCapMatched", "log_cap1e6_m89"),
                ("LogCapLow", "log_cap001"), ("LogCapHigh", "log_cap005")]
    for vn, meth in variants:
        vals = []
        for label, p, T in rows:
            add(f"abl{vn}Ratio{label}", r2(T[meth]), T[meth],
                f"{p}: mode=normal, method={meth}; mean over test segments of cost_over_oracle", p)
            vals.append(T[meth])
        add(f"abl{vn}RatioMean", r2(np.mean(vals)), np.mean(vals), "mean of the two exploratory-period values above")
    for label, p, T in rows + [("Mean", None, None)]:
        if T is None:
            T = pd.concat([rows[0][2], rows[1][2]], axis=1).mean(axis=1)
        total = T["unif_nocap"] - T["mvp_log"]
        cap = (T["unif_nocap"] - T["unif_cap002"]) / total
        res = (T["unif_cap002"] - T["mvp_log"]) / total
        src = "(unif_nocap - unif_cap002) / (unif_nocap - mvp_log), cost_over_oracle, mode=normal"
        add(f"ablCapSharePct{label}", pct(cap), cap, src + (f", {p}" if p else ", mean of the period means"))
        add(f"ablResolutionSharePct{label}", pct(res), res, src.replace("(unif_nocap - unif_cap002)", "(unif_cap002 - mvp_log)")
            + (f", {p}" if p else ", mean of the period means"))

    # ---------------------------------------------------------------- tau_min nature (confirmation, no outage)
    p = "results/porto_cctv_confirm_posthoc/taumin_nature/taumin_nature.csv"
    R = pd.read_csv(REPO / p); r = R[(R["scenario"] == "none") & (R["a_min"] == a_min)].iloc[0]
    add("tauMinBelowZeroPct", pct(r["A_zero_given_below"]), r["A_zero_given_below"],
        f"{p}: scenario=none, a_min={a_min}; A_zero_given_below (cells below tau_min never observed at any level)", p)
    add("tauMinZeroBelowPct", pct(r["B_below_given_zero"]), r["B_below_given_zero"],
        f"{p}: scenario=none, a_min={a_min}; B_below_given_zero (never-observed cells below tau_min)", p)

    # ---------------------------------------------------------------- re-acquisition share (confirmation run)
    p = "results/porto_cctv_confirm/conditional_coverage.csv"      # tracked (frozen confirmation result)
    cc = pd.read_csv(REPO / p)
    cc = cc[(cc["predictor"] == "src_zone_hour_speed") & (cc["method"] == "static") & (cc["dim"] == "hopkind")]
    share = cc.loc[cc["group"] == 2, "n"].sum() / cc["n"].sum()
    assert abs(share - (H["hopkind"] == 2).mean()) < 1e-12        # same as the per-hop results
    add("reacqSharePct", pct(share), share, f"{p}: predictor=src_zone_hour_speed, method=static, dim=hopkind; "
        "sum n(group 2) / sum n over test_jun_a and test_jun_b (= share of test hops with hopkind 2)", p)

    # ---------------------------------------------------------------- seed repetition, 25 groups
    p = "results/porto_cctv_confirm_posthoc/seeds_prereg25/seeds_criteria.csv"
    S = pd.read_csv(REPO / p)
    for nm, lab in [("MvpLog", "mvp_log"), ("QrOgd", "qr_ogd")]:
        k = int(S.loc[S["label"] == lab, "C1"].sum())
        add(f"seedCOnePass{nm}", f"{k:d}", k, f"{p}: label={lab}; sum of C1 over seeds", p)
    add("seedCount", f"{S['seed'].nunique():d}", S["seed"].nunique(), f"{p}: number of evaluation seeds", p)

    # ================================================================ Section 5 (setup)
    por, cam = cfg["porto"], cfg["cameras"]
    add("gpsInterval", f"{por['gps_interval_s']:g}", por["gps_interval_s"], f"{C}: porto.gps_interval_s (seconds)", CONFIG)
    add("maxSpeed", f"{por['max_speed_mps']:g}", por["max_speed_mps"], f"{C}: porto.max_speed_mps (trips with a faster step are dropped whole, ccpilot/porto.py)", CONFIG)
    add("interpStep", f"{ev['interp_step_s']:g}", ev["interp_step_s"], f"{C}: events.interp_step_s (seconds)", CONFIG)
    import json as _json
    import hashlib as _hl
    gj = _json.load(open(REPO / cam["geojson"], encoding="utf-8"))["features"]
    cctv_sha = _hl.sha256((REPO / cam["geojson"]).read_bytes()).hexdigest()
    CCTV_SRC = (f"{cam['geojson']} (SHA-256 {cctv_sha}; Porto Open Data dataset 9320b636-ef46-4200-9138-f7bf162d249b, "
                "Internet Archive snapshot 2025-07-09: https://web.archive.org/web/20250709151743/https://opendata.porto.digital/"
                "dataset/9320b636-ef46-4200-9138-f7bf162d249b/resource/17b0bdd2-fd58-4b81-a8e7-a4e6fb222154/download/"
                "ext-sistema-de-gestao-de-trafego-cctv-geojson.geojson)")
    tun = [f_["properties"].get("em_tunel") for f_ in gj]
    n_tun = sum(str(v).strip().lower() == "sim" for v in tun)
    n_nao = sum(v is not None and str(v).strip().lower() in ("não", "nao") for v in tun)
    n_none = sum(v is None for v in tun)
    assert n_tun + n_nao + n_none == len(gj)
    add("numCamerasRaw", f"{len(gj):d}", len(gj), f"{CCTV_SRC}: number of features", cam["geojson"])
    add("numTunnelCameras", f"{n_tun:d}", n_tun, f"{CCTV_SRC}: features with em_tunel == 'Sim'", cam["geojson"])
    _w = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    add("numTunnelCamerasWord", _w[n_tun], n_tun, f"{CCTV_SRC}: features with em_tunel == 'Sim', spelled out", cam["geojson"])
    add("numNonTunnelCameras", f"{n_nao:d}", n_nao, f"{CCTV_SRC}: features with em_tunel == 'Não'", cam["geojson"])
    add("numTunnelUnknownCameras", f"{n_none:d}", n_none, f"{CCTV_SRC}: features without an em_tunel value (null); "
        "ccpilot/cameras.py keeps them (only 'Sim' is excluded)", cam["geojson"])
    add("mergeRadius", f"{cam['merge_radius_m']:g}", cam["merge_radius_m"], f"{C}: cameras.merge_radius_m (complete linkage)", CONFIG)
    cams_csv = pd.read_csv(REPO / cfg["work_dir"] / "cameras.csv")
    add("numSites", f"{len(cams_csv):d}", len(cams_csv), f"{cfg['work_dir']}/cameras.csv rows (= load_cctv_geojson output of {CCTV_SRC}; work/ is not tracked)")
    add("cameraRadius", f"{ev['camera_radius_m']:g}", ev["camera_radius_m"], f"{C}: events.camera_radius_m", CONFIG)
    nb = int(np.ceil(ev["t_max_s"] / ev["bin_s"]))
    add("numBins", f"{nb:d}", nb, "ceil(events.t_max_s / events.bin_s)", CONFIG)
    add("feedbackPct", f"{100 * ex['aci']['feedback_fraction']:.0f}", 100 * ex["aci"]["feedback_fraction"], f"{C}: 100 * eval.aci.feedback_fraction", CONFIG)
    add("groupBar", f"{ex['group_bar']:.2f}", ex["group_bar"], f"{C}: eval.group_bar", CONFIG)
    import ast as _ast
    sp_src = (REPO / "select_primary.py").read_text()
    cf = float(_ast.literal_eval(sp_src.split("COST_FACTOR =")[1].split("\n")[0].strip()))
    add("costFactor", f"{cf:.2f}", cf, "select_primary.py: COST_FACTOR (selection rule 2 / criterion C2)", "select_primary.py")
    add("minGroupHops", f"{ex['min_group_n']:d}", ex["min_group_n"], f"{C}: eval.min_group_n (groups reported / judged)", CONFIG)
    add("spatulaSharePct", f"{100 * ex['spatula']['s_thresh']:.0f}", 100 * ex["spatula"]["s_thresh"], f"{C}: 100 * eval.spatula.s_thresh", CONFIG)
    pq = 100 * ex["spatula"]["t_quantile"]
    add("spatulaPercentileOrd", f"{pq:.0f}th", pq, f"{C}: 100 * eval.spatula.t_quantile (ordinal)", CONFIG)
    # CityTrac-style baseline: parameters used when it was added post hoc (ccpilot/posthoc.py reduce_cfg default)
    ph_src = (REPO / "ccpilot/posthoc.py").read_text()
    ct = _ast.literal_eval(ph_src.split('ex.setdefault("citytrac", ')[1].split(")\n")[0])
    add("citytracMinN", f"{ct['min_n']:d}", ct["min_n"], "ccpilot/posthoc.py: reduce_cfg citytrac min_n (confirmation config has no citytrac entry)", "ccpilot/posthoc.py")
    add("citytracTargetLow", f"{ct['targets'][0]:.2f}", ct["targets"][0], "ccpilot/posthoc.py: reduce_cfg citytrac targets[0]", "ccpilot/posthoc.py")
    add("citytracTargetHigh", f"{ct['targets'][1]:.2f}", ct["targets"][1], "ccpilot/posthoc.py: reduce_cfg citytrac targets[1]", "ccpilot/posthoc.py")
    sens_src = (REPO / "posthoc_sensitivity.py").read_text()
    fbs = [float(x) for x in __import__("re").findall(r'"feedback_fraction": ([0-9.]+)', sens_src)]
    dets = sorted({float(x) for x in __import__("re").findall(r'"p_det": ([0-9.]+)', sens_src)})
    add("sensFeedbackMinPct", f"{100 * min(fbs):.0f}", 100 * min(fbs), "posthoc_sensitivity.py: SCENARIOS min feedback_fraction x 100", "posthoc_sensitivity.py")
    add("sensFeedbackMaxPct", f"{100 * max(fbs):.0f}", 100 * max(fbs), "posthoc_sensitivity.py: SCENARIOS max feedback_fraction x 100", "posthoc_sensitivity.py")
    add("sensDetLow", f"{dets[0]:.2f}", dets[0], "posthoc_sensitivity.py: SCENARIOS min p_det", "posthoc_sensitivity.py")
    add("sensDetHigh", f"{dets[-1]:.2f}", dets[-1], "posthoc_sensitivity.py: SCENARIOS max p_det", "posthoc_sensitivity.py")
    AP = "results/porto_cctv_confirm_posthoc/outage_suite/all_periods_summary.csv"
    A_ = pd.read_csv(REPO / AP)
    rs = sorted({int(x[4:]) for x in A_["scenario"].unique() if x.startswith("rand")})
    for w, v in zip(["Low", "Mid", "High"], rs):
        add(f"outageRand{w}Pct", f"{v:d}", v, f"{AP}: scenario rand{v} (share of sites, %)", AP)
    nreg = int(A_.loc[A_["scenario"] == "region_fixed", "n_offline"].iloc[0])
    add("regionSites", f"{nreg:d}", nreg, f"{AP}: scenario=region_fixed, n_offline", AP)
    nseed = A_.loc[A_["scenario"].str.startswith("rand"), "site_seed"].nunique()
    add("outageSiteSeeds", f"{nseed:d}", nseed, f"{AP}: distinct site_seed of rand scenarios", AP)

    # non-exit hops per split (work/ transitions are not tracked; source = config splits + events)
    from ccpilot.evaluate import _period_mask
    def fmt_int(v):
        return f"{v:,}".replace(",", "{,}")
    names = {"porto_cctv": ("ExplOne", {"test_same": "Same", "test_holiday": "Holiday"}),
             "porto_cctv_rep": ("ExplTwo", {"test_mar": "Mar", "test_apr": "Apr", "test_easter": "Easter"}),
             "porto_cctv_confirm": ("Held", {"test_jun_a": "A", "test_jun_b": "B"})}
    for cpath in ["configs/porto_cctv.yaml", "configs/porto_cctv_replication.yaml", CONFIG]:
        cc_ = yaml.safe_load(open(REPO / cpath, encoding="utf-8")); tz_ = cc_["timezone"]; sp_ = cc_["eval"]["splits"]
        pre, segn = names[cc_["out_dir"].split("/")[-1]]
        tr_ = pd.read_parquet(REPO / cc_["work_dir"] / "transitions.parquet", columns=["t_exit", "is_exit"])
        t_ = tr_["t_exit"].to_numpy(); ok_ = ~tr_["is_exit"].to_numpy()
        for nm, rng_ in [("Train", sp_["train"]), ("Cal", sp_["cal"])] + [(segn[s_["name"]], s_["range"]) for s_ in sp_["test"]]:
            v = int((_period_mask(t_, rng_, tz_) & ok_).sum())
            add(f"hops{pre}{nm}", fmt_int(v), v, f"{cc_['work_dir']}/transitions.parquet: non-exit hops with t_exit in {rng_} ({cpath} splits)")

    # ================================================================ Section 6 (values noted in the skeleton)
    RS = "results/porto_cctv_confirm_regrade/regrade_summary.csv"
    G_ = pd.read_csv(REPO / RS)
    G_ = G_[(G_["predictor"] == "src_zone_hour_speed") & (G_["definition"] == "prereg_25")]
    mnames = {"mvp_log": "MvpLog", "qr_ogd": "QrOgd", "static": "Static", "aci_g0005": "Aci",
              "mondrian_hour_hop_speed": "Mondrian", "qr_groups": "QrGroups"}
    for meth, mn in mnames.items():
        for seg, sn in [("test_jun_a", "A"), ("test_jun_b", "B")]:
            r_ = G_[(G_["method"] == meth) & (G_["segment"] == seg)].iloc[0]
            add(f"held{mn}Worst{sn}", r3(r_["worst_cov"]), r_["worst_cov"], f"{RS}: prereg_25, {meth}, {seg}; worst_cov", RS)
            add(f"held{mn}BelowBar{sn}", f"{int(r_['n_sig_below_0.94'])}", r_["n_sig_below_0.94"], f"{RS}: prereg_25, {meth}, {seg}; n_sig_below_0.94", RS)
            add(f"held{mn}BelowTarget{sn}", f"{int(r_['n_sig_below_0.95'])}", r_["n_sig_below_0.95"], f"{RS}: prereg_25, {meth}, {seg}; n_sig_below_0.95", RS)
    SM = "results/porto_cctv_confirm/summary.csv"
    S_ = pd.read_csv(REPO / SM); S_ = S_[S_["predictor"] == "src_zone_hour_speed"]
    orc = S_[S_["method"] == "oracle(post-hoc)"].set_index("segment")["cost_mean_cam_s"]
    for meth, mn in [("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")]:
        rr = S_[S_["method"] == meth].set_index("segment")["cost_mean_cam_s"] / orc
        add(f"held{mn}CostRatioA", r3(rr["test_jun_a"]), rr["test_jun_a"], f"{SM}: {meth} cost_mean_cam_s / oracle(post-hoc), test_jun_a", SM)
        add(f"held{mn}CostRatioB", r3(rr["test_jun_b"]), rr["test_jun_b"], f"{SM}: {meth} cost / oracle, test_jun_b", SM)
        add(f"held{mn}CostRatioMean", r3(rr.mean()), rr.mean(), f"{SM}: {meth} mean over test_jun_a, test_jun_b of cost / oracle (criterion C2)", SM)
        if meth == "mvp_log":     # same value, two decimals (Sections 1 and 8)
            add(f"held{mn}CostRatioMeanShort", r2(rr.mean()), rr.mean(), f"{SM}: {meth} mean over test_jun_a, test_jun_b of cost / oracle (criterion C2), 2 decimals", SM)
    # exploratory cost ratio of the selected method (select_primary.py, rule 2): mean over the five exploratory segments
    EX = ["results/porto_cctv/summary.csv", "results/porto_cctv_rep/summary.csv"]
    E_ = pd.concat([pd.read_csv(REPO / x) for x in EX], ignore_index=True)
    E_ = E_[E_["predictor"] == "src_zone_hour_speed"]
    eo = E_[E_["method"] == "oracle(post-hoc)"].set_index("segment")["cost_mean_cam_s"]
    ed = E_[E_["method"] == "mvp_log"].set_index("segment")["cost_mean_cam_s"]
    assert eo.index.is_unique and len(ed) == 5
    er = (ed / eo.reindex(ed.index)).mean()
    add("explMvpLogCostRatioMean", r2(er), er, f"{EX[0]} + {EX[1]}: mvp_log mean over the five exploratory segments of cost_mean_cam_s / oracle(post-hoc) (select_primary.py rule 2)", EX[1])
    SD = "results/porto_cctv_confirm_posthoc/seeds_prereg25/seeds_all.csv"
    D_ = pd.read_csv(REPO / SD)
    for meth, mn in [("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")]:
        c2 = int(D_[D_["label"] == meth].groupby("seed")["cost_over_oracle"].mean().le(cf).sum())
        add(f"seedCTwoPass{mn}", f"{c2:d}", c2, f"{SD}: label={meth}; seeds with mean cost_over_oracle <= costFactor", SD)
    HS = "results/porto_cctv_confirm_posthoc/seeds_prereg25/seed_{k}/hits.parquet"
    from ccpilot.evaluate import _wilson_ub
    rec = []
    for k in range(5):
        Hh = pd.read_parquet(REPO / HS.format(k=k), columns=["segment", "hopkind", "hit|src_zone_hour_speed|mvp_log"])
        m_ = (Hh["segment"] == "test_jun_b") & (Hh["hopkind"] == 2)
        rec.append(Hh.loc[m_, "hit|src_zone_hour_speed|mvp_log"].mean())
    add("seedReacqMvpLogMin", r3(min(rec)), min(rec), f"{HS}: mvp_log recall of hopkind=2 in test_jun_b, min over seeds 0-4 (hits.parquet untracked; from posthoc_seeds.py --groups prereg_25)")
    add("seedReacqMvpLogMax", r3(max(rec)), max(rec), f"{HS}: same, max over seeds")
    FR = "results/porto_cctv_confirm_posthoc/frontier_prereg25/cost_matched.csv"
    F_ = pd.read_csv(REPO / FR)
    for seg, sn in [("test_jun_a", "A"), ("test_jun_b", "B")]:
        f_ = F_[F_["segment"] == seg].set_index("method")
        add(f"frontierRefRatio{sn}", r2(f_.loc["mvp_log", "ref_cost_ratio(mvp_log@0.95)"]), f_.loc["mvp_log", "ref_cost_ratio(mvp_log@0.95)"], f"{FR}: {seg}, mvp_log ref cost ratio", FR)
        for meth, mn in [("static", "Static"), ("citytrac", "Citytrac")]:
            add(f"frontier{mn}WorstAtRef{sn}", r3(f_.loc[meth, "worst_group_at_ref_cost"]), f_.loc[meth, "worst_group_at_ref_cost"], f"{FR}: {seg}, {meth}, worst_group_at_ref_cost", FR)
            add(f"frontier{mn}CostNoSig{sn}", r2(f_.loc[meth, "min_cost_ratio_no_sig_group"]), f_.loc[meth, "min_cost_ratio_no_sig_group"], f"{FR}: {seg}, {meth}, min_cost_ratio_no_sig_group", FR)
    FC = "results/porto_cctv_confirm_posthoc/frontier_prereg25/frontier.csv"
    Fc = pd.read_csv(REPO / FC)
    diffs = []
    for seg in ["test_jun_a", "test_jun_b"]:
        st = Fc[(Fc["method"] == "static") & (Fc["segment"] == seg)].sort_values("cost_over_oracle")
        mv = Fc[(Fc["method"] == "mvp_log") & (Fc["segment"] == seg) & (Fc["target"] == 0.95)].iloc[0]
        diffs.append(np.interp(mv["cost_over_oracle"], st["cost_over_oracle"], st["coverage"]) - mv["coverage"])
        add(f"frontierStaticRecallGainPp{'A' if seg.endswith('a') else 'B'}", f"{100 * diffs[-1]:.1f}", diffs[-1],
            f"{FC}: {seg}; static coverage interpolated (linear in cost_over_oracle) at mvp_log@0.95 cost minus mvp_log coverage, pp", FC)
    for vn, meth in variants:
        vals = []
        for label, p_, _ in rows:
            T5 = pd.read_csv(REPO / p_); T5 = T5[(T5["mode"] == "normal") & (T5["method"] == meth)]
            vals.append(T5)
        allseg = pd.concat(vals)["cost_over_oracle"].mean()
        add(f"abl{vn}RatioSegMean", r2(allseg), allseg, "mean over all five exploratory test segments (both scale_ablation_summary.csv, mode=normal) of cost_over_oracle")

    # ================================================================ revision 2 of sec4/sec5 (David, 2026-09-30)
    WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    def plain_int(v):
        return f"{v:,}"                     # text mode: 1,710,670
    TR = "data/porto/train.csv"
    raw = pd.read_csv(REPO / TR, usecols=["TAXI_ID"])
    add("numTripsFile", plain_int(len(raw)), len(raw), f"{TR}: number of rows (trips) (data file not tracked; ECML/PKDD 2015 / UCI 339)")
    add("numTaxisFile", f"{raw['TAXI_ID'].nunique():d}", raw["TAXI_ID"].nunique(), f"{TR}: distinct TAXI_ID")
    # value stated in the dataset description, not computable from the file
    add("numTaxisDescribed", "442", 442, "UCI Machine Learning Repository dataset 339 description, 'all the 442 taxis' "
        "(https://archive.ics.uci.edu/dataset/339, retrieved 2026-09-30); not computed from files")
    por_src = (REPO / "ccpilot/porto.py").read_text()
    minpts = int(__import__("re").search(r"if len\(pts\) < (\d+):", por_src).group(1))
    add("minTripPoints", f"{minpts:d}", minpts, "ccpilot/porto.py: trips with len(pts) < this are dropped", "ccpilot/porto.py")
    add("minTripPointsWord", WORDS[minpts], minpts, "same as minTripPoints, spelled out", "ccpilot/porto.py")
    abl_src = (REPO / "posthoc_scale_ablation.py").read_text()
    amins = {m: float(v) for m, v in __import__("re").findall(r'"name": "(log_cap00[15])".*?"a_min": ([0-9.]+)', abl_src)}
    add("aMinLow", f"{amins['log_cap001']:g}", amins["log_cap001"], "posthoc_scale_ablation.py: VARIANTS log_cap001 a_min", "posthoc_scale_ablation.py")
    add("aMinHigh", f"{amins['log_cap005']:g}", amins["log_cap005"], "posthoc_scale_ablation.py: VARIANTS log_cap005 a_min", "posthoc_scale_ablation.py")
    # secondary-method tie-break: lowest worst-group recall over the five exploratory segments (selection rule 5),
    # on the pre-registered 25 groups (exploratory regrade); equals the as-run value used at selection time
    RG = ["results/porto_cctv_regrade/regrade_summary.csv", "results/porto_cctv_rep_regrade/regrade_summary.csv"]
    rg = pd.concat([pd.read_csv(REPO / f) for f in RG])
    rg = rg[(rg["predictor"] == "src_zone_hour_speed") & (rg["definition"] == "prereg_25")]
    exs = pd.concat([pd.read_csv(REPO / f) for f in ["results/porto_cctv/summary.csv", "results/porto_cctv_rep/summary.csv"]])
    exs = exs[exs["predictor"] == "src_zone_hour_speed"]
    for meth, mn in [("qr_ogd", "QrOgd"), ("qr_groups", "QrGroups")]:
        v = rg.loc[rg["method"] == meth, "worst_cov"].min()
        assert len(rg[rg["method"] == meth]) == 5
        assert abs(v - exs.loc[exs["method"] == meth, "worst_group_cov"].min()) < 1e-12   # same as the as-run value
        add(f"sel{mn}MinWorst", r3(v), v, f"{RG[0]} + {RG[1]}: prereg_25, {meth}; min of worst_cov over the five "
            "exploratory segments (identical to the as-run value in results/porto_cctv*/summary.csv)", RG[0])
    # initial outage experiment (held-out period only; posthoc_outage.py)
    OS = "results/porto_cctv_confirm_posthoc/outage/outage_scenarios.csv"
    O_ = pd.read_csv(REPO / OS)
    ir = sorted(int(x[4:]) for x in O_["scenario"] if x.startswith("rand"))
    for w, v in zip(["Low", "Mid", "High"], ir):
        add(f"initOutageRand{w}Pct", f"{v:d}", v, f"{OS}: scenario rand{v} (initial outage, held-out only)", OS)
    nreg0 = int(O_.loc[O_["scenario"] == "region", "n_offline"].iloc[0])
    add("initRegionSitesWord", WORDS[nreg0], nreg0, f"{OS}: scenario=region, n_offline, spelled out", OS)
    add("outageSiteSeedsWord", WORDS[nseed], nseed, f"{AP}: distinct site_seed of rand scenarios, spelled out", AP)

    # qr_ogd clipping (sec4 L354-358): reconstruction of all qr_ogd runs over three periods by
    # scripts/verify_todos.py (each run checked against the stored hop-level results); files live in paper/.
    import glob
    qf = [f for f in sorted(glob.glob(str(PAPER / "generated/checks/qrogd_*.csv"))) if not f.endswith("qrogd_all.csv")]
    Q = pd.concat([pd.read_csv(f) for f in qf], ignore_index=True)
    Q["period"] = Q["period"].fillna("porto_cctv_confirm")
    Q["kind"] = Q.run.str.extract(r"(rand\d\d|region_fixed|region|none|seed_\d|normal)")[0]
    Q["kind"] = Q["kind"].str.replace(r"rand\d\d", "random", regex=True).str.replace(r"seed_\d|none|normal", "no outage", regex=True)
    Q["base"] = Q.predictor == "src_zone_hour_speed"
    QR = Q.groupby(["kind", "base", "period", "run"]).reached_clip.sum().reset_index()
    pc = subprocess.run(["git", "log", "-1", "--format=%h", "--", "generated/checks"], cwd=PAPER, capture_output=True, text=True).stdout.strip()
    QS = (f"paper generated/checks/qrogd_*.csv (excl. qrogd_all.csv; scripts/verify_todos.py, paper commit {pc}); "
          "per run x predictor: number of groups with reached_clip")
    rb = QR[(QR.kind == "random") & QR.base].reached_clip
    assert (rb > 0).all() and (QR[QR.kind == "no outage"].reached_clip == 0).all()
    med = float(rb.median())   # 48 runs: mean of the 24th and 25th values, may end in .5
    add("clipBaseRandMinGroups", f"{rb.min():d}", int(rb.min()), QS + "; kind=random, base predictor; min over runs")
    add("clipBaseRandMaxGroups", f"{rb.max():d}", int(rb.max()), QS + "; kind=random, base predictor; max over runs")
    add("clipBaseRandMedianGroups", f"{med:g}", med, QS + "; kind=random, base predictor; median over runs")
    ro = QR[(QR.kind != "no outage") & ~((QR.kind == "random") & QR.base)].reached_clip
    ro = ro[ro > 0]
    add("clipOtherMinGroupsWord", WORDS[int(ro.min())], int(ro.min()), QS + "; outage-aware predictor (all outage kinds) "
        "and base predictor under region / region_fixed; min over runs with reached_clip > 0, spelled out")
    add("clipOtherMaxGroupsWord", WORDS[int(ro.max())], int(ro.max()), QS + "; same runs; max over runs with reached_clip > 0, spelled out")

    # ================================================================ Chapter 6 tables and figures (key values)
    # Read from generated/data/<table>.csv, written by scripts/make_tables.py / make_figures.py from the result
    # files named in each CSV's first line (run `make tables figures` before `make numbers`). Rounding as in the tables.
    def ch6(name):
        f = PAPER / "generated" / "data" / f"{name}.csv"
        pc = subprocess.run(["git", "log", "-1", "--format=%h", "--", str(f.relative_to(PAPER))], cwd=PAPER,
                            capture_output=True, text=True).stdout.strip() or "uncommitted"
        return pd.read_csv(f, comment="#"), f"paper generated/data/{name}.csv (paper commit {pc})"
    T1, s1 = ch6("tab_main")
    for seg in ["A", "B"]:
        r_ = T1[(T1.method == "oracle") & (T1.seg == seg)].iloc[0]
        add(f"heldOracleCost{seg}", f"{r_.cost_cam_s:.1f}", r_.cost_cam_s,
            f"{s1}: method=oracle, segment {seg}; cost_cam_s = frozen summary oracle(post-hoc) cost_mean_cam_s (camera-seconds per hop)")
    for key, mn in [("citytrac095", "CityTracNinetyFive"), ("mvp_groups", "MvpGroups"), ("spatula", "Spatula")]:
        for seg in ["A", "B"]:
            r_ = T1[(T1.method == key) & (T1.seg == seg)].iloc[0]
            add(f"held{mn}CostRatio{seg}", r2(r_.cost_ratio), r_.cost_ratio, f"{s1}: method={key}, segment {seg}; cost_ratio")
            add(f"held{mn}Worst{seg}", r3(r_.worst), r_.worst, f"{s1}: method={key}, segment {seg}; worst (25 groups, n >= 200)")
    S3, s3 = ch6("tab_sensitivity")
    fb = S3[S3.part == "feedback"].set_index("scenario")
    for sc, mn in [("fb010", "Ten"), ("fb100", "Full"), ("fb100_nodelay", "FullImmediate")]:
        for seg in ["A", "B"]:
            add(f"sensFb{mn}Worst{seg}", r3(fb.loc[sc, f"worst_{seg}"]), fb.loc[sc, f"worst_{seg}"], f"{s3}: scenario={sc}, mvp_log; worst_{seg}")
            add(f"sensFb{mn}BelowBar{seg}", f"{int(fb.loc[sc, f'below94_{seg}'])}", fb.loc[sc, f"below94_{seg}"], f"{s3}: scenario={sc}, mvp_log; below94_{seg}")
    det = S3[S3.part == "detection"]
    for sc, mn in [("det095", "NinetyFive"), ("det090", "Ninety")]:
        for meth, me in [("mvp_log", ""), ("static", "Static")]:
            for adj, an in [("", "Unadj"), ("_adj", "Adj")]:
                r_ = det[(det.scenario == sc + adj) & (det.method == meth)].iloc[0]
                add(f"sensDet{mn}{me}{an}CostRatio", r2(r_.cost_ratio_clean_oracle_mean), r_.cost_ratio_clean_oracle_mean,
                    f"{s3}: scenario={sc + adj}, {meth}; mean over A, B of cost / hindsight oracle of the run without detection errors (Table 3 cost)")
        r_ = det[(det.scenario == sc + "_adj") & (det.method == "mvp_log")].iloc[0]
        for seg in ["A", "B"]:
            add(f"sensDet{mn}AdjRecall{seg}", r3(r_[f"recall_{seg}"]), r_[f"recall_{seg}"], f"{s3}: scenario={sc}_adj, mvp_log; true-location recall_{seg}")
        if sc == "det090":      # 2026-10-02 text: "with two groups below the bar in one segment"
            nb = [int(r_["below94_A"]), int(r_["below94_B"])]
            add("sensDetNinetyAdjBelowBarMaxWord", WORDS[max(nb)], max(nb), f"{s3}: scenario=det090_adj, mvp_log; max over segments of below94 ({nb[0]} A, {nb[1]} B), spelled out")
            nseg = sum(1 for x in nb if x > 0)
            add("sensDetNinetyAdjSegmentsBelowWord", WORDS[nseg], nseg, f"{s3}: scenario=det090_adj, mvp_log; number of segments with below94 > 0, spelled out")
    O4, s4 = ch6("tab_outage")
    for sc, sn in [("rand10", "Ten"), ("rand20", "Twenty"), ("rand30", "Thirty"), ("region_fixed", "Region")]:
        for pl, pn in [("base", "Base"), ("outage-aware", "Aware")]:
            r_ = O4[(O4.scenario == sc) & (O4.predictor == pl)].iloc[0]
            for key, mn in [("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd"), ("aci", "Aci"), ("static", "Static")]:
                add(f"out{sn}{pn}{mn}Recall", r3(r_[f"recall_{key}"]), r_[f"recall_{key}"], f"{s4}: scenario={sc}, predictor={pl}, {key}; recall (B_late, site-seed mean)")
                v = r_[f"below94_{key}"]
                add(f"out{sn}{pn}{mn}BelowBar", f"{v:.1f}" if sc != "region_fixed" else f"{int(v)}", v, f"{s4}: scenario={sc}, predictor={pl}, {key}; below94 (site-seed mean)")
                add(f"out{sn}{pn}{mn}CostRatio", r2(r_[f"cost_ratio_none_{key}"]), r_[f"cost_ratio_none_{key}"], f"{s4}: scenario={sc}, predictor={pl}, {key}; cost / no-outage oracle")
    C5, s5 = ch6("tab_ceiling")
    for sc, sn in [("rand10", "Ten"), ("rand30", "Thirty")]:
        for pl, pn in [("base", "Base"), ("outage-aware", "Aware")]:
            v = C5[(C5.scenario == sc) & (C5.predictor == pl) & (C5.key == "grp_all=0")].p_below_mean.iloc[0]
            add(f"ceil{sn}{pn}All", r3(v), v, f"{s5}: scenario={sc}, predictor={pl}, all hops; p_below_mean")
    LH, s6 = ch6("tab_lost_hops")
    r_ = LH[LH.scenario == "rand10"].iloc[0]
    add("lostTenSrcOffPct", f"{r_.pct_src_offline:.1f}", r_.pct_src_offline, f"{s6}: rand10; pct_src_offline")
    add("lostTenRelinkedRecallBase", r3(r_.recall_rerouted_mvp_log_base), r_.recall_rerouted_mvp_log_base, f"{s6}: rand10; recall_rerouted_mvp_log_base")
    add("lostTenRelinkedRecallAware", r3(r_["recall_rerouted_mvp_log_outage-aware"]), r_["recall_rerouted_mvp_log_outage-aware"], f"{s6}: rand10; recall_rerouted_mvp_log_outage-aware")
    OG, s7 = ch6("tab_oracle_groups")
    r_ = OG[OG.group == "all"].iloc[0]
    add("oracleGroupsAllCostRatio", r2(r_.cost_ratio_mvp_over_oracle), r_.cost_ratio_mvp_over_oracle, f"{s7}: group=all; cost_ratio_mvp_over_oracle (site seed 7)")

    # ================================================================ Section 6 text (draft 1, lines marked % NUM)
    GB, sgb = ch6("fig_group_recall_B")
    GA, sga = ch6("fig_group_recall_A")
    st = GB[GB.method == "static"].set_index("key")
    for key, mn in [("entropy_bin=3", "BranchHigh"), ("nn_bin=3", "IsoHigh"), ("hopkind=1", "Initiated"), ("speed_bin=0", "Slow")]:
        add(f"heldStatic{mn}RecallB", r3(st.loc[key, "recall"]), st.loc[key, "recall"], f"{sgb}: method=static, group {key}; recall (segment B)")
    easy = [st.loc[k, "recall"] for k in ["entropy_bin=0", "nn_bin=0"]]
    assert r2(easy[0]) == r2(easy[1]), easy
    add("heldStaticEasyRecallApproxB", r2(easy[0]), np.mean(easy), f"{sgb}: static, groups entropy_bin=0 ({easy[0]:.4f}) and nn_bin=0 ({easy[1]:.4f}); both round to this value")
    r_ = T1[(T1.method == "static") & (T1.seg == "B")].iloc[0]
    add("heldStaticRecallB", r3(r_.recall), r_.recall, f"{s1}: method=static, segment B; recall (all hops)")
    for seg in ["A", "B"]:
        r_ = T1[(T1.method == "oracle") & (T1.seg == seg)].iloc[0]
        add(f"heldOracleBelowBar{seg}", f"{int(r_.below94)}", r_.below94, f"{s1}: method=oracle, segment {seg}; below94")
    mg = T1[T1.method.isin(["static", "aci", "mvp_global", "oracle"])].below94
    add("heldMarginalBelowBarMin", f"{int(mg.min())}", mg.min(), f"{s1}: methods static, aci, mvp_global, oracle, both segments; min of below94")
    add("heldMarginalBelowBarMax", f"{int(mg.max())}", mg.max(), f"{s1}: same; max of below94")
    ct = T1[T1.method == "citytrac095"].recall
    assert r2(ct.iloc[0]) == r2(ct.iloc[1])
    add("heldCityTracNinetyFiveRecallApprox", r2(ct.iloc[0]), ct.mean(), f"{s1}: method=citytrac095, segments A and B ({ct.iloc[0]:.4f}, {ct.iloc[1]:.4f}); both round to this value")
    sp = T1[T1.method == "spatula"].below94
    assert sp.nunique() == 1
    add("heldSpatulaBelowBar", f"{int(sp.iloc[0])}", sp.iloc[0], f"{s1}: method=spatula; below94 (same in A and B)")
    for seg in ["A", "B"]:
        r_ = T1[(T1.method == "citytrac099") & (T1.seg == seg)].iloc[0]
        add(f"heldCityTracNinetyNineCostRatio{seg}", f"{r_.cost_ratio:.1f}", r_.cost_ratio, f"{s1}: method=citytrac099, segment {seg}; cost_ratio, one decimal (text)")
    for G_, sg_, seg, ex, mn in [(GA, sga, "A", False, "A"), (GB, sgb, "B", True, "ExReacqB")]:
        m_ = G_[(G_.method == "mvp_log") & G_.judged & (G_.ub95 < 0.95)]
        if ex:
            m_ = m_[m_.key != "hopkind=2"]
        v = 100 * (0.95 - m_.recall).max()
        add(f"heldMvpLogMaxShortfallPp{mn}", f"{v:.1f}", v, f"{sg_}: mvp_log, groups with n >= 200 and Wilson upper bound < 0.95"
            + (" except hopkind=2" if ex else "") + "; max of (0.95 - recall) in pp")
    LF, slf = ch6("tab_layout_factors")
    for att, an in [("speed_bin", "Speed"), ("nn_bin", "Iso")]:
        for lay, ln in [("virtual", "Virtual"), ("real", "Real")]:
            v = LF[(LF.attribute == att) & (LF.layout == lay)].spread_pp.mean()
            add(f"layout{an}Spread{ln}", f"{v:.0f}", v, f"{slf}: attribute={att}, layout={lay}; mean over the two exploratory periods of spread_pp, rounded ('about')")
    fbc = S3[S3.part == "feedback"].cost_ratio_mean
    add("sensFbCostRatioMin", r2(fbc.min()), fbc.min(), f"{s3}: feedback rows (mvp_log); min of cost_ratio_mean")
    add("sensFbCostRatioMax", r2(fbc.max()), fbc.max(), f"{s3}: feedback rows (mvp_log); max of cost_ratio_mean")
    sw = det[(det.method == "static") & det.scenario.str.endswith("_adj")].worst_B
    assert sw.map(r2).nunique() == 1
    add("sensDetStaticAdjWorstApproxB", r2(sw.iloc[0]), sw.mean(), f"{s3}: static, det095_adj and det090_adj, worst_B ({', '.join(f'{x:.4f}' for x in sw)}); both round to this value")
    r_ = LH[LH.scenario == "rand10"].iloc[0]
    add("lostTenOtherRecallBase", r2(r_.recall_nonrerouted_mvp_log_base), r_.recall_nonrerouted_mvp_log_base,
        f"{s6}: rand10; recall of all non-rerouted hops (unchanged + new), mvp_log, base predictor")
    ex_ = []
    for nm in ["tab_outage_expl1", "tab_outage_expl2"]:
        X_, sx = ch6(nm)
        ex_.append(X_[X_.predictor == "outage-aware"])
    ex_ = pd.concat(ex_)
    ex_ = ex_[ex_.scenario.str.startswith("rand")]          # random outages only (text: "under random outages")
    v = ex_.below94_mvp_log.max()
    add("explAwareMvpLogBelowBarMax", f"{v:.1f}", v, "paper generated/data/tab_outage_expl{1,2}.csv: outage-aware rows, random outages only (rand10/20/30 site-seed means); max of below94_mvp_log")
    v = ex_.below94_qr_ogd.max()
    add("explAwareQrOgdBelowBarMax", f"{v:.1f}", v, "paper generated/data/tab_outage_expl{1,2}.csv: outage-aware rows, random outages only; max of below94_qr_ogd")
    E_, se_ = ch6("tab_outage_early")
    e_ = E_[(E_.predictor == "outage-aware") & E_.scenario.str.startswith("rand")]
    for col, mn in [("below94_mvp_log", "MvpLog"), ("below94_qr_ogd", "QrOgd"), ("below94_aci", "Aci")]:
        for agg, an in [("min", "Min"), ("max", "Max")]:
            v = getattr(e_[col], agg)()
            add(f"earlyAware{mn}BelowBar{an}", f"{v:.1f}", v, f"{se_}: outage-aware, random outages (rand10/20/30 seed means; region excluded); {agg} of {col}, one decimal (table rule for seed means)")

    # ================================================================ Section 6 text (revision 1, lines marked % NUM)
    AP_ = "results/porto_cctv_confirm_posthoc/outage_suite/all_periods_summary.csv"
    A_ = pd.read_csv(REPO / AP_)
    a_ = A_[(A_.period == "porto_cctv_confirm") & (A_.segment == "B_late") & (A_.predictor == "src_zone_hour_speed")
            & (A_.method == "mvp_log_a001") & A_.scenario.isin(["rand10", "rand20", "rand30"])]
    g_ = a_.groupby("scenario").agg(r=("coverage", "mean"), c=("cost_over_oracle_none", "mean"))
    add("outTenBaseMvpLogAMinLowRecall", r3(g_.loc["rand10", "r"]), g_.loc["rand10", "r"],
        f"{AP_}: held-out, B_late, base predictor, method mvp_log_a001 (a_min 0.001), rand10; mean over site seeds of coverage", AP_)
    add("outRandBaseMvpLogAMinLowCostMin", f"{g_.c.min():.0f}", g_.c.min(), f"{AP_}: same, rand10/20/30; min over scenarios of the site-seed mean of cost_over_oracle_none, integer", AP_)
    add("outRandBaseMvpLogAMinLowCostMax", f"{g_.c.max():.0f}", g_.c.max(), f"{AP_}: same; max over scenarios, integer", AP_)
    HL_ = "results/porto_cctv_confirm_posthoc/exit_split/hop_loss_split.csv"
    S_ = pd.read_csv(REPO / HL_)
    S_ = S_[(S_.start == "2014-06-21") & (S_.window == "all_post")].set_index("scenario")
    sk = S_.rerouted_skip2plus / (S_.rerouted_skip1 + S_.rerouted_skip2plus)
    add("lostRegionSkipTwoPct", f"{100 * sk['region']:.0f}", 100 * sk["region"], f"{HL_}: start 2014-06-21, window all_post, scenario region (6 sites); rerouted_skip2plus / (skip1 + skip2plus), %", HL_)
    rk = sk[["rand10", "rand20", "rand30"]] * 100
    add("lostRandSkipTwoPctMin", f"{rk.min():.0f}", rk.min(), f"{HL_}: same, rand10/20/30; min, %", HL_)
    add("lostRandSkipTwoPctMax", f"{rk.max():.0f}", rk.max(), f"{HL_}: same; max, %", HL_)
    TSd, sts = ch6("fig_outage_timeseries")
    TSd = TSd[(TSd.bin_h == 6) & (TSd.bin_start_h >= 0)]

    def _first24(sr):
        sr = sr.sort_index(); ok = (sr >= 0.94).to_numpy(); b = sr.index.to_numpy()
        return next((float(b[i]) for i in range(len(ok)) if i + 4 <= len(ok) and ok[i:i + 4].all()), np.nan)
    rec = {k: _first24(TSd[(TSd.predictor == "src_zone_hour_speed_oa") & (TSd.method == k)].set_index("bin_start_h").recall_mean)
           for k in ["aci", "qr_ogd", "mvp_log"]}
    assert rec["aci"] == rec["qr_ogd"], rec
    add("recovAwareFastHours", f"{rec['aci']:.0f}", rec["aci"], f"{sts}: outage-aware, rand10, mean over site seeds of 6-h recall; first bin start (h) "
        "from which recall >= 0.94 for 24 h (4 bins); ACI and qr_ogd (equal)")
    add("recovAwareMvpLogHours", f"{rec['mvp_log']:.0f}", rec["mvp_log"], f"{sts}: same, mvp_log")
    RD_ = "results/porto_cctv_confirm_posthoc/outage_diag/recovery_48h.csv"
    D_ = pd.read_csv(REPO / RD_)
    D_ = D_[(D_.start == "2014-06-21") & (D_.scenario == "rand10")].set_index("method").recover_h
    add("warmMvpGlobalRecoverHours", f"{D_['mvp_global']:.0f}", D_["mvp_global"], f"{RD_}: start 2014-06-21, rand10, original predictor, mvp_global (warm start on); recover_h", RD_)
    add("warmZeroMvpGlobalRecoverHours", f"{D_['mvp_global_w000']:.0f}", D_["mvp_global_w000"], f"{RD_}: same, mvp_global_w000 (warm start removed); recover_h", RD_)

    # ================================================================ Section 7 revision (top-bucket share, original predictor)
    SD_ = "results/porto_cctv_confirm_posthoc/outage_diag/saturation_6h.csv"
    T_ = pd.read_csv(REPO / SD_)
    T_ = T_[(T_.method == "mvp_log") & (T_.group == "all") & (T_.hours >= 0)]
    sat = T_.groupby(["scenario", "start"]).sat_share.mean()
    for sc, sn in [("rand10", "Rand"), ("region", "Region")]:
        v = sat.loc[sc]
        add(f"out{sn}BaseMvpLogSatShareMin", r2(v.min()), v.min(), f"{SD_}: mvp_log, all hops, original predictor, scenario {sc} (site seed 7; region = 6 sites), "
            f"mean over 6-h bins after the outage start of sat_share; min over the two starts ({', '.join(f'{k} {x:.4f}' for k, x in v.items())})", SD_)
        add(f"out{sn}BaseMvpLogSatShareMax", r2(v.max()), v.max(), f"{SD_}: same; max over the two starts", SD_)

    # ================================================================ additional analyses in the text (David, 2026-10-01, lines marked % NUM)
    # --- group-conditional hindsight references (M1)
    GO = "results/porto_cctv_confirm_posthoc/group_oracle/group_oracle_summary.csv"
    Q_ = pd.read_csv(REPO / GO).set_index(["method", "segment"])
    gm = [Q_.loc[("group_min", s_), "recall_mean"] for s_ in ("test_jun_a", "test_jun_b")]
    assert r3(gm[0]) == r3(gm[1])
    add("goGroupMinRecall", r3(gm[0]), gm[0], f"{GO}: method=group_min, recall_mean, test_jun_a ({gm[0]:.4f}) and test_jun_b ({gm[1]:.4f}) equal to 3 decimals", GO)
    for s_, sn in [("test_jun_a", "A"), ("test_jun_b", "B")]:
        v = Q_.loc[("group_min", s_), "ratio_vs_oracle"]
        add(f"goGroupMinCostRatio{sn}", r2(v), v, f"{GO}: method=group_min, {s_}, ratio_vs_oracle", GO)
        v = Q_.loc[("mvp_log", s_), "cost_cam_s"] / Q_.loc[("hindsight_qr", s_), "cost_cam_s"]
        add(f"goMvpLogOverQr{sn}", r2(v), v, f"{GO}: {s_}, cost_cam_s of mvp_log / cost_cam_s of hindsight_qr", GO)
    qr = [Q_.loc[("hindsight_qr", s_), "ratio_vs_oracle"] for s_ in ("test_jun_a", "test_jun_b")]
    assert r2(qr[0]) == r2(qr[1])
    add("goQrCostRatio", r2(qr[0]), qr[0], f"{GO}: method=hindsight_qr, ratio_vs_oracle, A ({qr[0]:.4f}) and B ({qr[1]:.4f}) equal to 2 decimals", GO)
    qw = [Q_.loc[("hindsight_qr", s_), "worst"] for s_ in ("test_jun_a", "test_jun_b")]
    assert r3(qw[0]) == r3(qw[1])
    add("goQrWorst", r3(qw[0]), qw[0], f"{GO}: method=hindsight_qr, worst (25 groups, n >= 200), A ({qw[0]:.4f}) and B ({qw[1]:.4f}) equal to 3 decimals", GO)
    # paired test mvp_log vs qr_ogd on the re-acquisition hops of segment B
    from scipy.stats import binomtest
    HH = "results/porto_cctv_confirm_posthoc/outage_suite/none_s7/hits.parquet"
    H_ = pd.read_parquet(REPO / HH)
    H_["seg"] = H_["segment"].replace({"B_early": "test_jun_b", "B_late": "test_jun_b"})
    m_ = ((H_.seg == "test_jun_b") & (H_.hopkind == 2)).to_numpy()
    a_ = H_.loc[m_, "hit|src_zone_hour_speed|mvp_log"].to_numpy().astype(int); b_ = H_.loc[m_, "hit|src_zone_hour_speed|qr_ogd"].to_numpy().astype(int)
    n10, n01 = int(((a_ == 1) & (b_ == 0)).sum()), int(((a_ == 0) & (b_ == 1)).sum())
    pv = binomtest(min(n10, n01), n10 + n01).pvalue
    add("heldWorstBPairedP", r2(pv), pv, f"{HH}: test_jun_b, hopkind=2; exact McNemar (binomial) test of hit|mvp_log vs hit|qr_ogd; discordant {n10} vs {n01}", HH)
    # --- track custody (M5): paper generated/data/tab_custody.csv
    TCp = PAPER / "generated" / "data" / "tab_custody.csv"
    TC = pd.read_csv(TCp, comment="#")
    tc_src = f"paper generated/data/tab_custody.csv (paper commit {commit_of_paper('generated/data/tab_custody.csv')})"
    a5 = TC[(TC.start == "all") & (TC.k == 5)]
    add("custFiveMinPct", f"{100 * a5.custody.min():.0f}", a5.custody.min(), f"{tc_src}: start=all, k=5, min over methods and segments of custody, percent", None)
    add("custFiveMaxPct", f"{100 * a5.custody.max():.0f}", a5.custody.max(), f"{tc_src}: start=all, k=5, max over methods and segments of custody, percent", None)
    gap = 100 * (a5.custody - a5.indep)
    add("custIndepGapMin", f"{gap.min():.1f}", gap.min(), f"{tc_src}: start=all, k=5, min of 100 (custody - indep), percentage points", None)
    add("custIndepGapMax", f"{gap.max():.1f}", gap.max(), f"{tc_src}: start=all, k=5, max of 100 (custody - indep), percentage points", None)
    mg_ = a5[a5.method.isin(["mvp_log", "qr_ogd"])].custody; rf_ = a5[a5.method.isin(["oracle", "aci"])].custody
    add("custFiveMultiMin", r3(mg_.min()), mg_.min(), f"{tc_src}: start=all, k=5, methods mvp_log and qr_ogd, both segments; min", None)
    add("custFiveMultiMax", r3(mg_.max()), mg_.max(), f"{tc_src}: same; max", None)
    add("custFiveRefMin", r3(rf_.min()), rf_.min(), f"{tc_src}: start=all, k=5, methods oracle and aci, both segments; min", None)
    add("custFiveRefMax", r3(rf_.max()), rf_.max(), f"{tc_src}: same; max", None)
    ra = TC[TC.start == "re-acquired"].set_index(["method", "seg", "k"]).custody
    for meth, mn in [("mvp_log", "MvpLog"), ("oracle", "Oracle")]:
        for sn in ["A", "B"]:
            for k_ in ([1, 5] if sn == "B" else [5]):          # segment A: only k = 5 is quoted
                v = ra.loc[(meth, sn, k_)]
                add(f"custReacq{mn}{sn}K{WORDS[k_].capitalize()}", r3(v), v, f"{tc_src}: start=re-acquired, method={meth}, segment {sn}, k={k_}, custody", None)
    # later hops (hopkind=0): recall gap of the multigroup methods to the oracle (group_oracle_groups.csv)
    GG = "results/porto_cctv_confirm_posthoc/group_oracle/group_oracle_groups.csv"
    G_ = pd.read_csv(REPO / GG); G_ = G_[G_.key == "hopkind=0"].set_index(["segment", "method"])
    gaps = [100 * (G_.loc[(sg, "oracle"), "recall"] - G_.loc[(sg, mt), "recall"]) for sg in ("test_jun_a", "test_jun_b") for mt in ("mvp_log", "qr_ogd")]
    assert all(G_.loc[(sg, mt), "cost_cam_s"] > G_.loc[(sg, "oracle"), "cost_cam_s"] for sg in ("test_jun_a", "test_jun_b") for mt in ("mvp_log", "qr_ogd"))
    add("custLaterRecallGapMin", f"{min(gaps):.1f}", min(gaps), f"{GG}: key=hopkind=0 (later hops), 100 (recall of oracle - recall of mvp_log or qr_ogd), segments A and B; min (cost of both methods > oracle there, asserted)", GG)
    add("custLaterRecallGapMax", f"{max(gaps):.1f}", max(gaps), f"{GG}: same; max", GG)
    # --- geometry / horizon sensitivity (M3)
    GC = {n_: yaml.safe_load(open(REPO / f"configs/porto_cctv_confirm_geom_{n_}.yaml", encoding="utf-8")) for n_ in ["r30", "r75", "tmax300", "tmax900"]}
    add("geomRadiusSmall", f"{GC['r30']['events']['camera_radius_m']}", GC['r30']['events']['camera_radius_m'], "configs/porto_cctv_confirm_geom_r30.yaml: events.camera_radius_m (= cameras.merge_radius_m)", "configs/porto_cctv_confirm_geom_r30.yaml")
    add("geomRadiusLarge", f"{GC['r75']['events']['camera_radius_m']}", GC['r75']['events']['camera_radius_m'], "configs/porto_cctv_confirm_geom_r75.yaml: events.camera_radius_m (= cameras.merge_radius_m)", "configs/porto_cctv_confirm_geom_r75.yaml")
    add("geomTmaxShort", f"{GC['tmax300']['events']['t_max_s']}", GC['tmax300']['events']['t_max_s'], "configs/porto_cctv_confirm_geom_tmax300.yaml: events.t_max_s", "configs/porto_cctv_confirm_geom_tmax300.yaml")
    add("geomTmaxLong", f"{GC['tmax900']['events']['t_max_s']}", GC['tmax900']['events']['t_max_s'], "configs/porto_cctv_confirm_geom_tmax900.yaml: events.t_max_s", "configs/porto_cctv_confirm_geom_tmax900.yaml")
    GS = "results/porto_cctv_confirm_posthoc/geometry/geometry_seeds.csv"
    GP = "results/porto_cctv_confirm_posthoc/geometry/geometry_seed_pass.csv"
    S_g = pd.read_csv(REPO / GS); P_g = pd.read_csv(REPO / GP).set_index(["setting", "method"])
    Mg = S_g[(S_g.setting != "base") & S_g.method.isin(["mvp_log", "qr_ogd"])]
    ps = Mg.groupby(["setting", "method", "seed"]).cost_ratio.mean()      # per seed: mean over segments A and B
    add("geomMultiCostSeedMeanMin", r2(ps.min()), ps.min(), f"{GS}: settings r30, r75, tmax300, tmax900; mvp_log and qr_ogd; per evaluation seed 0-4 the mean over A and B of cost / hindsight oracle; min", GS)
    add("geomMultiCostSeedMeanMax", r2(ps.max()), ps.max(), f"{GS}: same; max", GS)
    mb = S_g[S_g.method.isin(["static", "aci", "oracle"])].below94
    add("geomMarginalBelowMin", f"{mb.min()}", mb.min(), f"{GS}: methods static, aci, oracle; all settings (base and four) and evaluation seeds 0-4; min of below94 (25 groups)", GS)
    add("geomMarginalBelowMax", f"{mb.max()}", mb.max(), f"{GS}: same; max of below94", GS)
    wb = S_g[(S_g.setting == "tmax900") & (S_g.method == "mvp_log") & (S_g.segment == "test_jun_b")].worst
    assert (S_g[(S_g.setting == "tmax900") & (S_g.method == "mvp_log") & (S_g.segment == "test_jun_b")].worst_key == "hopkind=2").all()
    add("geomTmaxLongMvpLogWorstB", r2(wb.mean()), wb.mean(), f"{GS}: setting=tmax900, mvp_log, test_jun_b, worst (re-acquisition group in every seed); mean over seeds 0-4 to 2 decimals (range {wb.min():.4f}-{wb.max():.4f})", GS)
    ns_ = int(P_g.n_seeds.max()); assert (P_g.n_seeds == ns_).all()
    add("geomSeedCountWord", WORDS[ns_], ns_, f"{GP}: n_seeds (evaluation seeds per setting), spelled out", GP)
    qp = int(P_g.loc[("tmax900", "qr_ogd"), "n_pass"])
    add("geomTmaxLongQrOgdPassWord", WORDS[qp], qp, f"{GP}: setting=tmax900, method=qr_ogd, n_pass (of 5 seeds), spelled out", GP)
    add("geomTmaxLongQrOgdCostMin", r2(P_g.loc[("tmax900", "qr_ogd"), "cost_ratio_mean_min"]), P_g.loc[("tmax900", "qr_ogd"), "cost_ratio_mean_min"],
        f"{GP}: setting=tmax900, qr_ogd, cost_ratio_mean_min (per seed: mean over A and B of cost / hindsight oracle; min over seeds)", GP)
    add("geomTmaxLongQrOgdCostMax", r2(P_g.loc[("tmax900", "qr_ogd"), "cost_ratio_mean_max"]), P_g.loc[("tmax900", "qr_ogd"), "cost_ratio_mean_max"],
        f"{GP}: same; max over seeds", GP)
    # --- Section 5: pre-outage cost change of mvp_log across the outage runs (held-out period)
    OSu = "results/porto_cctv_confirm_posthoc/outage_suite"
    t0_ = pd.Timestamp("2014-06-21", tz=cfg["timezone"]).timestamp()
    def _pre(run):
        X = pd.read_parquet(REPO / OSu / run / "hits.parquet", columns=["t_exit", "cost|src_zone_hour_speed|mvp_log"])
        return X.loc[X.t_exit < t0_ - 3600, "cost|src_zone_hour_speed|mvp_log"].astype(float).mean()
    c0_ = _pre("none_s7")
    runs_ = sorted(r_ for r_ in os.listdir(REPO / OSu) if (REPO / OSu / r_ / "hits.parquet").exists() and r_ != "none_s7")
    dd = np.abs([100 * (_pre(r_) - c0_) / c0_ for r_ in runs_])
    add("outPreCostDiffMinPct", f"{dd.min():.2f}", dd.min(), f"{OSu}/<run>/hits.parquet: held-out period, hops with t_exit < outage start (2014-06-21) - 1 h; |mean cost of mvp_log - same for none_s7| / none_s7, percent; min over {len(runs_)} outage runs", OSu + "/all_periods_summary.csv")
    add("outPreCostDiffMaxPct", f"{dd.max():.1f}", dd.max(), f"same; max over the {len(runs_)} outage runs", OSu + "/all_periods_summary.csv")
    # --- Section 5 (2026-10-02 shortened text): the bar lies "one point" below the target (percentage points, spelled out)
    gap_pp = round(100 * (cfg["eval"]["target_recall"] - cfg["eval"]["group_bar"]))
    assert abs(100 * (cfg["eval"]["target_recall"] - cfg["eval"]["group_bar"]) - gap_pp) < 1e-9
    add("barGapPointsWord", WORDS[gap_pp], gap_pp, f"{CONFIG}: eval.target_recall - eval.group_bar, in percentage points, spelled out", CONFIG)
    # --- Section 5: cameras on the current portal (not a result file)
    add("portalCamerasCurrent", "243", 243, "JD confirmation (2026-09, current open-data portal of the Municipality of Porto); not from a result file. The study uses the July 2025 version (239 cameras)", None)
    # --- v6 appendix B (instruction 14 §1(b)): cameras added since the snapshot, by objectid against the current portal file
    CUR = REPO / "work/cctv_check12/current.geojson"     # downloaded for report 12 (m), git-ignored
    cur = {f_["properties"]["objectid"]: f_["geometry"]["coordinates"] for f_ in _json.load(open(CUR, encoding="utf-8"))["features"]}
    old = {f_["properties"]["objectid"]: f_["geometry"]["coordinates"] for f_ in gj}
    new_ids = sorted(set(cur) - set(old))
    moved = [k for k in old if k in cur and max(abs(a - b) for a, b in zip(np.ravel(old[k]), np.ravel(cur[k]))) > 1e-7]
    assert not set(old) - set(cur) and not moved and len(cur) - len(old) == len(new_ids) == 243 - len(gj)
    add("portalCamerasAdded", _w[len(new_ids)], len(new_ids),
        f"work/cctv_check12/current.geojson (current portal GeoJSON, SHA-256 {_hl.sha256(CUR.read_bytes()).hexdigest()}; not "
        f"tracked) against {cam['geojson']}: objectids not in the snapshot ({', '.join(map(str, new_ids))}); removed 0, moved "
        f"(> 1e-7 degrees) 0; spelled out; = portalCamerasCurrent - numCamerasRaw", cam["geojson"])
    add("repoURL", r"\url{https://github.com/jdlee6461/ccpilot-release}", "https://github.com/jdlee6461/ccpilot-release",
        "snapshot repository (instruction 29 §3; created private 2026-11-03, public after JD approval); not a result", None)
    add("repoAccessDate", "[date]", "placeholder",
        "placeholder for the access date of the repository = date it is made public (instruction 29 §3); not a result", None)
    add("repoDOI", r"\url{https://doi.org/10.5281/zenodo.23934654}", "10.5281/zenodo.23934654",
        "Zenodo DOI reserved by JD on 2026-11-03 (verdict 35, instruction 28 §1); resolves only after publication; not a result",
        None)
    # --- v6 (instruction 14 §1(b)): float numbers of the repository bundle cited by the paper ("Table R16")
    import re as _re
    BAUX = PAPER / "supplementary_tables" / "supplementary_tables.aux"      # written by `make repotables` (bundle at dfbdb0a)
    baux = BAUX.read_text(errors="replace")
    bpdf = _hl.sha256((PAPER / "supplementary_tables" / "supplementary_tables.pdf").read_bytes()).hexdigest()
    for name, lab, cap in (("bundleTabGeometry", "tab:geometry", "Sensitivity to the observation radius and the horizon"),
                           ("bundleTabFeedbackShare", "tab:sensitivity", "Sensitivity on the held-out period")):
        m_ = _re.search(r"\\newlabel\{" + _re.escape(lab) + r"\}\{\{(R\d+)\}\{(\d+)\}\{([^}]*)", baux)
        assert m_ and m_.group(3).startswith(cap), lab
        add(name, m_.group(1), m_.group(1),
            f"supplementary_tables/supplementary_tables.aux (paper repository; bundle PDF SHA-256 {bpdf}): \\newlabel{{{lab}}}, "
            f"float number (bundle page {m_.group(2)}; caption '{cap} ...')", None)
    # --- v6 appendix A (instruction 14 §1(b)): earlier selection criteria per evaluation seed (POST HOC seeds 0-4)
    SD = "results/porto_cctv_confirm_posthoc/seeds_prereg25/seeds_all.csv"
    SDf = pd.read_csv(REPO / SD)
    for meth, mn in [("mvp_log", "MvpLog"), ("qr_ogd", "QrOgd")]:
        d_ = SDf[(SDf["label"] == meth) & (SDf["predictor"] == "src_zone_hour_speed")]
        assert sorted(d_.seed.unique()) == [0, 1, 2, 3, 4] and len(d_) == 10
        ok = d_.groupby("seed").apply(lambda x: (x.n_groups_sig_below_bar == 0).all() and x.cost_over_oracle.mean() <= cf)
        add(f"held{mn}SeedsPass", f"{int(ok.sum()):d}", int(ok.sum()),
            f"{SD}: label={meth}, predictor=src_zone_hour_speed, seeds 0-4 (POST HOC), segments test_jun_a, test_jun_b; seeds "
            f"with n_groups_sig_below_bar == 0 (prereg_25, Wilson upper bound < groupBar) in both segments and mean "
            f"cost_over_oracle <= costFactor (passing seeds: {list(ok.index[ok])})", SD)
        # v11 (verdict 35 A12, instruction 28 §1): "in three of five seeds"
        add(f"held{mn}SeedsPassWord", WORDS[int(ok.sum())], int(ok.sum()), f"same as held{mn}SeedsPass, spelled out", SD)

    # ---------------------------------------------------------------- write
    out = PAPER / "generated" / "numbers.tex"
    lines = ["% AUTO-GENERATED by scripts/make_numbers.py -- DO NOT EDIT.",
             "% Each macro: source file | row filter | column | formula | ccpilot commit that last changed the source (git log in the ccpilot repository; paper/ is a separate repository).", ""]
    for name, text, raw, src in MACROS:
        lines.append(f"% {src}")
        lines.append(f"\\newcommand{{\\{name}}}{{{text}\\xspace}}")   # xspace: keeps the following space in text
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(PAPER / "generated" / "numbers_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["macro", "value", "raw", "source"])
        for name, text, raw, src in MACROS:
            w.writerow([name, text, repr(float(raw)) if isinstance(raw, (int, float, np.floating, np.integer)) else raw, src])
    print(f"{len(MACROS)} macros -> {out}")


if __name__ == "__main__":
    main()
