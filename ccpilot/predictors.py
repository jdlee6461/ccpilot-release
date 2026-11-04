"""Predictors that score (camera, time-bin) pairs after a target leaves a source camera.

VisibilityModel
    p(c, b | key) = empirical probability that the target is visible in camera c
    during bin b, where key is a prefix of (src, zone, hgroup, ...).
      levels=['src']                 -> Spatula-like camera-level correlation
      levels=['src', 'zone']         -> CityTrac-like exit-zone conditioning
      levels=['src', 'zone', 'hgroup'] -> additionally time-of-day conditioned
    Hierarchical shrinkage toward the parent level handles sparse keys.
    Selecting all pairs with p >= tau is optimal for expected coverage under
    equal per-pair cost, so a single threshold tau parameterises the set.

SpatulaRule
    Reimplementation of Spatula's filtering rule (spatial threshold on the
    next-camera distribution + time window covering a quantile of arrival
    delays). Parameter values follow our reading of the paper; verify.
"""
import numpy as np
from scipy.ndimage import gaussian_filter1d

TAU_MIN = 1e-12


def candidate_sets(cams, trans_train, radius):
    xy = cams[["x", "y"]].to_numpy()
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    obs = trans_train.loc[~trans_train["is_exit"], ["src", "first_cam"]]
    extra = obs.groupby("src")["first_cam"].unique().to_dict()
    cand = {}
    for c in range(len(xy)):
        s = set(np.flatnonzero(d[c] <= radius).tolist()) | {c}
        s |= set(int(v) for v in extra.get(c, []))
        cand[c] = np.array(sorted(s))
    return cand


def _truth_by_tr(truth):
    g = {}
    for tr, c, b0, b1 in truth[["tr_id", "cam", "b0", "b1"]].itertuples(index=False):
        g.setdefault(tr, []).append((c, b0, b1))
    return g


