"""
Compute the Ecological Stress Index (ESI) per district.
ESI = 0.4 * air_norm + 0.35 * green_norm + 0.25 * traffic_norm
All component scores are min-max normalized to [0, 1] before combining.
"""

import pandas as pd
import numpy as np
import geopandas as gpd


def minmax_normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a Series to [0, 1]. Returns 0 if constant."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.0, index=series.index)
    return (series - lo) / (hi - lo)


def compute_esi(
    districts: gpd.GeoDataFrame,
    air_score: pd.Series,       # PM2.5 IDW per district (higher = worse)
    green_fraction: pd.Series,  # park area / district area (higher = better → invert for stress)
    traffic_density: pd.Series, # weighted road length / area (higher = worse)
) -> gpd.GeoDataFrame:
    """
    Assemble all scores, normalize, compute ESI, and return enriched GeoDataFrame.
    """
    df = districts.copy()
    idx = df["district_name"]

    # Align all series to district order
    air = air_score.reindex(idx.values).fillna(0)
    green = green_fraction.reindex(idx.values).fillna(0)
    traffic = traffic_density.reindex(idx.values).fillna(0)

    # Normalize
    air_norm = minmax_normalize(air)
    green_norm = minmax_normalize(1 - green)  # invert: less green → higher stress
    traffic_norm = minmax_normalize(traffic)

    df["air_score"] = air.values
    df["green_score"] = green.values
    df["traffic_score"] = traffic.values

    df["air_norm"] = air_norm.values
    df["green_norm"] = green_norm.values
    df["traffic_norm"] = traffic_norm.values

    df["ESI"] = (
        0.40 * df["air_norm"]
        + 0.35 * df["green_norm"]
        + 0.25 * df["traffic_norm"]
    )

    df = df.sort_values("ESI", ascending=False).reset_index(drop=True)

    print(f"[compute_esi] shape: {df.shape}")
    print(df[["district_name", "air_norm", "green_norm", "traffic_norm", "ESI"]].head(10))
    return df
