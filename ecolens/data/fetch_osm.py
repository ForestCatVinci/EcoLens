"""
Fetch Almaty district boundaries, park polygons, and road network from OSM via OSMnx.
"""

import streamlit as st
import osmnx as ox
import geopandas as gpd
import pandas as pd

ALMATY_PLACE = "Almaty, Kazakhstan"
CRS_METRIC = "EPSG:32643"  # UTM zone 43N — good for Kazakhstan


@st.cache_data(ttl=3600, show_spinner="Fetching district boundaries…")
def fetch_districts() -> gpd.GeoDataFrame:
    """Return Almaty admin level-9 (district) boundaries projected to metric CRS."""
    gdf = ox.geocode_to_gdf(ALMATY_PLACE, by_osmid=False)
    # Try fetching sub-districts (admin_level 9 inside Almaty)
    try:
        districts = ox.features_from_place(
            ALMATY_PLACE,
            tags={"boundary": "administrative", "admin_level": "9"},
        )
        districts = districts[districts.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
        if len(districts) < 3:
            raise ValueError("Too few districts at level 9, trying level 8")
    except Exception:
        districts = ox.features_from_place(
            ALMATY_PLACE,
            tags={"boundary": "administrative", "admin_level": "8"},
        )
        districts = districts[districts.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

    # Keep useful columns
    keep = ["name", "name:en", "geometry"]
    cols = [c for c in keep if c in districts.columns]
    districts = districts[cols].reset_index(drop=True)

    # Use English name when available, fall back to name
    if "name:en" in districts.columns:
        districts["district_name"] = districts["name:en"].fillna(districts.get("name", "Unknown"))
    else:
        districts["district_name"] = districts.get("name", "District")

    districts = districts.to_crs(CRS_METRIC)
    districts["area_m2"] = districts.geometry.area
    districts = districts[districts["area_m2"] > 1e5].reset_index(drop=True)  # drop tiny slivers

    print(f"[fetch_districts] shape: {districts.shape}")
    print(districts[["district_name", "area_m2"]].head())
    return districts


@st.cache_data(ttl=3600, show_spinner="Fetching park polygons…")
def fetch_parks() -> gpd.GeoDataFrame:
    """Return park / green-space polygons inside Almaty."""
    parks = ox.features_from_place(
        ALMATY_PLACE,
        tags={"leisure": ["park", "garden", "nature_reserve"], "landuse": "grass"},
    )
    parks = parks[parks.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    parks = parks[["geometry"]].reset_index(drop=True)
    parks = parks.to_crs(CRS_METRIC)
    parks["park_area_m2"] = parks.geometry.area

    print(f"[fetch_parks] shape: {parks.shape}")
    print(parks.head())
    return parks


@st.cache_data(ttl=3600, show_spinner="Fetching road network…")
def fetch_roads() -> gpd.GeoDataFrame:
    """Return road edges with highway type for Almaty."""
    G = ox.graph_from_place(ALMATY_PLACE, network_type="drive")
    _, edges = ox.graph_to_gdfs(G)
    edges = edges[["highway", "length", "geometry"]].copy().reset_index(drop=True)
    edges = edges.to_crs(CRS_METRIC)

    # Flatten list values in highway column
    edges["highway"] = edges["highway"].apply(
        lambda x: x[0] if isinstance(x, list) else x
    )

    print(f"[fetch_roads] shape: {edges.shape}")
    print(edges["highway"].value_counts().head(10))
    return edges


@st.cache_data(ttl=3600, show_spinner="Computing green score per district…")
def compute_green_score(districts: gpd.GeoDataFrame, parks: gpd.GeoDataFrame) -> pd.Series:
    """Return park area fraction per district (higher fraction = greener)."""
    joined = gpd.sjoin(parks, districts[["district_name", "area_m2", "geometry"]], how="left", predicate="intersects")
    park_by_district = joined.groupby("district_name")["park_area_m2"].sum()
    district_areas = districts.set_index("district_name")["area_m2"]
    green_fraction = park_by_district / district_areas
    green_fraction = green_fraction.reindex(districts["district_name"]).fillna(0)
    print(f"[compute_green_score] green_fraction:\n{green_fraction}")
    return green_fraction  # higher = more green (lower stress)


ROAD_WEIGHTS = {
    "motorway": 5,
    "motorway_link": 5,
    "trunk": 4,
    "trunk_link": 4,
    "primary": 4,
    "primary_link": 4,
    "secondary": 3,
    "secondary_link": 3,
    "tertiary": 2,
    "tertiary_link": 2,
    "residential": 1,
    "living_street": 1,
    "unclassified": 1,
}


@st.cache_data(ttl=3600, show_spinner="Computing traffic score per district…")
def compute_traffic_score(districts: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> pd.Series:
    """Return weighted road length per district area (higher = more traffic stress)."""
    roads = roads.copy()
    roads["weight"] = roads["highway"].map(ROAD_WEIGHTS).fillna(1)
    roads["weighted_length"] = roads["length"] * roads["weight"]

    joined = gpd.sjoin(roads, districts[["district_name", "area_m2", "geometry"]], how="left", predicate="intersects")
    traffic_by_district = joined.groupby("district_name")["weighted_length"].sum()
    district_areas = districts.set_index("district_name")["area_m2"]
    traffic_density = traffic_by_district / district_areas
    traffic_density = traffic_density.reindex(districts["district_name"]).fillna(0)
    print(f"[compute_traffic_score] traffic_density:\n{traffic_density}")
    return traffic_density
