import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    inject_css,
    hero,
    kpi_card,
    section_title,
    load_data,
    PRIMARY,
    TEAL,
    AMBER
)

st.set_page_config(
    page_title="About",
    page_icon="Hospital",
    layout="wide"
)

inject_css()

hospitals, districts = load_data()

hero(
    "Hospital Accessibility Management",
    "A four-person Streamlit analytics system that combines hospital capacity, "
    "services, location and district population to identify healthcare accessibility gaps."
)

section_title("Project objective")

st.markdown("""
**Problem:** The presence of hospitals does not automatically mean that healthcare
is accessible. People also need reasonable distance, available beds, emergency
services, physical accessibility, transport, diagnostics and specialist care.

**Solution:** This dashboard combines those factors into a transparent accessibility
score, then provides a map, district analytics, patient-oriented hospital finder,
and downloadable reports.
""")

c1, c2, c3, c4 = st.columns(4)

with c1:
    kpi_card(
        "Hospitals",
        len(hospitals),
        PRIMARY
    )

with c2:
    kpi_card(
        "Total beds",
        f"{int(hospitals.beds.sum()):,}",
        TEAL
    )

with c3:
    kpi_card(
        "Districts",
        districts.district.nunique(),
        AMBER
    )

with c4:
    kpi_card(
        "ICU beds",
        f"{int(hospitals.icu_beds.sum()):,}",
        "#263746"
    )


st.write("")

section_title("Module Division")

cols = st.columns(4)

modules = [
    (
        "Amala B — Analyzer",
        "Calculates transparent hospital accessibility scores using distance, "
        "capacity, services and other accessibility factors.",
        PRIMARY
    ),
    (
        "Megha S — Map Explorer",
        "Visualizes hospital locations and district coverage with interactive "
        "map-based exploration and filters.",
        TEAL
    ),
    (
        "Aiswarya S — District Analytics",
        "Analyzes district-level healthcare accessibility using population, "
        "hospital capacity, services and performance indicators.",
        AMBER
    ),
    (
        "Theertha A — Hospital Finder",
        "Helps users explore hospitals based on their requirements and provides "
        "score breakdowns and useful comparisons.",
        "#263746"
    ),
]

for col, (title, desc, accent) in zip(cols, modules):
    with col:
        st.markdown(
            f'<div class="kpi-card" style="--accent:{accent};min-height:150px">'
            f'<div class="label">{title}</div>'
            f'<div style="margin-top:.5rem;color:#334155;font-size:.85rem;line-height:1.5">'
            f'{desc}'
            f'</div>'
            '</div>',
            unsafe_allow_html=True
        )


st.write("")

left, right = st.columns(2)


with left:
    section_title("Hospitals by district")

    counts = (
        hospitals
        .groupby("district")
        .size()
        .reset_index(name="hospitals")
        .sort_values("hospitals")
    )

    fig = px.bar(
        counts,
        x="hospitals",
        y="district",
        orientation="h",
        labels={
            "hospitals": "Hospitals",
            "district": "District"
        }
    )

    fig.update_traces(
        marker_color="#3B6E8F",
        width=0.45
    )

    fig.update_layout(
        height=430,
        margin=dict(
            l=0,
            r=0,
            t=10,
            b=0
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(
            color="#263238"
        ),
        bargap=0.08
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


with right:
    section_title("Government vs Private")

    fig = px.pie(
        hospitals,
        names="type",
        hole=0.55,
        color="type",
        color_discrete_map={
            "Government": "#263746",
            "Private": "#4F8A8B"
        }
    )

    fig.update_traces(
        domain=dict(
            x=[0.20, 0.80],
            y=[0.12, 0.88]
        ),
        textfont=dict(
            size=14
        )
    )

    fig.update_layout(
        height=430,
        margin=dict(
            l=0,
            r=0,
            t=10,
            b=0
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(
            color="#263238"
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


st.divider()

section_title("Dataset fields used by the system")

field_purposes = {
    "name": "Hospital identity",
    "district": "District / area",
    "type": "Government or private",
    "latitude": "Map and distance",
    "longitude": "Map and distance",
    "beds": "Bed capacity",
    "icu_beds": "ICU capacity",
    "emergency": "Emergency service",
    "wheelchair_access": "Wheelchair accessibility",
    "ambulance": "Ambulance availability",
    "pharmacy": "Pharmacy availability",
    "laboratory": "Laboratory availability",
    "blood_bank": "Blood bank availability",
    "specialist_doctor": "Specialist available",
    "avg_waiting_min": "Average waiting time",
    "opening_hours": "Operating hours",
    "rating": "User-facing rating",
}

field_rows = []

for field in hospitals.columns:
    example = (
        hospitals[field].iloc[0]
        if len(hospitals)
        else ""
    )

    field_rows.append({
        "Field": field,
        "Example": example,
        "Purpose": field_purposes.get(
            field,
            "Hospital dataset field"
        )
    })

field_df = pd.DataFrame(field_rows)

st.dataframe(
    field_df,
    hide_index=True,
    use_container_width=True
)


st.info(
    "Dataset note: the original hospital names, locations and bed counts are retained. "
    "The added service/operational fields in this demonstration dataset are illustrative "
    "project data and must be replaced with verified hospital records before real-world use."
)


st.divider()

section_title("How the score works")

st.markdown("""
### Hospital score (out of 100)

- Distance: **20%**
- Bed capacity: **10%**
- ICU capacity: **10%**
- Emergency service: **15%**
- Wheelchair access: **10%**
- Ambulance: **10%**
- Pharmacy + laboratory + blood bank: **10%**
- Specialist availability: **10%**
- Waiting time: **3%**
- Rating: **2%**

### District score (out of 100)

- Nearest-hospital distance: **30%**
- Beds per 100,000 population: **30%**
- ICU beds per 100,000: **10%**
- Service coverage: **20%**
- Waiting time: **5%**
- Average rating: **5%**

**Good:** 75–100 | **Moderate:** 50–74.9 | **Poor:** below 50
""")