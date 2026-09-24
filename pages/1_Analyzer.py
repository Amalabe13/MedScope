import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    inject_css, hero, section_title, load_data, haversine_km,
    clamp100, score_label, RATING_COLORS
)

st.set_page_config(
    page_title="Accessibility Analyzer",
    page_icon="Analyzer",
    layout="wide"
)

inject_css()

hospitals, districts = load_data()

hero(
    "Accessibility Analyzer",
    "Understand exactly how hospital accessibility is calculated. "
    "Adjust the importance of each factor, compare hospitals, and generate an explainable score."
)

section_title("1. Select a hospital and reference location")

c1, c2 = st.columns(2)

with c1:
    hospital_name = st.selectbox(
        "Hospital",
        hospitals["name"].tolist()
    )
    hospital = hospitals.loc[
        hospitals["name"] == hospital_name
    ].iloc[0]

with c2:
    reference_places = {
        "Chinnakkada, Kollam": (8.88756, 76.58957),
        "Kollam City Centre": (8.89321, 76.61414),
        "Kollam Junction": (8.88531, 76.59454),
        "Kottarakkara": (9.00550, 76.78320),
        "Kundara": (8.96060, 76.68024),
        "Karunagappally": (9.05515, 76.53542),
        "Punalur": (9.01750, 76.92650),
    }

    reference_location = st.selectbox(
        "Reference location",
        list(reference_places.keys())
    )

    ref_lat, ref_lon = reference_places[reference_location]

distance = float(
    haversine_km(
        ref_lat,
        ref_lon,
        float(hospital["latitude"]),
        float(hospital["longitude"])
    )
)

st.info(
    f"Calculated straight-line distance: **{distance:.2f} km**"
)

st.divider()

section_title("2. Configure accessibility weights")

st.caption(
    "The weights below are a transparent project model. "
    "They are not a medical or government standard. "
    "The total is automatically normalized."
)

cols = st.columns(5)

with cols[0]:
    w_distance = st.slider("Distance", 0, 30, 20)

with cols[1]:
    w_beds = st.slider("Bed capacity", 0, 20, 10)

with cols[2]:
    w_icu = st.slider("ICU capacity", 0, 20, 10)

with cols[3]:
    w_emergency = st.slider("Emergency service", 0, 25, 15)

with cols[4]:
    w_wheelchair = st.slider("Wheelchair access", 0, 20, 10)

cols = st.columns(5)

with cols[0]:
    w_ambulance = st.slider("Ambulance", 0, 20, 10)

with cols[1]:
    w_services = st.slider(
        "Pharmacy + Laboratory + Blood Bank",
        0,
        20,
        10
    )

with cols[2]:
    w_specialist = st.slider(
        "Specialist availability",
        0,
        20,
        10
    )

with cols[3]:
    w_waiting = st.slider(
        "Waiting time",
        0,
        10,
        3
    )

with cols[4]:
    w_rating = st.slider(
        "Rating",
        0,
        10,
        2
    )

weights = {
    "Distance": w_distance,
    "Beds": w_beds,
    "ICU": w_icu,
    "Emergency": w_emergency,
    "Wheelchair": w_wheelchair,
    "Ambulance": w_ambulance,
    "Other services": w_services,
    "Specialist": w_specialist,
    "Waiting time": w_waiting,
    "Rating": w_rating
}

total_weight = sum(weights.values())

if total_weight == 0:
    st.error(
        "At least one weight must be greater than zero."
    )
    st.stop()

components = {
    "Distance": clamp100(100 - distance * 4),

    "Beds": clamp100(
        float(hospital["beds"]) / 10
    ),

    "ICU": clamp100(
        float(hospital["icu_beds"]) * 5
    ),

    "Emergency": (
        100
        if hospital["emergency"] == "Yes"
        else 0
    ),

    "Wheelchair": (
        100
        if hospital["wheelchair_access"] == "Yes"
        else 0
    ),

    "Ambulance": (
        100
        if hospital["ambulance"] == "Yes"
        else 0
    ),

    "Other services": (
        sum(
            hospital[c] == "Yes"
            for c in [
                "pharmacy",
                "laboratory",
                "blood_bank"
            ]
        ) / 3 * 100
    ),

    "Specialist": (
        100
        if str(hospital["specialist_doctor"]).strip()
        else 0
    ),

    "Waiting time": clamp100(
        100 -
        float(hospital["avg_waiting_min"]) * 0.8
    ),

    "Rating": clamp100(
        float(hospital["rating"]) / 5 * 100
    )
}

weighted_contributions = {
    name: components[name] * weights[name] / total_weight
    for name in weights
}

overall = round(
    sum(weighted_contributions.values()),
    1
)

classification = score_label(overall)

st.divider()

section_title("3. Explainable accessibility score")

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.metric(
        "Overall score",
        f"{overall}/100"
    )

with k2:
    st.metric(
        "Classification",
        classification
    )

with k3:
    st.metric(
        "Distance",
        f"{distance:.2f} km"
    )

with k4:
    st.metric(
        "Hospital rating",
        f"{hospital['rating']}/5"
    )

