"""
IDW (Inverse Distance Weighting) interpolation of PM2.5 station values onto district centroids.
"""

import streamlit as st
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree


def idw_interpolate(
    known_xy: np.ndarray,
    known_values: np.ndarray,
    query_xy: np.ndarray,
    power: float = 2.0,
    k: int = 5,
) -> np.ndarray:
    """
    IDW interpolation.
    known_xy: (N, 2) source coordinates
    known_values: (N,) source values
    query_xy: (M, 2) target coordinates
    Returns (M,) interpolated values.
    """
    tree = cKDTree(known_xy)
    k_actual = min(k, len(known_xy))
    dists, idxs = tree.query(query_xy, k=k_actual)

    # Avoid division by zero for exact matches
    dists = np.where(dists == 0, 1e-10, dists)
    weights = 1.0 / (dists ** power)
    weighted_vals = weights * known_values[idxs]
    interpolated = weighted_vals.sum(axis=1) / weights.sum(axis=1)
    return interpolated


@st.cache_data(ttl=3600, show_spinner="Interpolating PM2.5 to districts…")
def interpolate_pm25_to_districts(
    pm25_df: pd.DataFrame,
    districts: gpd.GeoDataFrame,
) -> pd.Series:
    """
    Use IDW to assign an average PM2.5 value to each district centroid.
    pm25_df must have columns: lat, lon, pm25
    districts must be in a metric CRS (centroids computed from that).
    Returns a Series indexed by district_name.
    """
    if pm25_df.empty:
        print("[interpolate] pm25_df is empty — returning zeros")
        return pd.Series(0.0, index=districts["district_name"])

    # Station coords in WGS84 → project to same CRS as districts
    import geopandas as gpd2
    from shapely.geometry import Point

    stations_gdf = gpd2.GeoDataFrame(
        pm25_df,
        geometry=[Point(lon, lat) for lat, lon in zip(pm25_df["lat"], pm25_df["lon"])],
        crs="EPSG:4326",
    ).to_crs(districts.crs)

    known_xy = np.column_stack([stations_gdf.geometry.x, stations_gdf.geometry.y])
    known_values = pm25_df["pm25"].values.astype(float)

    # District centroids
    centroids = districts.geometry.centroid
    query_xy = np.column_stack([centroids.x, centroids.y])

    interpolated = idw_interpolate(known_xy, known_values, query_xy)

    result = pd.Series(interpolated, index=districts["district_name"])
    print(f"[interpolate_pm25_to_districts] result:\n{result}")
    return result
