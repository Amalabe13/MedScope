from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from csv_manager import CSVManager, EXCLUDE_ROWS, FILL_MEDIAN
from utils import (
    inject_css, hero, section_title, kpi_card, flash, show_flash, load_manager,
    missing_notice, style_chart, haversine_km, clamp100, yes_score, score_label,
    safe_number, choice_index, DISTRICTS, SPECIALISTS, OPENING_HOURS, YES_NO,
    REFERENCE_PLACES, PRIMARY, TEAL, AMBER, VIOLET, GREEN,
)

st.set_page_config(page_title="Hospital Finder", page_icon="🔎", layout="wide")
inject_css()

FACILITIES = {"Pharmacy": "pharmacy", "Laboratory": "laboratory", "Blood bank": "blood_bank"}


class DirectoryManager(CSVManager):
    def __init__(self):
        super().__init__(
            file_name="hospital_directory.csv",
            columns=[
                "hospital_id", "name", "district", "latitude", "longitude",
                "specialist_doctor", "pharmacy", "laboratory", "blood_bank", "opening_hours",
            ],
            id_column="hospital_id",
            id_prefix="H",
            numeric_columns=["latitude", "longitude"],
            yes_no_columns=["pharmacy", "laboratory", "blood_bank"],
        )

    def validate(self, record):
        errors = self.check_required(record, ["hospital_id", "name", "district", "specialist_doctor", "opening_hours"])
        errors += self.check_choice(record, "district", DISTRICTS)
        errors += self.check_choice(record, "specialist_doctor", SPECIALISTS)
        errors += self.check_choice(record, "opening_hours", OPENING_HOURS)
        errors += self.check_number(record, "latitude", 8.0, 13.0)
        errors += self.check_number(record, "longitude", 74.5, 77.5)
        for field in self.yes_no_columns:
            errors += self.check_choice(record, field, YES_NO)
        return errors

    def create(self, record):
        record = self.tidy(record)
        errors = self.validate(record)
        if errors:
            return False, " ".join(errors)
        if self.id_exists(record["hospital_id"]):
            return False, f"A hospital with ID {record['hospital_id']} already exists."
        if self.name_taken(record["name"], record["district"]):
            return False, f"{record['name']} is already in the directory for {record['district']}."
        new_row = pd.DataFrame([record], columns=self.columns)
        combined = new_row if self._data.empty else pd.concat([self._data, new_row], ignore_index=True)
        ok, message = self.save(combined)
        return ok, f"Added {record['name']} as {record['hospital_id']}." if ok else message

    def search(self, text="", districts=None, specialist="Any specialist", facilities=(), open_24h=False):
        result = self._data.copy()
        if text:
            result = result[result["name"].str.contains(text, case=False, na=False, regex=False)]
        if districts:
            result = result[result["district"].isin(districts)]
        if specialist != "Any specialist":
            result = result[result["specialist_doctor"] == specialist]
        for column in facilities:
            result = result[result[column] == "Yes"]
        if open_24h:
            result = result[result["opening_hours"] == "24 Hours"]
        return result

    def update(self, record_id, changes):
        position = self.find_position(record_id)
        if position is None:
            return False, f"No hospital found with ID {record_id}."
        merged = self._data.loc[position].to_dict()
        merged.update(changes)
        merged = self.tidy(merged)
        errors = self.validate(merged)
        if errors:
            return False, " ".join(errors)
        if self.name_taken(merged["name"], merged["district"], skip_position=position):
            return False, f"Another record already uses the name {merged['name']} in {merged['district']}."
        updated = self._data.copy()
        for column in self.columns:
            updated.at[position, column] = merged[column]
        ok, message = self.save(updated)
        return ok, f"Updated {merged['hospital_id']}." if ok else message

    def delete(self, record_id):
        position = self.find_position(record_id)
        if position is None:
            return False, f"No hospital found with ID {record_id}."
        name = self._data.at[position, "name"]
        remaining = self._data.drop(index=position).reset_index(drop=True)
        ok, message = self.save(remaining)
        return ok, f"Deleted {name} ({record_id})." if ok else message

    def rank_hospitals(self, frame, lat, lon, max_distance):
        ranked = frame.copy()
        if ranked.empty:
            return ranked
        ranked["distance_km"] = haversine_km(lat, lon, ranked["latitude"], ranked["longitude"]).round(2)
        ranked = ranked[ranked["distance_km"] <= max_distance].copy()
        scores = []
        for row in ranked.itertuples():
            services = np.mean([yes_score(row.pharmacy), yes_score(row.laboratory), yes_score(row.blood_bank)])
            hours = 100.0 if row.opening_hours == "24 Hours" else 60.0
            scores.append(round(0.60 * clamp100(100 - row.distance_km * 4) + 0.30 * services + 0.10 * hours, 1))
        ranked["match_score"] = scores
        ranked["match_class"] = ranked["match_score"].map(score_label)
        return ranked.sort_values(["match_score", "distance_km"], ascending=[False, True])

    def statistics(self, frame):
        if frame.empty:
            return {"hospitals": 0, "full_services": np.nan, "top_specialist": "-", "open_24h": 0}
        full = frame[["pharmacy", "laboratory", "blood_bank"]].eq("Yes").all(axis=1).mean() * 100
        counts = frame["specialist_doctor"].value_counts()
        return {
            "hospitals": len(frame),
            "full_services": full,
            "top_specialist": counts.index[0] if len(counts) else "-",
            "open_24h": int((frame["opening_hours"] == "24 Hours").sum()),
        }

    def specialist_counts(self, frame):
        counts = frame["specialist_doctor"].value_counts().reset_index()
        counts.columns = ["specialist", "hospitals"]
        return counts

    def report_text(self, frame, filters, strategy):
        lines = self.report_header("MedScope - Hospital Directory Report", frame, filters)
        stats = self.statistics(frame)
        lines += [
            f"Missing-value rule: {strategy}",
            "",
            "Summary statistics",
            f"  - Hospitals: {stats['hospitals']}",
            f"  - With pharmacy, laboratory and blood bank: {stats['full_services']:.1f}%",
            f"  - Most common specialist: {stats['top_specialist']}",
            f"  - Open 24 hours: {stats['open_24h']}",
            "",
            "Hospitals by specialist",
        ]
        for row in self.specialist_counts(frame).itertuples():
            lines.append(f"  - {row.specialist}: {row.hospitals}")
        return "\n".join(lines)

    def pdf_report(self, text):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=9)
        for line in text.split("\n"):
            safe = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, safe or " ", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return bytes(pdf.output())