class VisibilityModel:
    def __init__(self, levels, cand, n_bins, lam=20.0, eps=1e-4, sigma_bins=1.0):
        assert levels[0] == "src"
        self.levels = list(levels); self.cand = cand; self.B = n_bins
        self.lam = lam; self.eps = eps; self.sigma = sigma_bins
        self.row = {s: {c: i for i, c in enumerate(cs)} for s, cs in cand.items()}

    def fit(self, trans, truth_map):
        depth = len(self.levels)
        counts = [dict() for _ in range(depth)]
        nobs = [dict() for _ in range(depth)]
        tr = trans.loc[~trans["is_exit"]]
        keys = tr[self.levels].to_numpy()
        for tid, kf in zip(tr["tr_id"].to_numpy(), keys):
            src = int(kf[0]); rows = self.row[src]
            C = len(self.cand[src])
            key_levels = [tuple(int(v) for v in kf[:d + 1]) for d in range(depth)]
            for d, key in enumerate(key_levels):
                if key not in counts[d]:
                    counts[d][key] = np.zeros((C, self.B), np.float32); nobs[d][key] = 0
                nobs[d][key] += 1
            for c, b0, b1 in truth_map.get(tid, []):
                r = rows.get(int(c))
                if r is None:
                    continue
                for d, key in enumerate(key_levels):
                    counts[d][key][r, b0:b1 + 1] += 1.0
        self.P = [dict() for _ in range(depth)]
        for d in range(depth):
            for key, cmat in counts[d].items():
                if self.sigma > 0:
                    cmat = gaussian_filter1d(cmat, self.sigma, axis=1, mode="constant")
                if d == 0:
                    prior = self.eps
                else:
                    prior = self.P[d - 1][key[:-1]]
                self.P[d][key] = np.clip((cmat + self.lam * prior) / (nobs[d][key] + self.lam), 0, 1).astype(np.float32)
        del counts
        # flatten + sort for fast cost queries; key registry
        self.key_list, self.key_index, self.sorted_vals = [], {}, []
        for d in range(depth):
            for key, M in self.P[d].items():
                self.key_index[(d, key)] = len(self.key_list)
                self.key_list.append((d, key)); self.sorted_vals.append(np.sort(M.ravel()))
        return self

    # ---- camera outage (post-hoc stress test): offline cameras are never searched
    def set_offline(self, offline):
        self.offline = set(int(c) for c in offline)
        self._out = {}          # (base key id) -> (matrix, key id)

    def _outage_version(self, M, k, src):
        if k not in self._out:
            rows = [r for c, r in self.row[src].items() if c in self.offline]
            Mo = M.copy()
            if rows:
                Mo[rows, :] = 0.0
            ko = len(self.key_list); self.key_list.append(("outage", k))
            self.sorted_vals.append(np.sort(Mo.ravel()))
            self._out[k] = (Mo, ko)
        return self._out[k]

    def _matrix_for(self, kf, out=False):
        M, k = self._matrix_for_base(kf)
        if out:
            return self._outage_version(M, k, int(kf[0]))
        return M, k

    def _matrix_for_base(self, kf):
        for d in range(len(self.levels) - 1, -1, -1):
            key = tuple(int(v) for v in kf[:d + 1])
            if key in self.P[d]:
                return self.P[d][key], self.key_index[(d, key)]
        # source never seen in training: flat low-probability matrix
        src = int(kf[0])
        fk = ("fallback", src)
        if not hasattr(self, "_fallback"):
            self._fallback = {}
        if fk not in self.key_index:
            M = np.full((len(self.cand[src]), self.B), self.eps, np.float32)
            self.key_index[fk] = len(self.key_list); self.key_list.append(fk)
            self.sorted_vals.append(np.sort(M.ravel()))
            self._fallback[src] = M
        return self._fallback[src], self.key_index[fk]

    def _rows(self, src, out=False):
        """camera -> matrix row for a query from src (outage-aware subclass may extend it)."""
        return self.row[src]

    def score(self, trans, truth_map, out_mask=None):
        """score_i = max_{truth pairs} p(c,b); hit(tau) <=> score_i >= tau.
        Returns scores, key ids (for cost lookup), structural-miss flags.
        out_mask[i] = True -> query made during a camera outage (offline cameras excluded)."""
        keys = trans[self.levels].to_numpy()
        n = len(trans)
        scores = np.zeros(n); kid = np.zeros(n, dtype=np.int64); struct = np.zeros(n, bool)
        om = np.zeros(n, bool) if out_mask is None else np.asarray(out_mask)
        for i, (tid, kf) in enumerate(zip(trans["tr_id"].to_numpy(), keys)):
            M, k = self._matrix_for(kf, bool(om[i]))
            kid[i] = k
            rows = self._rows(int(kf[0]), bool(om[i]))
            best = 0.0; any_in = False
            for c, b0, b1 in truth_map.get(tid, []):
                r = rows.get(int(c))
                if r is None:
                    continue
                any_in = True
                best = max(best, float(M[r, b0:b1 + 1].max()))
            scores[i] = best
            struct[i] = not any_in
        return scores, kid, struct

    def detect_bins(self, trans, truth_map, tau, out_mask=None):
        """POST-HOC output (2026-10-13, confirm2): first time bin after the exit in which the target is detected
        under threshold(s) tau, i.e. the smallest b over the visibility set (camera c, bins b0..b1) with
        P[c, b] >= tau; -1 if not detected. Detected  <=>  score >= tau (same matrices and rows as score())."""
        tau = np.broadcast_to(np.atleast_1d(np.asarray(tau, float)), (len(trans),))
        keys = trans[self.levels].to_numpy()
        om = np.zeros(len(trans), bool) if out_mask is None else np.asarray(out_mask)
        out = np.full(len(trans), -1, dtype=np.int32)
        for i, (tid, kf) in enumerate(zip(trans["tr_id"].to_numpy(), keys)):
            M, _ = self._matrix_for(kf, bool(om[i]))
            rows = self._rows(int(kf[0]), bool(om[i]))
            t = max(float(tau[i]), TAU_MIN)
            best = -1
            for c, b0, b1 in truth_map.get(tid, []):
                r = rows.get(int(c))
                if r is None:
                    continue
                hit = np.flatnonzero(M[r, b0:b1 + 1].astype(np.float64) >= t)   # float64, as score() (NumPy 2 would compare in float32)
                if len(hit) and (best < 0 or b0 + hit[0] < best):
                    best = int(b0 + hit[0])
            out[i] = best
        return out

    def cost(self, kid, tau, delta):
        """camera-seconds searched for key id(s) at threshold(s) tau."""
        kid = np.atleast_1d(kid); tau = np.broadcast_to(np.atleast_1d(tau), kid.shape)
        out = np.empty(len(kid))
        for i, (k, t) in enumerate(zip(kid, tau)):
            v = self.sorted_vals[k]
            out[i] = (len(v) - np.searchsorted(v, max(t, TAU_MIN), side="left")) * delta
        return out

    def cost_table(self, kids_unique, taus, delta):
        tab = np.empty((len(kids_unique), len(taus)))
        taus = np.maximum(np.asarray(taus), TAU_MIN)
        for i, k in enumerate(kids_unique):
            v = self.sorted_vals[k]
            tab[i] = (len(v) - np.searchsorted(v, taus, side="left")) * delta
        return tab