with k5:
    st.metric(
        "Beds",
        f"{int(hospital['beds'])}"
    )

left, right = st.columns(2)

with left:
    section_title("Score breakdown")

    breakdown = pd.DataFrame({
        "Factor": list(components.keys()),
        "Raw score": [
            round(components[k], 1)
            for k in components
        ],
        "Weight": [
            weights[k]
            for k in components
        ],
        "Contribution": [
            round(weighted_contributions[k], 2)
            for k in components
        ]
    })

    st.dataframe(
        breakdown,
        hide_index=True,
        use_container_width=True,
        height=450
    )

with right:
    section_title("Contribution to final score")

    chart_df = breakdown.sort_values(
        "Contribution"
    )

    fig = px.bar(
        chart_df,
        x="Contribution",
        y="Factor",
        orientation="h",
        labels={
            "Contribution": "Weighted contribution"
        }
    )

    fig.update_traces(
        marker_color="#3B6E8F",
        width=0.35
    )

    fig.update_layout(
        height=450,
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
        bargap=0.15
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

st.divider()

section_title(
    "4. Compare hospitals using the same weighting"
)

comparison_names = st.multiselect(
    "Select hospitals to compare",
    hospitals["name"].tolist(),
    default=hospitals["name"].tolist()[:3],
    max_selections=5
)

comparison_rows = []

for name in comparison_names:

    row = hospitals.loc[
        hospitals["name"] == name
    ].iloc[0]

    d = float(
        haversine_km(
            ref_lat,
            ref_lon,
            float(row["latitude"]),
            float(row["longitude"])
        )
    )

    scores = {
        "Distance": clamp100(100 - d * 4),

        "Beds": clamp100(
            float(row["beds"]) / 10
        ),

        "ICU": clamp100(
            float(row["icu_beds"]) * 5
        ),

        "Emergency": (
            100
            if row["emergency"] == "Yes"
            else 0
        ),

        "Wheelchair": (
            100
            if row["wheelchair_access"] == "Yes"
            else 0
        ),

        "Ambulance": (
            100
            if row["ambulance"] == "Yes"
            else 0
        ),

        "Other services": (
            sum(
                row[c] == "Yes"
                for c in [
                    "pharmacy",
                    "laboratory",
                    "blood_bank"
                ]
            ) / 3 * 100
        ),

        "Specialist": (
            100
            if str(
                row["specialist_doctor"]
            ).strip()
            else 0
        ),

        "Waiting time": clamp100(
            100 -
            float(row["avg_waiting_min"]) * 0.8
        ),

        "Rating": clamp100(
            float(row["rating"]) / 5 * 100
        )
    }

    score = sum(
        scores[k] * weights[k]
        for k in weights
    ) / total_weight

    comparison_rows.append({
        "Hospital": name,
        "District": row["district"],
        "Distance (km)": round(d, 2),
        "Accessibility score": round(
            score,
            1
        ),
        "Class": score_label(score),
        "Beds": int(row["beds"]),
        "ICU": int(row["icu_beds"])
    })

comparison_df = pd.DataFrame(
    comparison_rows
)

if len(comparison_df):

    comparison_df = comparison_df.sort_values(
        [
            "Accessibility score",
            "Distance (km)"
        ],
        ascending=[
            False,
            True
        ]
    )

    st.dataframe(
        comparison_df,
        hide_index=True,
        use_container_width=True
    )

    fig = px.bar(
        comparison_df.sort_values(
            "Accessibility score"
        ),
        x="Accessibility score",
        y="Hospital",
        orientation="h",
        color="Class",
        color_discrete_map={
            "Good": "#5C9270",
            "Moderate": "#C49A52",
            "Poor": "#B96A6A"
        },
        labels={
            "Accessibility score": "Score / 100"
        }
    )

    # Thin bars + reduced gap
    fig.update_traces(
        width=0.25
    )

    fig.update_layout(
        height=300,
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
        bargap=0.02
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

st.divider()

section_title("5. Sensitivity analysis")

st.markdown(
    """
Change one or more weights above and observe how the accessibility score changes.
This demonstrates that the system is **explainable** rather than a black-box
recommendation.

For example:

- Increase **Emergency** and **Ambulance** for an emergency-focused scenario.
- Increase **Wheelchair** for a mobility-accessibility scenario.
- Increase **Distance** for a location-focused scenario.
- Increase **Beds** and **ICU** for a capacity-focused scenario.
"""
)

report = pd.DataFrame({
    "Factor": list(components.keys()),
    "Raw Score": [
        round(components[k], 2)
        for k in components
    ],
    "Weight": [
        weights[k]
        for k in components
    ],
    "Contribution": [
        round(weighted_contributions[k], 2)
        for k in components
    ]
})

st.download_button(
    "Download score analysis CSV",
    report.to_csv(
        index=False
    ).encode("utf-8"),
    "accessibility_score_analysis.csv",
    "text/csv"
)

st.info(
    "Important: this prototype is an accessibility information system. "
    "It does not diagnose, triage, or replace medical advice. "
    "The service fields in the demonstration dataset should be replaced "
    "with verified data."
)