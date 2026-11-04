"""Coordinate and time helpers."""
import numpy as np
import pandas as pd

R_EARTH = 6_371_000.0


def lonlat_to_xy(lon, lat, lon0, lat0):
    """Equirectangular projection to local metres (adequate for city scale)."""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    x = np.radians(lon - lon0) * R_EARTH * np.cos(np.radians(lat0))
    y = np.radians(lat - lat0) * R_EARTH
    return x, y


def date_to_unix(date_str, tz):
    """'YYYY-MM-DD' local midnight -> unix seconds."""
    return pd.Timestamp(date_str, tz=tz).timestamp()


def local_hour_dow(t_unix, tz):
    ts = pd.to_datetime(np.asarray(t_unix), unit="s", utc=True).tz_convert(tz)
    return ts.hour.to_numpy(), ts.dayofweek.to_numpy()


def hour_group(hours, edges):
    """edges like [0, 6, 10, 16, 20, 24] -> group index 0..len(edges)-2"""
    return np.clip(np.searchsorted(edges, hours, side="right") - 1, 0, len(edges) - 2)