class OutageAwareModel(VisibilityModel):
    """POST-HOC outage-aware predictor (a separate method; the registered analysis is unchanged).

    During an outage the probability mass of an offline next camera `off` is passed on one step:
        P'(c', b | key) = P(c', b | key)                                    (online c')
                        + sum_{off offline} sum_a Q(off, a | key) * P(c', b - a | off)
    i.e.  p(c'|src) + p(off|src) * p(c'|off)  with the delay distribution composed by convolution.
      Q(off, a | key) : probability that the next camera is `off`, the target leaves `off` in bin a
                        after leaving src, and a next hop follows (training hops src->off whose
                        next transition starts at off and is not an exit; P(.|off) is conditional on that),
                        smoothed and shrunk toward the parent key like P (root prior 0).
      P(. | off)      : source-level visibility matrix of `off` (zone, hour group and speed at `off`
                        are unknown when the query is made).
    Rows are extended with cand(off), so cameras beyond the source's candidate set can be searched.
    LIMITATION (one step only): if the target passes a second offline site after `off`, that mass
    is dropped; chains of offline sites are not composed. Mass beyond T_max is truncated.
    Predictor and thresholds are NOT refitted; only the matrices used during the outage change."""

    def fit_next(self, trans_train, trans_all, delta):
        tr = trans_train.loc[~trans_train["is_exit"]]
        nxt = trans_all.set_index("tr_id")[["trip_id", "src", "t_exit", "is_exit"]].reindex(tr["tr_id"].to_numpy() + 1)
        a = np.floor((nxt["t_exit"].to_numpy() - tr["t_exit"].to_numpy()) / delta)
        ok = ((nxt["trip_id"].to_numpy() == tr["trip_id"].to_numpy()) &
              (nxt["src"].to_numpy() == tr["first_cam"].to_numpy()) & (a >= 0) & (a < self.B) &
              (nxt["is_exit"].to_numpy() == False))   # noqa: E712  P(.|off) is conditional on a next hop
        depth = len(self.levels)
        self.qcnt = [dict() for _ in range(depth)]
        keys = tr[self.levels].to_numpy()
        for kf, c, ai, v in zip(keys, tr["first_cam"].to_numpy(), a, ok):
            if not v:
                continue
            for d in range(depth):
                key = tuple(int(x) for x in kf[:d + 1])
                q = self.qcnt[d].setdefault(key, {}).setdefault(int(c), np.zeros(self.B, np.float32))
                q[int(ai)] += 1.0
        self.qnobs = [dict() for _ in range(depth)]
        for kf in keys:
            for d in range(depth):
                key = tuple(int(x) for x in kf[:d + 1])
                self.qnobs[d][key] = self.qnobs[d].get(key, 0) + 1
        self._q = {}
        return self

    def _qvec(self, d, key, off):
        ck = (d, key, off)
        if ck not in self._q:
            prior = np.zeros(self.B) if d == 0 else self._qvec(d - 1, key[:-1], off)
            cnt = self.qcnt[d].get(key, {}).get(off)
            cnt = np.zeros(self.B) if cnt is None else gaussian_filter1d(cnt, self.sigma, mode="constant") \
                if self.sigma > 0 else cnt
            self._q[ck] = (cnt + self.lam * prior) / (self.qnobs[d].get(key, 0) + self.lam)
        return self._q[ck]

    def set_offline(self, offline):
        super().set_offline(offline)
        self._ext = {}

    def _rows(self, src, out=False):
        if not out or not self.offline:
            return self.row[src]
        if src not in self._ext:
            cams = list(self.cand[src])
            seen = set(cams)
            for off in sorted(c for c in self.row[src] if c in self.offline):
                for c in self.cand.get(off, []):
                    if int(c) not in seen:
                        cams.append(int(c)); seen.add(int(c))
            self._ext[src] = {int(c): i for i, c in enumerate(cams)}
        return self._ext[src]

    def _outage_version(self, M, k, src):
        if k in self._out:
            return self._out[k]
        ext = self._rows(src, True)
        Mo = np.zeros((len(ext), self.B), np.float32)
        Mo[:M.shape[0]] = M
        for c, r in self.row[src].items():
            if c in self.offline:
                Mo[r, :] = 0.0
        d, key = self.key_list[k]
        if isinstance(d, int):
            for off in (c for c in self.row[src] if c in self.offline):
                P0 = self.P[0].get((off,))
                if P0 is None:
                    continue
                q = self._qvec(d, key, off)
                pairs = [(ext[c], r) for c, r in self.row[off].items() if c not in self.offline and c in ext]
                if not pairs:
                    continue
                T = np.array([t for t, _ in pairs]); R = np.array([r for _, r in pairs])
                for ai in np.flatnonzero(q > 1e-7):
                    Mo[T, ai:] += q[ai] * P0[R, :self.B - ai]
        Mo = np.clip(Mo, 0, 1)
        ko = len(self.key_list); self.key_list.append(("outage", k))
        self.sorted_vals.append(np.sort(Mo.ravel()))
        self._out[k] = (Mo, ko)
        return self._out[k]