def finder_tab(manager, analysis):
    section_title("1. Choose the patient's reference point")
    mode = st.radio("Reference point", ["Pick a place", "Custom coordinates"], horizontal=True, key="ref_mode")
    if mode == "Pick a place":
        place = st.selectbox("Place", list(REFERENCE_PLACES), key="ref_place")
        lat, lon = REFERENCE_PLACES[place]
        st.caption(f"Using {place}: {lat:.4f}, {lon:.4f}")
    else:
        c1, c2 = st.columns(2)
        lat = c1.number_input("Latitude", value=10.0, format="%.4f", key="ref_lat")
        lon = c2.number_input("Longitude", value=76.3, format="%.4f", key="ref_lon")
    max_distance = st.slider("Maximum distance (km)", 1, 150, 30, key="max_distance")
    st.caption("The sidebar filters (specialist, facilities, 24-hour opening) also apply here.")
    st.divider()
    section_title("2. Recommended hospitals")
    results = manager.rank_hospitals(analysis.dropna(subset=["latitude", "longitude"]), lat, lon, max_distance)
    if results.empty:
        st.warning("No hospital satisfies every requirement within this distance. Try a larger distance or fewer filters.")
        return
    st.success(f"{len(results)} hospital(s) match the requirements.")
    top = results.head(8)
    st.dataframe(
        top[["name", "district", "distance_km", "match_score", "match_class", "specialist_doctor",
             "pharmacy", "laboratory", "blood_bank", "opening_hours"]],
        hide_index=True, width="stretch",
    )
    left, right = st.columns(2)
    with left:
        best = top.iloc[0]
        section_title("Top recommendation")
        st.markdown(f"### {best['name']}")
        details = pd.DataFrame({
            "Feature": ["District", "Distance", "Match score", "Specialist", "Pharmacy", "Laboratory", "Blood bank", "Opening hours"],
            "Value": [best["district"], f"{best['distance_km']:.2f} km", f"{best['match_score']}/100 ({best['match_class']})",
                      best["specialist_doctor"], best["pharmacy"], best["laboratory"], best["blood_bank"], best["opening_hours"]],
        })
        st.table(details)
    with right:
        fig = px.scatter_map(top, lat="latitude", lon="longitude", hover_name="name",
                             hover_data={"distance_km": True, "match_score": True, "latitude": False, "longitude": False},
                             zoom=7, height=430, color_discrete_sequence=[VIOLET])
        fig.add_scattermap(lat=[lat], lon=[lon], marker=dict(size=18, color=PRIMARY), name="Patient reference point")
        fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, width="stretch")
    st.download_button("Download matching hospitals CSV", results.to_csv(index=False).encode("utf-8"),
                       "hospital_recommendations.csv", "text/csv")
    st.caption("Match score: distance 60%, pharmacy + laboratory + blood bank 30%, opening hours 10%.")


