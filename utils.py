from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INK = "#263238"
PRIMARY = "#3B6E8F"
TEAL = "#4F8A8B"
AMBER = "#C49A52"
CORAL = "#B96A6A"
VIOLET = "#263746"
GREEN = "#5C9270"
SLATE = "#71808C"
BORDER = "#DCE3E8"
PAGE_BG = "#F5F7F9"
RATING_COLORS = {"Good": GREEN, "Moderate": AMBER, "Poor": CORAL}
TYPE_COLORS = {"Government": PRIMARY, "Private": VIOLET}

YES_NO_COLS = [
    "emergency", "wheelchair_access", "ambulance",
    "pharmacy", "laboratory", "blood_bank"
]

@st.cache_data
def load_data():
    hospitals = pd.read_csv(DATA_DIR / "hospitals.csv")
    districts = pd.read_csv(DATA_DIR / "districts.csv")
    for c in YES_NO_COLS:
        hospitals[c] = hospitals[c].astype(str).str.strip().str.title()
    return hospitals, districts

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

def yes_score(value):
    return 100.0 if str(value).strip().lower() == "yes" else 0.0

def clamp100(x):
    return float(max(0, min(100, x)))

def hospital_score(row, distance_km):
    distance = clamp100(100 - (float(distance_km) * 4.0))
    beds = clamp100(float(row.beds) / 10.0)
    icu = clamp100(float(row.icu_beds) * 5.0)
    emergency = yes_score(row.emergency)
    wheelchair = yes_score(row.wheelchair_access)
    ambulance = yes_score(row.ambulance)
    services = np.mean([
        yes_score(row.pharmacy),
        yes_score(row.laboratory),
        yes_score(row.blood_bank),
    ])
    specialist = 100.0 if str(row.specialist_doctor).strip() else 0.0
    waiting = clamp100(100 - float(row.avg_waiting_min) * 0.8)
    rating = clamp100(float(row.rating) / 5.0 * 100)

    return round(
        0.20 * distance +
        0.10 * beds +
        0.10 * icu +
        0.15 * emergency +
        0.10 * wheelchair +
        0.10 * ambulance +
        0.10 * services +
        0.10 * specialist +
        0.03 * waiting +
        0.02 * rating, 1
    )

def score_label(score):
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Moderate"
    return "Poor"

def district_service_coverage(within):
    if len(within) == 0:
        return 0.0
    return float(np.mean([
        within[c].eq("Yes").mean() * 100 for c in YES_NO_COLS
    ]))

def compute_metrics(hospitals, districts, radius_km):
    rows = []
    for _, d in districts.iterrows():
        if len(hospitals):
            dist = haversine_km(
                d.centroid_lat, d.centroid_lon,
                hospitals.latitude, hospitals.longitude
            )
            nearest_km = float(np.min(dist))
            within = hospitals.loc[dist <= radius_km].copy()
            within["distance_km"] = dist[dist <= radius_km]
        else:
            nearest_km = np.nan
            within = hospitals.copy()

        beds = int(within.beds.sum()) if len(within) else 0
        icu = int(within.icu_beds.sum()) if len(within) else 0
        pop = float(d.population_2011)
        beds_per_100k = (beds / pop) * 100000 if pop else 0
        icu_per_100k = (icu / pop) * 100000 if pop else 0

        distance_score = 0 if np.isnan(nearest_km) else clamp100(100 - nearest_km * 4)
        capacity_score = clamp100(beds_per_100k)
        icu_score = clamp100(icu_per_100k * 10)
        service_score = district_service_coverage(within)
        wait_score = 0 if len(within) == 0 else clamp100(100 - within.avg_waiting_min.mean() * 0.8)
        rating_score = 0 if len(within) == 0 else clamp100(within.rating.mean() / 5 * 100)

        overall = round(
            0.30 * distance_score +
            0.30 * capacity_score +
            0.10 * icu_score +
            0.20 * service_score +
            0.05 * wait_score +
            0.05 * rating_score, 1
        )

        rows.append({
            "district": d.district,
            "population": int(pop),
            "centroid_lat": d.centroid_lat,
            "centroid_lon": d.centroid_lon,
            "nearest_hospital_km": round(nearest_km, 1) if not np.isnan(nearest_km) else np.nan,
            "hospitals_in_radius": len(within),
            "beds_in_radius": beds,
            "icu_beds_in_radius": icu,
            "beds_per_100k": round(beds_per_100k, 1),
            "icu_per_100k": round(icu_per_100k, 2),
            "service_coverage": round(service_score, 1),
            "avg_waiting_min": round(within.avg_waiting_min.mean(), 1) if len(within) else np.nan,
            "avg_rating": round(within.rating.mean(), 2) if len(within) else np.nan,
            "accessibility_score": overall,
        })

    metrics = pd.DataFrame(rows)
    metrics["accessibility"] = metrics.accessibility_score.map(score_label)
    return metrics