def _drop_rows(M, rows, off):
    r = [rows[c] for c in off if c in rows]
    if not r:
        return M
    M = M.copy(); M[r, :] = False
    return M


class SpatulaRule:
    def __init__(self, cand, n_bins, delta, s_thresh=0.05, t_quantile=0.98):
        self.cand = cand; self.B = n_bins; self.delta = delta
        self.s_thresh = s_thresh; self.tq = t_quantile
        self.row = {s: {c: i for i, c in enumerate(cs)} for s, cs in cand.items()}

    def fit(self, trans):
        tr = trans.loc[~trans["is_exit"]].copy()
        tr["delay"] = tr["t_arrive"] - tr["t_exit"]
        self.sel = {}
        for src, g in tr.groupby("src"):
            src = int(src)
            share = g["first_cam"].value_counts(normalize=True)
            chosen = share[share >= self.s_thresh].index.tolist() or [share.index[0]]
            M = np.zeros((len(self.cand[src]), self.B), bool)
            for c in chosen:
                r = self.row[src].get(int(c))
                if r is None:
                    continue
                dl = g.loc[g["first_cam"] == c, "delay"].to_numpy()
                b_lo = int(np.floor(dl.min() / self.delta))
                b_hi = int(np.floor(np.quantile(dl, self.tq) / self.delta))
                M[r, max(0, b_lo):min(self.B - 1, b_hi) + 1] = True
            self.sel[src] = M
        return self

    def evaluate(self, trans, truth_map, out_mask=None, offline=()):
        n = len(trans)
        hit = np.zeros(n, bool); cost = np.zeros(n)
        om = np.zeros(n, bool) if out_mask is None else np.asarray(out_mask)
        off = set(int(c) for c in offline)
        for i, (tid, src) in enumerate(zip(trans["tr_id"].to_numpy(), trans["src"].to_numpy())):
            src = int(src)
            M = self.sel.get(src)
            if M is None:  # unseen source: search all candidates, full window
                M = np.ones((len(self.cand[src]), self.B), bool)
            if om[i] and off:
                M = _drop_rows(M, self.row[src], off)
            cost[i] = M.sum() * self.delta
            rows = self.row[src]
            for c, b0, b1 in truth_map.get(tid, []):
                r = rows.get(int(c))
                if r is not None and M[r, b0:b1 + 1].any():
                    hit[i] = True
                    break
        return hit, cost


