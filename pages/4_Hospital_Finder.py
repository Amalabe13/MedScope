
import io
import plotly.express as px
import streamlit as st
from fpdf import FPDF
from utils import (
    inject_css, hero, section_title, load_data, filter_hospitals,
    haversine_km, hospital_score, TYPE_COLORS, PRIMARY
)

st.set_page_config(page_title="Hospital Finder", page_icon="Finder", layout="wide")
inject_css()

hospitals, districts = load_data()

hero(
    "Hospital Finder",
    "Enter patient requirements and receive a ranked list of hospitals, "
    "with an explainable accessibility score and downloadable report."
)

section_title("1. Choose the patient's reference point")
mode = st.radio(
    "Reference point",
    ["Pick a district", "Custom coordinates"],
    horizontal=True
)

if mode == "Pick a district":
    district_name = st.selectbox("District", sorted(districts.district))
    drow = districts.loc[districts.district == district_name].iloc[0]
    lat, lon = float(drow.centroid_lat), float(drow.centroid_lon)
    st.caption(f"Using the centroid of {district_name}: {lat:.4f}, {lon:.4f}")
else:
    c1, c2 = st.columns(2)
    lat = c1.number_input("Latitude", value=10.0000, format="%.4f")
    lon = c2.number_input("Longitude", value=76.3000, format="%.4f")

st.divider()
section_title("2. Patient requirements")

specialists = ["Any specialist"] + sorted(hospitals.specialist_doctor.dropna().unique().tolist())
c1, c2 = st.columns(2)
with c1:
    specialist = st.selectbox("Required specialist", specialists)
    min_beds = st.number_input("Minimum available beds", min_value=0, max_value=int(hospitals.beds.max()), value=0, step=50)
    max_distance = st.slider("Maximum distance (km)", 1, 100, 25)
with c2:
    st.markdown("**Required facilities**")
    emergency = st.checkbox("Emergency service")
    wheelchair = st.checkbox("Wheelchair access")
    ambulance = st.checkbox("Ambulance")
    pharmacy = st.checkbox("Pharmacy")
    laboratory = st.checkbox("Laboratory")
    blood_bank = st.checkbox("Blood bank")

results = filter_hospitals(
    hospitals,
    specialist=specialist,
    emergency=emergency,
    wheelchair=wheelchair,
    ambulance=ambulance,
    pharmacy=pharmacy,
    laboratory=laboratory,
    blood_bank=blood_bank,
    min_beds=min_beds,
    max_distance=max_distance,
    lat=lat,
    lon=lon
)

st.divider()
section_title("3. Recommended hospitals")

if len(results) == 0:
    st.warning(
        "No hospital satisfies every selected requirement within the chosen distance. "
        "Try increasing the distance or removing one requirement."
    )
else:
    st.success(f"{len(results)} hospital(s) match the selected requirements.")

    top = results.head(5).copy()
    st.dataframe(
        top[[
            "name", "district", "type", "distance_km", "accessibility_score",
            "accessibility", "beds", "icu_beds", "specialist_doctor",
            "emergency", "wheelchair_access", "ambulance",
            "avg_waiting_min", "rating"
        ]],
        hide_index=True, use_container_width=True
    )

    left, right = st.columns([1, 1])
    with left:
        section_title("Top recommendation details")
        row = top.iloc[0]
        st.markdown(f"### {row['name']}")
        st.write(f"**District:** {row['district']}")
        st.write(f"**Distance:** {row['distance_km']:.2f} km")
        st.write(f"**Accessibility score:** {row['accessibility_score']}/100 ({row['accessibility']})")

        components = {
            "Emergency": "Yes" if row.emergency == "Yes" else "No",
            "Wheelchair": "Yes" if row.wheelchair_access == "Yes" else "No",
            "Ambulance": "Yes" if row.ambulance == "Yes" else "No",
            "Pharmacy": "Yes" if row.pharmacy == "Yes" else "No",
            "Laboratory": "Yes" if row.laboratory == "Yes" else "No",
            "Blood bank": "Yes" if row.blood_bank == "Yes" else "No",
            "Specialist": row.specialist_doctor,
            "Beds / ICU": f"{int(row.beds)} / {int(row.icu_beds)}",
            "Waiting": f"{int(row.avg_waiting_min)} min",
            "Opening": row.opening_hours,
            "Rating": f"{row.rating}/5",
        }
        st.table(__import__("pandas").DataFrame(list(components.items()), columns=["Feature", "Value"]))

    with right:
        fig = px.scatter_map(
            top, lat="latitude", lon="longitude", size="beds",
            color="type", hover_name="name",
            hover_data={"distance_km": True, "accessibility_score": True,
                        "latitude": False, "longitude": False},
            zoom=7, height=430, color_discrete_map=TYPE_COLORS
        )
        fig.add_scattermap(
            lat=[lat], lon=[lon],
            marker=dict(size=18, color=PRIMARY),
            name="Patient reference point"
        )
        fig.update_layout(map_style="open-street-map", margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        "Download matching hospitals CSV",
        results.to_csv(index=False).encode("utf-8"),
        "hospital_recommendations.csv",
        "text/csv"
    )

st.divider()
section_title("4. Download a summary PDF")

if st.button("Generate PDF report"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 10, "Hospital Accessibility Management Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Reference point: {lat:.4f}, {lon:.4f}", ln=True)
    pdf.cell(0, 7, f"Maximum distance: {max_distance} km | Required specialist: {specialist}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    headers = ["Hospital", "District", "Dist km", "Score", "Beds", "ICU"]
    widths = [58, 31, 20, 20, 18, 18]
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for _, r in results.head(12).iterrows():
        values = [
            str(r["name"])[:31], str(r["district"])[:17],
            f"{r['distance_km']:.1f}", f"{r['accessibility_score']:.1f}",
            str(int(r["beds"])), str(int(r["icu_beds"]))
        ]
        for v, w in zip(values, widths):
            pdf.cell(w, 7, v, border=1)
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0, 5,
        "Demonstration dataset. The added hospital service and operational fields are "
        "illustrative and should be replaced by verified data for real-world decisions. "
        "Distances are straight-line Haversine distances, not road travel times."
    )

    output = pdf.output()
    pdf_bytes = bytes(output) if not isinstance(output, bytes) else output
    st.download_button(
        "Download PDF",
        pdf_bytes,
        "hospital_accessibility_report.pdf",
        "application/pdf"
    )
