# EcoLens Almaty

A Streamlit web app that visualizes an **Ecological Stress Index (ESI)** for Almaty districts, combining:

- 🌫️ **Air quality** — PM2.5 readings from OpenAQ, IDW-interpolated to district centroids
- 🌳 **Green space** — inverse park area fraction per district (OSMnx)
- 🚗 **Traffic load** — weighted road length density per district (OSMnx)

## ESI Formula

```
ESI = 0.40 × air_norm + 0.35 × green_norm + 0.25 × traffic_norm
```

Each component is min-max normalized to [0, 1] before combining.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```
ecolens/
├── app.py              # Streamlit entry point
├── data/
│   ├── fetch_openaq.py # OpenAQ PM2.5 fetcher
│   ├── fetch_osm.py    # OSMnx district/park/road fetcher + green/traffic scores
│   └── interpolate.py  # IDW spatial interpolation
├── model/
│   └── esi.py          # ESI computation and normalization
└── requirements.txt
```

## Features

- Folium choropleth map colored green → red by ESI
- Sidebar toggles to view individual air / green / traffic layers
- Click any district to see a bar chart of its three component scores
- Top 5 most stressed districts table