def records_tab(manager, shown, raw):
    section_title("Hospital directory")
    stats = manager.statistics(shown)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Hospitals", stats["hospitals"], PRIMARY)
    with c2:
        kpi_card("Full services", f"{stats['full_services']:.0f}%", TEAL)
    with c3:
        kpi_card("Open 24 hours", stats["open_24h"], AMBER)
    with c4:
        kpi_card("Top specialist", stats["top_specialist"], VIOLET)
    st.write("")
    left, right = st.columns([2, 1])
    sort_column = left.selectbox("Sort by", manager.columns, key="sort_column")
    order = right.radio("Order", ["Ascending", "Descending"], horizontal=True, key="sort_order")
    table = manager.sort_records(raw, sort_column, order == "Ascending")
    st.dataframe(manager.display_frame(table), hide_index=True, width="stretch")
    st.caption(f"Showing {len(table)} of {manager.row_count} records. Empty cells are shown as blank.")


def add_tab(manager):
    section_title("Add a hospital to the directory")
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        record = {}
        record["hospital_id"] = c1.text_input("Hospital ID", value=manager.next_id(), key="add_id")
        record["name"] = c2.text_input("Hospital name", key="add_name")
        record["district"] = c1.selectbox("District", DISTRICTS, key="add_district")
        record["specialist_doctor"] = c2.selectbox("Specialist doctor", SPECIALISTS, key="add_specialist")
        record["latitude"] = c1.number_input("Latitude", value=10.0, format="%.4f", key="add_lat")
        record["longitude"] = c2.number_input("Longitude", value=76.3, format="%.4f", key="add_lon")
        record["opening_hours"] = c1.selectbox("Opening hours", OPENING_HOURS, key="add_hours")
        record["pharmacy"] = c2.selectbox("Pharmacy", YES_NO, key="add_pharmacy")
        record["laboratory"] = c1.selectbox("Laboratory", YES_NO, key="add_laboratory")
        record["blood_bank"] = c2.selectbox("Blood bank", YES_NO, key="add_blood")
        submitted = st.form_submit_button("Add hospital")
    if submitted:
        ok, message = manager.create(record)
        flash("success" if ok else "error", message)
        st.rerun()


def edit_tab(manager):
    section_title("Edit a directory entry")
    data = manager.data
    if data.empty:
        st.info("There are no records to edit.")
        return
    labels = dict(zip(data["hospital_id"], data["hospital_id"] + " - " + data["name"].fillna("(no name)")))
    record_id = st.selectbox("Choose a record", data["hospital_id"].tolist(), format_func=labels.get, key="edit_pick")
    row = data.loc[data["hospital_id"] == record_id].iloc[0]
    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        changes = {}
        changes["name"] = c1.text_input("Hospital name", value=str(row["name"]), key=f"edit_name_{record_id}")
        district_options = DISTRICTS if row["district"] in DISTRICTS else DISTRICTS + [row["district"]]
        changes["district"] = c2.selectbox("District", district_options, index=choice_index(district_options, row["district"]), key=f"edit_district_{record_id}")
        changes["specialist_doctor"] = c1.selectbox("Specialist doctor", SPECIALISTS, index=choice_index(SPECIALISTS, row["specialist_doctor"]), key=f"edit_specialist_{record_id}")
        changes["opening_hours"] = c2.selectbox("Opening hours", OPENING_HOURS, index=choice_index(OPENING_HOURS, row["opening_hours"]), key=f"edit_hours_{record_id}")
        changes["latitude"] = c1.number_input("Latitude", value=safe_number(row["latitude"], 10.0), format="%.4f", key=f"edit_lat_{record_id}")
        changes["longitude"] = c2.number_input("Longitude", value=safe_number(row["longitude"], 76.3), format="%.4f", key=f"edit_lon_{record_id}")
        changes["pharmacy"] = c1.selectbox("Pharmacy", YES_NO, index=choice_index(YES_NO, row["pharmacy"]), key=f"edit_pharmacy_{record_id}")
        changes["laboratory"] = c2.selectbox("Laboratory", YES_NO, index=choice_index(YES_NO, row["laboratory"]), key=f"edit_laboratory_{record_id}")
        changes["blood_bank"] = c1.selectbox("Blood bank", YES_NO, index=choice_index(YES_NO, row["blood_bank"]), key=f"edit_blood_{record_id}")
        submitted = st.form_submit_button("Save changes")
    if submitted:
        ok, message = manager.update(record_id, changes)
        flash("success" if ok else "error", message)
        st.rerun()