class CityTracRule:
    """CityTrac-STYLE baseline (our approximation, not the authors' code).

    Captures the two ideas of CityTrac/HyMOT that matter for our comparison:
      * next-camera probabilities conditioned on the source camera AND its exit zone,
        estimated from history (backing off to the source camera when data are sparse);
      * camera selection that satisfies an accuracy constraint computed from the MODEL's
        own probabilities (no calibration): cameras are added greedily by probability,
        each watched over its historical arrival-delay window, until the model-predicted
        success sum_c p(c) * w >= target.
    CityTrac's exact constraint (failure probability bounded relative to the exit
    probability, with an 'importance' level) and its multi-camera field handling are
    NOT reproduced; the `target` levels play the role of the importance setting.
    """

    def __init__(self, cand, n_bins, delta, target=0.95, window_q=0.98, min_n=30):
        self.cand = cand; self.B = n_bins; self.delta = delta
        self.target = target; self.wq = window_q; self.min_n = min_n
        self.row = {s: {c: i for i, c in enumerate(cs)} for s, cs in cand.items()}
        self.cache = {}

    def fit(self, trans):
        tr = trans.loc[~trans["is_exit"]].copy()
        tr["delay"] = tr["t_arrive"] - tr["t_exit"]
        self.p_sz = tr.groupby(["src", "zone"])["first_cam"].value_counts(normalize=True)
        self.n_sz = tr.groupby(["src", "zone"]).size()
        self.p_s = tr.groupby("src")["first_cam"].value_counts(normalize=True)
        lo_q = 0.01
        g = tr.groupby(["src", "first_cam"])["delay"]
        qlo, qhi, cnt = g.quantile(lo_q), g.quantile(self.wq), g.size()
        glo, ghi = tr["delay"].quantile(lo_q), tr["delay"].quantile(self.wq)
        self.win = {}
        for k in cnt.index:
            lo, hi = (qlo[k], qhi[k]) if cnt[k] >= 5 else (glo, ghi)
            self.win[k] = (max(0, int(np.floor(lo / self.delta))), min(self.B - 1, int(np.floor(hi / self.delta))))
        self.wcov = self.wq - lo_q
        self.gwin = (max(0, int(np.floor(glo / self.delta))), min(self.B - 1, int(np.floor(ghi / self.delta))))
        return self

    def _select(self, src, zone):
        key = (src, zone)
        if key in self.cache:
            return self.cache[key]
        C = len(self.cand[src])
        if (src, zone) in self.n_sz.index and self.n_sz[(src, zone)] >= self.min_n:
            p = self.p_sz.loc[(src, zone)]
        elif src in self.p_s.index.get_level_values(0):
            p = self.p_s.loc[src]
        else:
            M = np.ones((C, self.B), bool)
            self.cache[key] = M
            return M
        M = np.zeros((C, self.B), bool)
        acc = 0.0
        for c, pc in p.sort_values(ascending=False).items():
            r = self.row[src].get(int(c))
            if r is None:
                continue
            lo, hi = self.win.get((src, int(c)), self.gwin)
            M[r, lo:hi + 1] = True
            acc += pc * self.wcov
            if acc >= self.target:
                break
        self.cache[key] = M
        return M

    def evaluate(self, trans, truth_map, out_mask=None, offline=()):
        n = len(trans)
        hit = np.zeros(n, bool); cost = np.zeros(n)
        om = np.zeros(n, bool) if out_mask is None else np.asarray(out_mask)
        off = set(int(c) for c in offline)
        for i, (tid, src, zone) in enumerate(zip(trans["tr_id"].to_numpy(), trans["src"].to_numpy(),
                                                  trans["zone"].to_numpy())):
            src = int(src)
            M = self._select(src, int(zone))
            if om[i] and off:
                M = _drop_rows(M, self.row[src], off)
            cost[i] = M.sum() * self.delta
            rows = self.row[src]
            for c, b0, b1 in truth_map.get(tid, []):
                r = rows.get(int(c))
                if r is not None and M[r, b0:b1 + 1].any():
                    hit[i] = True
                    break
        return hit, cost
