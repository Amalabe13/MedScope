import pandas as pd
import streamlit as st
from utils import inject_css, hero, section_title, kpi_card, PRIMARY, TEAL, AMBER, VIOLET

st.set_page_config(page_title="MedScope", page_icon="🏥", layout="wide")
inject_css()

hero(
    "Hospital Accessibility Management",
    "A analytics system that combines hospital capacity, services, location "
    "and district population to identify healthcare accessibility gaps across Kerala.",
)

section_title("Objective")
st.markdown("""
The presence of hospitals does not automatically mean that healthcare is accessible.
People also need reasonable distance, available beds, emergency services, physical accessibility,
transport, diagnostics and specialist care. *- MedScope combines those factors into transparent accessibility scores. Each team
member owns one dataset and one page where records can be added, viewed, edited, deleted, charted
and exported as reports.*
""")

st.write("")
section_title("Module division")

modules = [
    ("Amala B", "Analyzer", "pages/1_Analyzer.py", "hospital_readiness.csv",
     "Scores each hospital on distance, ICU beds, emergency, wheelchair access, ambulance, waiting time and rating with adjustable weights.", PRIMARY),
    ("Megha S", "Map Explorer", "pages/2_Map_Explorer.py", "hospital_locations.csv",
     "Shows hospital locations, type and bed capacity on an interactive map with filters and district summaries.", TEAL),
    ("Aiswarya S", "District Analytics", "pages/3_District_Analytics.py", "district_profiles.csv",
     "Ranks districts by accessibility using population, nearby beds, services, waiting time and ratings.", AMBER),
    ("Theertha A", "Hospital Finder", "pages/4_Hospital_Finder.py", "hospital_directory.csv",
     "Finds and ranks hospitals near a patient by specialist, facilities, opening hours and distance.", VIOLET),
]

for column, (owner, title, path, csv_name, description, accent) in zip(st.columns(4), modules):
    with column:
        st.markdown(
            f'<div class="kpi-card" style="--accent:{accent};min-height:210px">'
            f'<div class="label">{owner} — {title}</div>'
            f'<div style="margin-top:.4rem;font-size:.78rem;color:#71808C">data/{csv_name}</div>'
            f'<div style="margin-top:.5rem;color:#334155;font-size:.85rem;line-height:1.5">{description}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.page_link(path, label=f"Open {title}")

st.divider()
section_title("Who owns what")
ownership = pd.DataFrame(
    [{"Student": owner, "Page": path, "CSV file": f"data/{csv_name}"} for owner, _, path, csv_name, _, _ in modules]
)
st.dataframe(ownership, hide_index=True, width="stretch")

st.divider()
section_title("Fields in each dataset")
fields = {
    "hospital_readiness.csv": "hospital_id, name, district, latitude, longitude, icu_beds, emergency, wheelchair_access, ambulance, avg_waiting_min, rating",
    "hospital_locations.csv": "hospital_id, name, district, type, latitude, longitude, beds",
    "district_profiles.csv": "district_id, district, population_2011, centroid_lat, centroid_lon, hospitals_nearby, beds_nearby, icu_beds_nearby, nearest_hospital_km, service_coverage, avg_waiting_min, avg_rating",
    "hospital_directory.csv": "hospital_id, name, district, latitude, longitude, specialist_doctor, pharmacy, laboratory, blood_bank, opening_hours",
}
st.dataframe(
    pd.DataFrame({"CSV file": list(fields), "Columns": list(fields.values())}),
    hide_index=True, width="stretch",
)
st.info(
    "Note: hospital names, locations and bed counts come from the original project. The service "
    "and operational fields are illustrative and must be replaced with verified records before real use."
)

st.divider()
section_title("How the scores work")
left, right = st.columns(2)
with left:
    st.markdown("""
**Hospital readiness score (Analyzer, default weights)**
- Distance: 25%
- ICU capacity: 15%
- Emergency service: 20%
- Wheelchair access: 15%
- Ambulance: 15%
- Waiting time: 5%
- Rating: 5%

**Hospital match score (Finder)**
- Distance: 60%
- Pharmacy + laboratory + blood bank: 30%
- Opening hours: 10%
""")
with right:
    st.markdown("""
**District score (District Analytics)**
- Nearest-hospital distance: 30%
- Beds per 100,000 population: 30%
- ICU beds per 100,000: 10%
- Service coverage: 20%
- Waiting time: 5%
- Average rating: 5%

**Good:** 75–100 | **Moderate:** 50–74.9 | **Poor:** below 50
""")