def nearest_hospitals(lat, lon, hospitals, n=5):
    out = hospitals.copy()
    if len(out) == 0:
        out["distance_km"] = []
        out["accessibility_score"] = []
        return out
    out["distance_km"] = haversine_km(
        lat, lon, out.latitude, out.longitude
    ).round(2)
    out["accessibility_score"] = [
        hospital_score(row, dist) for (_, row), dist in zip(out.iterrows(), out.distance_km)
    ]
    return out.sort_values(["accessibility_score", "distance_km"], ascending=[False, True]).head(n)

def filter_hospitals(hospitals, specialist=None, emergency=False,
                     wheelchair=False, ambulance=False, pharmacy=False,
                     laboratory=False, blood_bank=False, min_beds=0,
                     max_distance=None, lat=None, lon=None):
    out = hospitals.copy()

    if specialist and specialist != "Any specialist":
        out = out[out.specialist_doctor == specialist]
    if emergency:
        out = out[out.emergency == "Yes"]
    if wheelchair:
        out = out[out.wheelchair_access == "Yes"]
    if ambulance:
        out = out[out.ambulance == "Yes"]
    if pharmacy:
        out = out[out.pharmacy == "Yes"]
    if laboratory:
        out = out[out.laboratory == "Yes"]
    if blood_bank:
        out = out[out.blood_bank == "Yes"]
    out = out[out.beds >= min_beds]

    if lat is not None and lon is not None and len(out):
        out["distance_km"] = haversine_km(lat, lon, out.latitude, out.longitude).round(2)
        if max_distance is not None:
            out = out[out.distance_km <= max_distance]
        if len(out):
            out["accessibility_score"] = [
                hospital_score(row, dist) for (_, row), dist in zip(out.iterrows(), out.distance_km)
            ]
            out["accessibility"] = out.accessibility_score.map(score_label)
            out = out.sort_values(["accessibility_score", "distance_km"], ascending=[False, True])
    return out

def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Manrope', sans-serif; }}
    .stApp {{
        background: {PAGE_BG};
    }}
    section[data-testid="stSidebar"] {{
        background: {VIOLET};
    }}
    section[data-testid="stSidebar"] * {{ color: #F5F7F9 !important; }}
    .hero {{
        background: {PRIMARY};
        padding: 1.8rem 2.2rem; border-radius: 16px; color: white; margin-bottom: 1.4rem;
    }}
    .hero h1 {{ margin: 0; font-size: 1.9rem; font-weight: 800; }}
    .hero p {{ margin: .5rem 0 0; font-size: .92rem; opacity: .92; max-width: 850px; line-height: 1.5; }}
    .kpi-card {{
        background: #FFFFFF; border: 1px solid {BORDER}; border-top: 4px solid var(--accent);
        border-radius: 12px; padding: .9rem 1.1rem; min-height: 88px;
    }}
    .kpi-card .label {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
                         color: {SLATE}; font-weight: 700; }}
    .kpi-card .value {{ font-size: 1.55rem; font-weight: 800; color: {INK}; margin-top: .1rem; }}
    .section-title {{
        font-size: 1.08rem; font-weight: 800; color: {INK};
        border-left: 5px solid {PRIMARY}; padding-left: .6rem; margin: .3rem 0 .8rem;
    }}
    .score {{
        background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 12px;
        padding: 1rem; text-align: center;
    }}
    .score .num {{ font-size: 2rem; font-weight: 800; color: {PRIMARY}; }}
    .small-note {{ color: {SLATE}; font-size: .82rem; }}
    </style>
    """, unsafe_allow_html=True)

def kpi_card(label, value, accent):
    st.markdown(
        f'<div class="kpi-card" style="--accent:{accent}">'
        f'<div class="label">{label}</div><div class="value">{value}</div></div>',
        unsafe_allow_html=True
    )

def section_title(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)

def hero(title, subtitle):
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True
    )