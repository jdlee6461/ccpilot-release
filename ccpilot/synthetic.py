"""Synthetic grid-city trajectories with a controllable regime shift.

Purpose: an end-to-end sanity check of the pipeline where the ground truth of the
shift is known. Output format is identical to the Porto loader:
    trajectories: trip_id, t (unix s), x, y (metres)
    cameras:      cam_id, x, y
"""
import numpy as np
import pandas as pd
import networkx as nx

from .geo import date_to_unix


def _hour_speed_factor(h):
    if 7 <= h < 9 or 17 <= h < 19:
        return 0.6          # rush hour
    if 0 <= h < 5:
        return 1.2          # night
    return 1.0


def _sample_start_hours(rng, n):
    # mixture: two rush peaks + flat daytime base
    comp = rng.choice(3, size=n, p=[0.3, 0.3, 0.4])
    h = np.where(comp == 0, rng.normal(8.0, 1.0, n),
         np.where(comp == 1, rng.normal(18.0, 1.2, n), rng.uniform(5.0, 24.0, n)))
    return np.mod(h, 24.0)


def generate(cfg):
    s = cfg["synthetic"]
    rng = np.random.default_rng(s.get("seed", 0))
    n = s["grid_size"]
    sp = s["spacing_m"]

    G = nx.grid_2d_graph(n, n)
    pos = {v: (v[0] * sp, v[1] * sp) for v in G.nodes}
    for u, v in G.edges:
        arterial = (u[0] == v[0] and u[0] % 4 == 0) or (u[1] == v[1] and u[1] % 4 == 0)
        G.edges[u, v]["speed"] = 13.9 if arterial else 8.3
        G.edges[u, v]["length"] = sp

    nodes = list(G.nodes)
    center = ((n - 1) / 2.0, (n - 1) / 2.0)
    dist_c = np.array([np.hypot(v[0] - center[0], v[1] - center[1]) for v in nodes])
    central = [v for v, d in zip(nodes, dist_c) if d <= n * 0.2]

    # cameras at random intersections
    cam_nodes_idx = rng.choice(len(nodes), size=s["n_cameras"], replace=False)
    cams = pd.DataFrame({
        "cam_id": np.arange(s["n_cameras"]),
        "x": [pos[nodes[i]][0] for i in cam_nodes_idx],
        "y": [pos[nodes[i]][1] for i in cam_nodes_idx],
    })

    # regime shift: closed central edges, slower traffic, event attractor
    G_shift = G.copy()
    central_edges = [e for e in G.edges if e[0] in central or e[1] in central]
    n_close = min(s["shift"]["n_closed_edges"], len(central_edges))
    close_idx = rng.choice(len(central_edges), size=n_close, replace=False)
    G_shift.remove_edges_from([central_edges[i] for i in close_idx])
    if not nx.is_connected(G_shift):  # keep largest component usable
        G_shift = G_shift.subgraph(max(nx.connected_components(G_shift), key=len)).copy()
    event_node = nodes[rng.integers(len(nodes))]

    t0_day = date_to_unix(s["start_date"], cfg["timezone"])
    rows_tid, rows_t, rows_x, rows_y = [], [], [], []
    trip_id = 0
    for d in range(s["n_days"]):
        shifted = d >= s["shift"]["start_day"]
        g = G_shift if shifted else G
        gnodes = list(g.nodes)
        regime_speed = s["shift"]["speed_factor"] if shifted else 1.0
        hours = _sample_start_hours(rng, s["trips_per_day"])
        for h in hours:
            # origin / destination
            if 6.5 <= h < 10 and rng.random() < 0.6:
                o = gnodes[rng.integers(len(gnodes))]
                dst = central[rng.integers(len(central))]
            elif 16 <= h < 20 and rng.random() < 0.6:
                o = central[rng.integers(len(central))]
                dst = gnodes[rng.integers(len(gnodes))]
            else:
                o = gnodes[rng.integers(len(gnodes))]
                dst = gnodes[rng.integers(len(gnodes))]
            if shifted and rng.random() < s["shift"]["event_share"]:
                dst = event_node
            if o == dst or o not in g or dst not in g:
                continue
            hf = _hour_speed_factor(int(h))
            vf = rng.lognormal(0.0, 0.15)
            # per-trip perturbed travel-time weights -> route diversity
            noise = {e: rng.lognormal(0.0, 0.25) for e in g.edges}
            def w(u, v, attr, _n=noise):
                key = (u, v) if (u, v) in _n else (v, u)
                return attr["length"] / attr["speed"] * _n[key]
            try:
                path = nx.shortest_path(g, o, dst, weight=w)
            except nx.NetworkXNoPath:
                continue
            # piecewise-linear time/position knots with stops at intersections
            t = t0_day + d * 86400 + h * 3600
            kt, kx, ky = [t], [pos[path[0]][0]], [pos[path[0]][1]]
            for a, b in zip(path[:-1], path[1:]):
                e = g.edges[a, b]
                t += e["length"] / (e["speed"] * hf * vf * regime_speed)
                kt.append(t); kx.append(pos[b][0]); ky.append(pos[b][1])
                if b != path[-1] and rng.random() < s["stop_prob"]:
                    t += rng.uniform(0, s["max_stop_s"])
                    kt.append(t); kx.append(pos[b][0]); ky.append(pos[b][1])
            kt = np.asarray(kt); kx = np.asarray(kx); ky = np.asarray(ky)
            ts = np.arange(kt[0], kt[-1], s["gps_interval_s"])
            if len(ts) < 2:
                continue
            xs = np.interp(ts, kt, kx) + rng.normal(0, s["gps_noise_m"], len(ts))
            ys = np.interp(ts, kt, ky) + rng.normal(0, s["gps_noise_m"], len(ts))
            rows_tid.append(np.full(len(ts), trip_id, dtype=np.int64))
            rows_t.append(ts); rows_x.append(xs); rows_y.append(ys)
            trip_id += 1

    traj = pd.DataFrame({
        "trip_id": np.concatenate(rows_tid),
        "t": np.concatenate(rows_t),
        "x": np.concatenate(rows_x),
        "y": np.concatenate(rows_y),
    })
    return traj, cams
