import plotly.express as px
import streamlit as st
from utils import (
    inject_css, hero, section_title, kpi_card, load_data,
    compute_metrics, RATING_COLORS, PRIMARY, TEAL, AMBER, CORAL, VIOLET
)

st.set_page_config(page_title="District Analytics", page_icon="Analytics", layout="wide")
inject_css()

hospitals, districts = load_data()

hero(
    "District Analytics",
    "Measure healthcare accessibility at district level using distance, capacity, "
    "ICU resources, services, waiting time and rating."
)

radius_km = st.sidebar.slider(
    "Search radius from district centroid (km)", 5, 100, 25, step=5
)
metrics = compute_metrics(hospitals, districts, radius_km)

good = (metrics.accessibility == "Good").sum()
moderate = (metrics.accessibility == "Moderate").sum()
poor = (metrics.accessibility == "Poor").sum()

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Districts", len(metrics), PRIMARY)
with c2: kpi_card("Average score", f"{metrics.accessibility_score.mean():.1f}/100", TEAL)
with c3: kpi_card("Average nearest distance", f"{metrics.nearest_hospital_km.mean():.1f} km", AMBER)
with c4: kpi_card("Poor districts", poor, CORAL)

st.write("")
g1, g2, g3 = st.columns(3)
with g1: kpi_card("Good", good, TEAL)
with g2: kpi_card("Moderate", moderate, AMBER)
with g3: kpi_card("Poor", poor, CORAL)

st.divider()
section_title("District ranking")

ranked = metrics.sort_values(
    ["accessibility_score", "nearest_hospital_km"],
    ascending=[False, True]
)
display_cols = [
    "district", "population", "accessibility_score", "accessibility",
    "nearest_hospital_km", "hospitals_in_radius", "beds_in_radius",
    "icu_beds_in_radius", "beds_per_100k", "icu_per_100k",
    "service_coverage", "avg_waiting_min", "avg_rating"
]
st.dataframe(ranked[display_cols], hide_index=True, use_container_width=True)

st.download_button(
    "Download district metrics CSV",
    ranked.to_csv(index=False).encode("utf-8"),
    "district_accessibility_metrics.csv",
    "text/csv"
)

st.divider()
left, right = st.columns(2)

with left:
    section_title("Accessibility score by district")
    fig = px.bar(
        ranked.sort_values("accessibility_score"),
        x="accessibility_score", y="district", orientation="h",
        color="accessibility", color_discrete_map=RATING_COLORS,
        labels={"accessibility_score": "Score / 100"}
    )
    fig.update_layout(height=480, margin=dict(l=0,r=0,t=10,b=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)

with right:
    section_title("Beds per 100,000 population")
    fig = px.bar(
        metrics.sort_values("beds_per_100k"),
        x="beds_per_100k", y="district", orientation="h",
        color="accessibility", color_discrete_map=RATING_COLORS,
        labels={"beds_per_100k": "Beds / 100k"}
    )
    fig.update_layout(height=480, margin=dict(l=0,r=0,t=10,b=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    section_title("Population vs nearest-hospital distance")
    fig = px.scatter(
        metrics, x="population", y="nearest_hospital_km",
        size="beds_in_radius", color="accessibility",
        hover_name="district", color_discrete_map=RATING_COLORS,
        labels={"population": "Population", "nearest_hospital_km": "Nearest hospital (km)"}
    )
    fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)

with right:
    section_title("Service coverage")
    service_cols = ["emergency", "wheelchair_access", "ambulance", "pharmacy", "laboratory", "blood_bank"]
    service_rates = []
    for c in service_cols:
        service_rates.append({
            "Service": c.replace("_", " ").title(),
            "Availability (%)": hospitals[c].eq("Yes").mean() * 100
        })
    service_df = __import__("pandas").DataFrame(service_rates)
    fig = px.bar(service_df, x="Availability (%)", y="Service", orientation="h",color_discrete_sequence=[TEAL],
                 labels={"Availability (%)": "Hospitals with service (%)"})
    fig.update_layout(height=420, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)

st.divider()
section_title("Compare two districts")

names = sorted(metrics.district)
a, b = st.columns(2)
with a:
    dist_a = st.selectbox("District A", names, index=0)
with b:
    dist_b = st.selectbox("District B", names, index=min(1, len(names)-1))

row_a = metrics.loc[metrics.district == dist_a].iloc[0]
row_b = metrics.loc[metrics.district == dist_b].iloc[0]

compare = __import__("pandas").DataFrame({
    "Metric": [
        "Accessibility score", "Accessibility class", "Population",
        "Nearest hospital", "Hospitals in radius", "Beds in radius",
        "ICU beds in radius", "Beds / 100k", "ICU / 100k",
        "Service coverage", "Average waiting", "Average rating"
    ],
    dist_a: [
        row_a.accessibility_score, row_a.accessibility, f"{row_a.population:,}",
        f"{row_a.nearest_hospital_km} km", row_a.hospitals_in_radius,
        row_a.beds_in_radius, row_a.icu_beds_in_radius, row_a.beds_per_100k,
        row_a.icu_per_100k, f"{row_a.service_coverage}%",
        f"{row_a.avg_waiting_min} min", row_a.avg_rating
    ],
    dist_b: [
        row_b.accessibility_score, row_b.accessibility, f"{row_b.population:,}",
        f"{row_b.nearest_hospital_km} km", row_b.hospitals_in_radius,
        row_b.beds_in_radius, row_b.icu_beds_in_radius, row_b.beds_per_100k,
        row_b.icu_per_100k, f"{row_b.service_coverage}%",
        f"{row_b.avg_waiting_min} min", row_b.avg_rating
    ]
})
st.dataframe(compare, hide_index=True, use_container_width=True)
