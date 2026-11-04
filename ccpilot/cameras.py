"""Camera placement for trajectory datasets without real camera locations.

Density placement: rank grid cells by the number of *distinct moving trips*
passing through them (stationary taxis at stands are excluded), then pick cells
greedily subject to a minimum spacing. This approximates 'busy intersections';
it is NOT identical to Spatula's intersection placement (see README).
"""
import numpy as np
import pandas as pd


def place_by_density(traj, n_cameras, min_spacing_m, cell_m=50.0, min_speed_mps=2.0,
                     region_xy=None):
    trip = traj["trip_id"].to_numpy()
    t = traj["t"].to_numpy(); x = traj["x"].to_numpy(); y = traj["y"].to_numpy()
    same = trip[1:] == trip[:-1]
    v = np.zeros(len(x))
    dt = np.diff(t)
    v[1:] = np.where(same & (dt > 0), np.hypot(np.diff(x), np.diff(y)) / np.maximum(dt, 1e-9), 0.0)
    m = v >= min_speed_mps
    if region_xy is not None:
        x0, y0, x1, y1 = region_xy
        m &= (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    cx = np.floor(x[m] / cell_m).astype(np.int64)
    cy = np.floor(y[m] / cell_m).astype(np.int64)
    df = pd.DataFrame({"trip": trip[m], "cx": cx, "cy": cy}).drop_duplicates()
    cnt = df.groupby(["cx", "cy"]).size().sort_values(ascending=False)

    chosen = []
    for (ix, iy), _ in cnt.items():
        px, py = (ix + 0.5) * cell_m, (iy + 0.5) * cell_m
        if all((px - qx) ** 2 + (py - qy) ** 2 >= min_spacing_m ** 2 for qx, qy in chosen):
            chosen.append((px, py))
            if len(chosen) >= n_cameras:
                break
    cams = pd.DataFrame(chosen, columns=["x", "y"])
    cams.insert(0, "cam_id", np.arange(len(cams)))
    return cams


def load_cctv_geojson(path, proj_center, merge_radius_m=50.0, exclude_tunnel=True, bbox=None):
    """Real camera locations from a GeoJSON point layer (e.g. Porto traffic-management CCTV).

    Cameras closer than `merge_radius_m` (complete linkage: every pair inside a site is
    within the radius) are merged into one camera SITE located at their centroid; a site
    typically corresponds to one intersection watched by several directional cameras.
    Tunnel cameras (em_tunel == 'Sim') are dropped because GPS is unreliable in tunnels.
    """
    import json
    from scipy.cluster.hierarchy import fcluster, linkage
    from .geo import lonlat_to_xy
    g = json.load(open(path, encoding="utf-8"))
    rows = []
    for f in g["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        p = f.get("properties", {}) or {}
        if exclude_tunnel and str(p.get("em_tunel", "")).strip().lower() == "sim":
            continue
        if bbox is not None and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
            continue
        rows.append((lon, lat, str(p.get("cctv_id", "")).strip()))
    df = pd.DataFrame(rows, columns=["lon", "lat", "cctv_id"])
    x, y = lonlat_to_xy(df["lon"], df["lat"], *proj_center)
    df["x"], df["y"] = x, y
    if merge_radius_m and merge_radius_m > 0 and len(df) > 1:
        lab = fcluster(linkage(df[["x", "y"]].to_numpy(), "complete"), merge_radius_m, "distance")
    else:
        lab = np.arange(1, len(df) + 1)
    df["site"] = lab
    sites = df.groupby("site").agg(x=("x", "mean"), y=("y", "mean"), lon=("lon", "mean"), lat=("lat", "mean"),
                                   n_cams=("cctv_id", "size"),
                                   cctv_ids=("cctv_id", lambda s: ",".join(sorted(s)))).reset_index(drop=True)
    sites.insert(0, "cam_id", np.arange(len(sites)))
    return sites
