
import plotly.express as px
import streamlit as st
from utils import (
    inject_css, hero, section_title, load_data, compute_metrics,
    hospital_score, RATING_COLORS, TYPE_COLORS
)

st.set_page_config(page_title="Map Explorer", page_icon="Map", layout="wide")
inject_css()

hospitals_all, districts = load_data()

hero(
    "Map Explorer",
    "Explore hospital locations, capacity and district accessibility. "
    "Use the sidebar to focus the map on a particular type, district or facility."
)

st.sidebar.header("Map filters")
selected_types = st.sidebar.multiselect(
    "Hospital type",
    sorted(hospitals_all.type.unique()),
    default=sorted(hospitals_all.type.unique())
)
selected_districts = st.sidebar.multiselect(
    "District",
    sorted(hospitals_all.district.unique()),
    default=[]
)
min_beds = st.sidebar.slider(
    "Minimum beds", 0, int(hospitals_all.beds.max()), 0, step=50
)
radius_km = st.sidebar.slider(
    "District analysis radius (km)", 5, 100, 25, step=5
)

hospitals = hospitals_all[
    hospitals_all.type.isin(selected_types) &
    (hospitals_all.beds >= min_beds)
].copy()
if selected_districts:
    hospitals = hospitals[hospitals.district.isin(selected_districts)]

metrics = compute_metrics(hospitals, districts, radius_km)

district_lookup = districts.set_index("district")[["centroid_lat", "centroid_lon"]]
if len(hospitals):
    hospitals["district_lat"] = hospitals.district.map(district_lookup.centroid_lat)
    hospitals["district_lon"] = hospitals.district.map(district_lookup.centroid_lon)
    hospitals["centroid_distance_km"] = (
        (hospitals.latitude - hospitals.district_lat).abs() * 111
    )
    from utils import haversine_km
    hospitals["centroid_distance_km"] = haversine_km(
        hospitals.district_lat, hospitals.district_lon,
        hospitals.latitude, hospitals.longitude
    )
    hospitals["hospital_score"] = [
        hospital_score(row, d) for (_, row), d in zip(hospitals.iterrows(), hospitals.centroid_distance_km)
    ]

section_title(f"{len(hospitals)} hospitals shown")
st.caption("Hospital marker size represents beds. District markers represent the district centroid and its calculated accessibility class.")

if len(hospitals):
    fig = px.scatter_map(
        hospitals, lat="latitude", lon="longitude",
        size="beds", color="type",
        hover_name="name",
        hover_data={
            "district": True, "beds": True, "icu_beds": True,
            "specialist_doctor": True, "hospital_score": True,
            "latitude": False, "longitude": False
        },
        zoom=6.2, height=600, color_discrete_map=TYPE_COLORS
    )
else:
    fig = px.scatter_map(height=600)

centroids = px.scatter_map(
    metrics, lat="centroid_lat", lon="centroid_lon",
    color="accessibility", size="accessibility_score",
    hover_name="district",
    hover_data={
        "accessibility_score": True, "nearest_hospital_km": True,
        "beds_per_100k": True, "hospitals_in_radius": True,
        "centroid_lat": False, "centroid_lon": False
    },
    color_discrete_map=RATING_COLORS
)
for trace in centroids.data:
    trace.marker.size = 18
    fig.add_trace(trace)

fig.update_layout(map_style="open-street-map", margin=dict(l=0,r=0,t=0,b=0))
st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    section_title("District accessibility snapshot")
    st.dataframe(
        metrics[[
            "district", "accessibility_score", "accessibility",
            "nearest_hospital_km", "hospitals_in_radius", "beds_per_100k"
        ]].sort_values("accessibility_score", ascending=False),
        hide_index=True, use_container_width=True
    )
with right:
    section_title("Visible hospital facilities")
    st.dataframe(
        hospitals[[
            "name", "district", "type", "beds", "icu_beds",
            "emergency", "wheelchair_access", "ambulance",
            "specialist_doctor", "hospital_score"
        ]].sort_values("hospital_score", ascending=False),
        hide_index=True, use_container_width=True
    )

st.info(
    "Map distance uses the Haversine formula (straight-line distance). "
    "It is a geographic accessibility proxy, not a real road travel time."
)
