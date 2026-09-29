import numpy as np
import pandas as pd
import streamlit as st

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

DISTRICTS = [
    "Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam",
    "Idukki", "Ernakulam", "Thrissur", "Palakkad", "Malappuram",
    "Kozhikode", "Wayanad", "Kannur", "Kasaragod",
]
SPECIALISTS = [
    "Cardiologist", "Dermatologist", "ENT Specialist", "General Physician",
    "Gynecologist", "Neurologist", "Orthopedist", "Pediatrician",
    "Pulmonologist", "Surgeon",
]
OPENING_HOURS = ["24 Hours", "7 AM - 10 PM", "8 AM - 8 PM", "9 AM - 9 PM"]
YES_NO = ["Yes", "No"]
HOSPITAL_TYPES = ["Government", "Private"]

REFERENCE_PLACES = {
    "Thiruvananthapuram": (8.5241, 76.9366),
    "Kollam": (8.8932, 76.5924),
    "Pathanamthitta": (9.2646, 76.7871),
    "Alappuzha": (9.4981, 76.3388),
    "Kottayam": (9.5916, 76.5222),
    "Idukki": (9.8437, 76.9744),
    "Ernakulam": (9.9816, 76.2999),
    "Thrissur": (10.5276, 76.2144),
    "Palakkad": (10.7867, 76.6548),
    "Malappuram": (11.0510, 76.0711),
    "Kozhikode": (11.2588, 75.7804),
    "Wayanad": (11.6854, 76.1320),
    "Kannur": (11.8745, 75.3704),
    "Kasaragod": (12.5024, 75.0103),
    "Chinnakkada, Kollam": (8.88756, 76.58957),
    "Kollam Junction": (8.88531, 76.59454),
    "Kottarakkara": (9.0055, 76.7832),
    "Punalur": (9.0175, 76.9265),
}


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def clamp100(value):
    return float(max(0, min(100, value)))


def yes_score(value):
    return 100.0 if str(value).strip().lower() == "yes" else 0.0


def score_label(score):
    if pd.isna(score):
        return "Unscored"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Moderate"
    return "Poor"


def safe_number(value, default=0.0):
    return default if pd.isna(value) else float(value)


def choice_index(options, value):
    return options.index(value) if value in options else 0


def flash(kind, message):
    st.session_state["flash"] = (kind, message)


def show_flash():
    item = st.session_state.pop("flash", None)
    if item:
        getattr(st, item[0])(item[1])


def load_manager(manager):
    ok, message = manager.load()
    if not ok:
        st.error(message)
        if manager.problem in ("missing", "empty"):
            if st.button("Create a fresh file with the correct headers"):
                done, info = manager.create_empty()
                if done:
                    st.rerun()
                st.error(info)
        st.stop()
    for warning in manager.warnings:
        st.warning(warning)


def missing_notice(manager, raw, strategy):
    total = manager.count_missing(raw)
    st.caption(
        f"Missing values: {total} empty cell(s) in the current view. "
        f"Statistics and charts use this rule: {strategy.lower()}."
    )


def style_chart(fig, height=380):
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=INK),
    )
    return fig


def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Manrope', sans-serif; }}
    .stApp {{ background: {PAGE_BG}; }}
    section[data-testid="stSidebar"] {{ background: {VIOLET}; }}
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label p,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color: #F5F7F9 !important; }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"],
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{ color: #F5F7F9 !important; }}
    .hero {{
        background: {PRIMARY};
        padding: 1.8rem 2.2rem; border-radius: 16px; color: white; margin-bottom: 1.4rem;
    }}
    .hero h1 {{ margin: 0; font-size: 1.9rem; font-weight: 800; color: white; }}
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
    </style>
    """, unsafe_allow_html=True)


def kpi_card(label, value, accent):
    st.markdown(
        f'<div class="kpi-card" style="--accent:{accent}">'
        f'<div class="label">{label}</div><div class="value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def section_title(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)