def delete_tab(manager):
    section_title("Delete a directory entry")
    data = manager.data
    if data.empty:
        st.info("There are no records to delete.")
        return
    labels = dict(zip(data["hospital_id"], data["hospital_id"] + " - " + data["name"].fillna("(no name)")))
    record_id = st.selectbox("Choose a record", data["hospital_id"].tolist(), format_func=labels.get, key="delete_pick")
    st.dataframe(manager.display_frame(data[data["hospital_id"] == record_id]), hide_index=True, width="stretch")
    st.warning("Deleting removes this row from the CSV file permanently.")
    confirmed = st.checkbox("Yes, delete this record", key=f"delete_confirm_{record_id}")
    if st.button("Delete record", disabled=not confirmed, key="delete_button"):
        ok, message = manager.delete(record_id)
        flash("success" if ok else "error", message)
        st.rerun()


def charts_tab(manager, analysis):
    if analysis.empty:
        st.info("No data to chart with the current filters.")
        return
    left, right = st.columns(2)
    with left:
        section_title("Hospitals by specialist")
        counts = manager.specialist_counts(analysis).sort_values("hospitals")
        fig = px.bar(counts, x="hospitals", y="specialist", orientation="h",
                     labels={"hospitals": "Hospitals", "specialist": "Specialist"})
        fig.update_traces(marker_color=PRIMARY)
        st.plotly_chart(style_chart(fig), width="stretch")
    with right:
        section_title("Opening hours")
        fig = px.pie(analysis, names="opening_hours", hole=0.5,
                     color_discrete_sequence=[PRIMARY, TEAL, AMBER, VIOLET])
        st.plotly_chart(style_chart(fig), width="stretch")


def report_tab(manager, shown, filters, strategy):
    section_title("Export a summary report")
    text = manager.report_text(shown, filters, strategy)
    st.code(text, language=None)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    c1, c2, c3 = st.columns(3)
    c1.download_button("Download report (.txt)", text.encode("utf-8"), f"directory_report_{stamp}.txt", "text/plain")
    c2.download_button("Download report (.pdf)", manager.pdf_report(text), f"directory_report_{stamp}.pdf", "application/pdf")
    c3.download_button("Download filtered data (.csv)", shown.to_csv(index=False).encode("utf-8"),
                       f"directory_data_{stamp}.csv", "text/csv")


manager = DirectoryManager()
load_manager(manager)

hero(
    "Hospital Finder",
    "Enter patient requirements and receive a ranked list of nearby hospitals, with an "
    "explainable match score, a map and downloadable reports.",
)
show_flash()

st.sidebar.header("Requirements and filters")
search = st.sidebar.text_input("Search hospital name")
picked_districts = st.sidebar.multiselect("District", DISTRICTS)
specialist = st.sidebar.selectbox("Required specialist", ["Any specialist"] + SPECIALISTS)
picked_facilities = [label for label in FACILITIES if st.sidebar.checkbox(label)]
open_24h = st.sidebar.checkbox("Open 24 hours")
strategy = st.sidebar.radio("Missing values", [EXCLUDE_ROWS, FILL_MEDIAN])

filters = {
    "Search": search,
    "Districts": ", ".join(picked_districts),
    "Specialist": specialist if specialist != "Any specialist" else "",
    "Required facilities": ", ".join(picked_facilities),
    "Open 24 hours": "Yes" if open_24h else "",
}
raw = manager.search(search, picked_districts, specialist, [FACILITIES[f] for f in picked_facilities], open_24h)
analysis = manager.apply_missing_strategy(raw, strategy)
missing_notice(manager, raw, strategy)

tabs = st.tabs(["Find hospitals", "Records", "Add", "Edit", "Delete", "Charts", "Report"])
with tabs[0]:
    finder_tab(manager, analysis)
with tabs[1]:
    records_tab(manager, analysis, raw)
with tabs[2]:
    add_tab(manager)
with tabs[3]:
    edit_tab(manager)
with tabs[4]:
    delete_tab(manager)
with tabs[5]:
    charts_tab(manager, analysis)
with tabs[6]:
    report_tab(manager, analysis, filters, strategy)
