"""
EcoLens Almaty — Ecological Stress Index Streamlit app.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import geopandas as gpd
import pandas as pd
import json

# ── local modules ──────────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from data.fetch_osm import (
    fetch_districts,
    fetch_parks,
    fetch_roads,
    compute_green_score,
    compute_traffic_score,
)
from data.fetch_openaq import fetch_pm25
from data.interpolate import interpolate_pm25_to_districts
from model.esi import compute_esi

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EcoLens Almaty",
    page_icon="🌿",
    layout="wide",
)

st.title("🌿 EcoLens Almaty — Ecological Stress Index")
st.caption("Air quality · Green space · Traffic load · per district")

# ── sidebar controls ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Layer toggles")
    show_air = st.checkbox("🌫️ Air quality layer", value=False)
    show_green = st.checkbox("🌳 Green space layer", value=False)
    show_traffic = st.checkbox("🚗 Traffic layer", value=False)
    st.markdown("---")
    st.info("Click a district on the map to see its component scores.")

# ── data loading ───────────────────────────────────────────────────────────────
with st.spinner("Loading data (first run may take a few minutes)…"):
    districts = fetch_districts()
    parks = fetch_parks()
    roads = fetch_roads()
    pm25_df = fetch_pm25(days_back=30)

    green_fraction = compute_green_score(districts, parks)
    traffic_density = compute_traffic_score(districts, roads)
    air_score = interpolate_pm25_to_districts(pm25_df, districts)

    esi_gdf = compute_esi(districts, air_score, green_fraction, traffic_density)

# ── helper: pick score column based on sidebar ─────────────────────────────────
def active_layer(esi_gdf: gpd.GeoDataFrame) -> tuple[str, str]:
    """Return (column_name, label) for the currently active single layer, or ESI."""
    if show_air and not show_green and not show_traffic:
        return "air_norm", "Air Stress"
    if show_green and not show_air and not show_traffic:
        return "green_norm", "Green Stress"
    if show_traffic and not show_air and not show_green:
        return "traffic_norm", "Traffic Stress"
    return "ESI", "Ecological Stress Index"


col_name, col_label = active_layer(esi_gdf)

# ── build Folium map ───────────────────────────────────────────────────────────
centroid = esi_gdf.to_crs("EPSG:4326").geometry.centroid
center_lat = centroid.y.mean()
center_lon = centroid.x.mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")

# Convert to WGS84 for Folium
esi_wgs = esi_gdf.to_crs("EPSG:4326").copy()
esi_wgs["__idx"] = esi_wgs.index.astype(str)

folium.Choropleth(
    geo_data=esi_wgs.__geo_interface__,
    data=esi_wgs[["district_name", col_name]],
    columns=["district_name", col_name],
    key_on="feature.properties.district_name",
    fill_color="RdYlGn_r",
    fill_opacity=0.75,
    line_opacity=0.5,
    legend_name=col_label,
    nan_fill_color="lightgrey",
).add_to(m)

# Invisible GeoJson layer for click events
def district_tooltip(row):
    return (
        f"<b>{row['district_name']}</b><br>"
        f"ESI: {row['ESI']:.3f}<br>"
        f"Air: {row['air_norm']:.3f} | Green: {row['green_norm']:.3f} | Traffic: {row['traffic_norm']:.3f}"
    )

geojson_layer = folium.GeoJson(
    esi_wgs.__geo_interface__,
    name="Districts",
    style_function=lambda f: {
        "fillOpacity": 0,
        "color": "#555",
        "weight": 1.2,
    },
    highlight_function=lambda f: {
        "fillOpacity": 0.2,
        "fillColor": "#fff",
        "color": "#222",
        "weight": 2.5,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["district_name", "ESI", "air_norm", "green_norm", "traffic_norm"],
        aliases=["District", "ESI", "Air", "Green stress", "Traffic"],
        localize=True,
    ),
)
geojson_layer.add_to(m)

# ── render map ─────────────────────────────────────────────────────────────────
map_col, info_col = st.columns([3, 1])

with map_col:
    map_data = st_folium(m, width="100%", height=520, returned_objects=["last_active_drawing", "last_object_clicked_tooltip"])

# ── district click → bar chart ─────────────────────────────────────────────────
with info_col:
    st.subheader("District detail")

    clicked_name = None
    if map_data and map_data.get("last_object_clicked_tooltip"):
        # Tooltip text starts with district name on first line
        tooltip_text = map_data["last_object_clicked_tooltip"]
        # Extract district_name from tooltip (first bold element)
        for name in esi_wgs["district_name"]:
            if name and str(name) in str(tooltip_text):
                clicked_name = name
                break

    if clicked_name:
        row = esi_gdf[esi_gdf["district_name"] == clicked_name].iloc[0]
        st.markdown(f"**{clicked_name}**")
        st.markdown(f"ESI: `{row['ESI']:.3f}`")

        fig = go.Figure(go.Bar(
            x=["Air", "Green stress", "Traffic"],
            y=[row["air_norm"], row["green_norm"], row["traffic_norm"]],
            marker_color=["#e74c3c", "#2ecc71", "#e67e22"],
            text=[f"{v:.2f}" for v in [row["air_norm"], row["green_norm"], row["traffic_norm"]]],
            textposition="auto",
        ))
        fig.update_layout(
            yaxis=dict(range=[0, 1], title="Normalized score"),
            margin=dict(l=10, r=10, t=30, b=10),
            height=280,
            title_text="Component scores",
            title_font_size=13,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Click a district on the map.")

# ── top-5 most stressed districts ─────────────────────────────────────────────
st.subheader("🔴 Top 5 Most Stressed Districts")
top5 = esi_gdf[["district_name", "ESI", "air_norm", "green_norm", "traffic_norm"]].head(5).copy()
top5.columns = ["District", "ESI", "Air", "Green stress", "Traffic"]
top5 = top5.reset_index(drop=True)
top5.index += 1
st.dataframe(
    top5.style.background_gradient(subset=["ESI"], cmap="RdYlGn_r"),
    use_container_width=True,
)

# ── raw data expander ──────────────────────────────────────────────────────────
with st.expander("📊 All district data"):
    display_cols = ["district_name", "ESI", "air_norm", "green_norm", "traffic_norm", "area_m2"]
    st.dataframe(esi_gdf[display_cols].rename(columns={
        "district_name": "District",
        "air_norm": "Air",
        "green_norm": "Green stress",
        "traffic_norm": "Traffic",
        "area_m2": "Area (m²)",
    }), use_container_width=True)
