"""Trajectories -> camera sightings -> hop transitions with multi-label ground truth.

Definitions (overlap-agnostic):
  sighting  : maximal run of time a trip is inside one camera's disk (radius R).
  episode   : maximal interval during which the trip is visible in >= 1 camera
              (overlapping sightings of different cameras are merged).
  transition: from the end of episode k (t_exit, source camera = the camera whose
              sighting ends last) to episode k+1 if it starts within T_max,
              otherwise the transition is an 'exit' (left network / parked / trip end).
  truth     : all (camera, time-bin) pairs in which the trip is visible during
              episode k+1, bins measured from t_exit with width delta.
              A search set 'hits' iff it contains at least one truth pair.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from tqdm import tqdm

from .geo import local_hour_dow, hour_group


def extract_sightings(traj, cams, radius, step, max_overlap=4, h_heading_s=4.0,
                      chunk_points=10_000_000):
    traj = traj.sort_values(["trip_id", "t"], kind="stable")
    trip = traj["trip_id"].to_numpy(); t = traj["t"].to_numpy()
    x = traj["x"].to_numpy(); y = traj["y"].to_numpy()
    cam_xy = cams[["x", "y"]].to_numpy()
    ncam = len(cam_xy)
    tree = cKDTree(cam_xy)
    k = min(max_overlap, ncam)

    bnd = np.flatnonzero(np.diff(trip)) + 1
    starts = np.r_[0, bnd]; ends = np.r_[bnd, len(trip)]

    H_trip, H_cam, H_t, H_x, H_y = [], [], [], [], []
    buf_trip, buf_t, buf_x, buf_y, buf_n = [], [], [], [], 0

    def flush():
        nonlocal buf_trip, buf_t, buf_x, buf_y, buf_n
        if buf_n == 0:
            return
        bt = np.concatenate(buf_t); bx = np.concatenate(buf_x); by = np.concatenate(buf_y)
        btr = np.concatenate(buf_trip)
        _, idx = tree.query(np.column_stack([bx, by]), k=k, distance_upper_bound=radius)
        idx = idx.reshape(len(bx), -1)
        pi, kj = np.nonzero(idx < ncam)
        H_trip.append(btr[pi]); H_cam.append(idx[pi, kj]); H_t.append(bt[pi])
        H_x.append(bx[pi]); H_y.append(by[pi])
        buf_trip, buf_t, buf_x, buf_y, buf_n = [], [], [], [], 0

    for s, e in tqdm(zip(starts, ends), total=len(starts), desc="densify+query"):
        if e - s < 2:
            continue
        grid = np.arange(t[s], t[e - 1] + 1e-9, step)
        buf_t.append(grid)
        buf_x.append(np.interp(grid, t[s:e], x[s:e]))
        buf_y.append(np.interp(grid, t[s:e], y[s:e]))
        buf_trip.append(np.full(len(grid), trip[s], dtype=np.int64))
        buf_n += len(grid)
        if buf_n >= chunk_points:
            flush()
    flush()

    tr = np.concatenate(H_trip); cm = np.concatenate(H_cam); tt = np.concatenate(H_t)
    xx = np.concatenate(H_x); yy = np.concatenate(H_y)
    o = np.lexsort((tt, cm, tr))
    tr, cm, tt, xx, yy = tr[o], cm[o], tt[o], xx[o], yy[o]
    new = np.ones(len(tr), bool)
    new[1:] = (tr[1:] != tr[:-1]) | (cm[1:] != cm[:-1]) | (tt[1:] - tt[:-1] > 1.5 * step)
    first = np.flatnonzero(new); last = np.r_[first[1:] - 1, len(tr) - 1]
    hp = max(1, int(round(h_heading_s / step)))
    hidx = np.maximum(first, last - hp)
    dx = xx[last] - xx[hidx]; dy = yy[last] - yy[hidx]; dt = tt[last] - tt[hidx]
    speed = np.where(dt > 0, np.hypot(dx, dy) / np.maximum(dt, 1e-9), 0.0)
    heading = np.arctan2(dy, dx)
    cam_ids = cm[first]
    rel = np.arctan2(yy[last] - cam_xy[cam_ids, 1], xx[last] - cam_xy[cam_ids, 0])
    # exit zone: 0=E, 1=N, 2=W, 3=S sector of the exit point relative to camera centre
    zone = (np.floor(np.mod(rel + np.pi / 4, 2 * np.pi) / (np.pi / 2)).astype(int)) % 4
    return pd.DataFrame({
        "trip_id": tr[first], "cam": cam_ids, "t_in": tt[first], "t_out": tt[last],
        "speed_out": speed, "heading_out": heading, "zone": zone,
    }).sort_values(["trip_id", "t_in"], kind="stable").reset_index(drop=True)


def build_transitions(sight, cfg):
    ev = cfg["events"]
    step = ev["interp_step_s"]; t_max = ev["t_max_s"]; delta = ev["bin_s"]
    n_bins = int(np.ceil(t_max / delta))
    tz = cfg["timezone"]

    trip = sight["trip_id"].to_numpy(); cam = sight["cam"].to_numpy()
    tin = sight["t_in"].to_numpy(); tout = sight["t_out"].to_numpy()
    zone = sight["zone"].to_numpy(); spd = sight["speed_out"].to_numpy()
    bnd = np.flatnonzero(np.diff(trip)) + 1
    starts = np.r_[0, bnd]; ends = np.r_[bnd, len(trip)]

    rec = {k: [] for k in ["trip_id", "src", "t_exit", "zone", "speed_out", "is_exit",
                           "t_arrive", "first_cam", "chain", "hop"]}
    tr_ids, tcam, tb0, tb1 = [], [], [], []
    tid = 0
    for s, e in tqdm(zip(starts, ends), total=len(starts), desc="transitions"):
        # merge sightings into episodes
        eps = []
        cur = [s]; cur_end = tout[s]
        for i in range(s + 1, e):
            if tin[i] <= cur_end + 1.5 * step:
                cur.append(i); cur_end = max(cur_end, tout[i])
            else:
                eps.append(cur); cur = [i]; cur_end = tout[i]
        eps.append(cur)
        chain = 0; hop = 0
        for k, members in enumerate(eps):
            m = np.asarray(members)
            j_src = m[np.argmax(tout[m])]
            t_exit = tout[j_src]
            is_exit = True; t_arr = np.nan; fcam = -1
            if k + 1 < len(eps):
                nxt = np.asarray(eps[k + 1])
                t_arr = tin[nxt].min()
                if t_arr - t_exit <= t_max:
                    is_exit = False
                    fcam = cam[nxt[np.argmin(tin[nxt])]]
                    for j in nxt:
                        b0 = max(0, int(np.floor((tin[j] - t_exit) / delta)))
                        b1 = min(n_bins - 1, int(np.floor((tout[j] - t_exit) / delta)))
                        if b0 <= n_bins - 1:
                            tr_ids.append(tid); tcam.append(cam[j]); tb0.append(b0); tb1.append(b1)
            rec["trip_id"].append(trip[s]); rec["src"].append(cam[j_src])
            rec["t_exit"].append(t_exit); rec["zone"].append(zone[j_src])
            rec["speed_out"].append(spd[j_src]); rec["is_exit"].append(is_exit)
            rec["t_arrive"].append(t_arr); rec["first_cam"].append(fcam)
            rec["chain"].append(chain); rec["hop"].append(hop)
            tid += 1
            if is_exit:
                chain += 1; hop = 0
            else:
                hop += 1
    trans = pd.DataFrame(rec)
    trans.insert(0, "tr_id", np.arange(len(trans)))
    hours, dow = local_hour_dow(trans["t_exit"].to_numpy(), tz)
    trans["hour"] = hours; trans["dow"] = dow
    trans["hgroup"] = hour_group(hours, np.asarray(ev["hour_group_edges"]))
    truth = pd.DataFrame({"tr_id": tr_ids, "cam": tcam, "b0": tb0, "b1": tb1})
    # one row per (transition, camera): union of bin ranges (rare multi-visits over-covered)
    truth = truth.groupby(["tr_id", "cam"], as_index=False).agg(b0=("b0", "min"), b1=("b1", "max"))
    return trans, truth, n_bins
