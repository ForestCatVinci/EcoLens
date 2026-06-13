---
title: EcoLens Almaty
emoji: 🌿
colorFrom: green
colorTo: red
sdk: streamlit
sdk_version: "1.35.0"
app_file: ecolens/app.py
pinned: false
---

# EcoLens Almaty

A Streamlit web app that visualizes an **Ecological Stress Index (ESI)** for Almaty districts, combining:

- 🌫️ **Air quality** — PM2.5 readings from OpenAQ, IDW-interpolated to district centroids
- 🌳 **Green space** — inverse park area fraction per district (OSMnx)
- 🚗 **Traffic load** — weighted road length density per district (OSMnx)

## ESI Formula

```
ESI = 0.40 × air_norm + 0.35 × green_norm + 0.25 × traffic_norm
```

## Setup

```bash
pip install -r requirements.txt
streamlit run ecolens/app.py
```
