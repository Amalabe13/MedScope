from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from csv_manager import CSVManager, EXCLUDE_ROWS, FILL_MEDIAN
from utils import (
    section_nav, keep_widget_state,
    inject_css, hero, section_title, kpi_card, flash, show_flash, load_manager,
    missing_notice, style_chart, safe_number, choice_index, DISTRICTS, HOSPITAL_TYPES,
    TYPE_COLORS, PRIMARY, TEAL, AMBER, VIOLET,
)

st.set_page_config(page_title="Map Explorer", page_icon="🗺️", layout="wide")
inject_css()
keep_widget_state()


class LocationManager(CSVManager):
    def __init__(self):
        super().__init__(
            file_name="hospital_locations.csv",
            columns=["hospital_id", "name", "district", "type", "latitude", "longitude", "beds"],
            id_column="hospital_id",
            id_prefix="H",
            numeric_columns=["latitude", "longitude", "beds"],
            integer_columns=["beds"],
        )

    def validate(self, record):
        errors = self.check_required(record, ["hospital_id", "name", "district", "type"])
        errors += self.check_choice(record, "district", DISTRICTS)
        errors += self.check_choice(record, "type", HOSPITAL_TYPES)
        errors += self.check_number(record, "latitude", 8.0, 13.0)
        errors += self.check_number(record, "longitude", 74.5, 77.5)
        errors += self.check_number(record, "beds", 1, 5000, whole=True)
        return errors

    def create(self, record):
        record = self.tidy(record)
        errors = self.validate(record)
        if errors:
            return False, " ".join(errors)
        if self.id_exists(record["hospital_id"]):
            return False, f"A hospital with ID {record['hospital_id']} already exists."
        if self.name_taken(record["name"], record["district"]):
            return False, f"{record['name']} is already on the map for {record['district']}."
        new_row = pd.DataFrame([record], columns=self.columns)
        combined = new_row if self._data.empty else pd.concat([self._data, new_row], ignore_index=True)
        ok, message = self.save(combined)
        return ok, f"Added {record['name']} as {record['hospital_id']}." if ok else message

    def search(self, text="", districts=None, types=None, min_beds=0):
        result = self._data.copy()
        if text:
            result = result[result["name"].str.contains(text, case=False, na=False, regex=False)]
        if districts:
            result = result[result["district"].isin(districts)]
        if types:
            result = result[result["type"].isin(types)]
        if min_beds:
            result = result[result["beds"] >= min_beds]
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

    def statistics(self, frame):
        if frame.empty:
            return {"hospitals": 0, "total_beds": 0, "mean_beds": np.nan,
                    "government_share": np.nan, "largest": "-"}
        largest = frame.loc[frame["beds"].idxmax(), "name"] if frame["beds"].notna().any() else "-"
        return {
            "hospitals": len(frame),
            "total_beds": frame["beds"].sum(),
            "mean_beds": frame["beds"].mean(),
            "government_share": (frame["type"] == "Government").mean() * 100,
            "largest": largest,
        }

    def district_summary(self, frame):
        return (
            frame.groupby("district")
            .agg(hospitals=("hospital_id", "count"), total_beds=("beds", "sum"),
                 average_beds=("beds", "mean"))
            .round(1)
            .reset_index()
            .sort_values("total_beds", ascending=False)
        )

    def report_text(self, frame, filters, strategy):
        lines = self.report_header("MedScope - Hospital Locations Report", frame, filters)
        stats = self.statistics(frame)
        lines += [
            f"Missing-value rule: {strategy}",
            "",
            "Summary statistics",
            f"  - Hospitals: {stats['hospitals']}",
            f"  - Total beds: {int(stats['total_beds'])}",
            f"  - Average beds per hospital: {stats['mean_beds']:.1f}",
            f"  - Government hospitals: {stats['government_share']:.1f}%",
            f"  - Largest hospital: {stats['largest']}",
            "",
            "Beds by district",
        ]
        for row in self.district_summary(frame).itertuples():
            lines.append(f"  - {row.district}: {int(row.total_beds)} beds in {row.hospitals} hospitals")
        return "\n".join(lines)


def map_tab(manager, analysis):
    mappable = analysis.dropna(subset=["latitude", "longitude", "beds"])
    section_title(f"{len(mappable)} hospitals shown")
    st.caption("Marker size shows the number of beds. Colour shows the hospital type.")
    if mappable.empty:
        st.info("No hospitals match the current filters.")
        return
    fig = px.scatter_map(
        mappable, lat="latitude", lon="longitude", size="beds", color="type",
        hover_name="name", hover_data={"district": True, "beds": True, "latitude": False, "longitude": False},
        color_discrete_map=TYPE_COLORS, size_max=28, zoom=6.2, height=560,
        center={"lat": float(mappable["latitude"].mean()), "lon": float(mappable["longitude"].mean())},
    )
    fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")
    section_title("District snapshot")
    st.dataframe(manager.district_summary(mappable), hide_index=True, width="stretch")
    st.info("Positions are stored as latitude and longitude in the CSV. Distances elsewhere in MedScope are straight-line, not road travel time.")


def records_tab(manager, shown, raw):
    section_title("Hospital locations")
    stats = manager.statistics(shown)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Hospitals", stats["hospitals"], PRIMARY)
    with c2:
        kpi_card("Total beds", f"{int(stats['total_beds']):,}", TEAL)
    with c3:
        kpi_card("Average beds", f"{stats['mean_beds']:.0f}", AMBER)
    with c4:
        kpi_card("Government share", f"{stats['government_share']:.0f}%", VIOLET)
    st.write("")
    left, right = st.columns([2, 1])
    sort_column = left.selectbox("Sort by", manager.columns, key="sort_column")
    order = right.radio("Order", ["Ascending", "Descending"], horizontal=True, key="sort_order")
    table = manager.sort_records(raw, sort_column, order == "Ascending")
    st.dataframe(manager.display_frame(table), hide_index=True, width="stretch")
    st.caption(f"Showing {len(table)} of {manager.row_count} records. Largest hospital in view: {stats['largest']}.")


def add_tab(manager):
    section_title("Add a hospital location")
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        record = {}
        record["hospital_id"] = c1.text_input("Hospital ID", value=manager.next_id(), key="add_id")
        record["name"] = c2.text_input("Hospital name", key="add_name")
        record["district"] = c1.selectbox("District", DISTRICTS, key="add_district")
        record["type"] = c2.selectbox("Type", HOSPITAL_TYPES, key="add_type")
        record["latitude"] = c1.number_input("Latitude", value=10.0, format="%.4f", key="add_lat")
        record["longitude"] = c2.number_input("Longitude", value=76.3, format="%.4f", key="add_lon")
        record["beds"] = c1.number_input("Beds", 1, 5000, 100, key="add_beds")
        submitted = st.form_submit_button("Add hospital")
    if submitted:
        ok, message = manager.create(record)
        flash("success" if ok else "error", message)
        st.rerun()


def edit_tab(manager):
    section_title("Edit a hospital location")
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
        changes["type"] = c1.selectbox("Type", HOSPITAL_TYPES, index=choice_index(HOSPITAL_TYPES, row["type"]), key=f"edit_type_{record_id}")
        changes["beds"] = c2.number_input("Beds", 1, 5000, int(max(1, safe_number(row["beds"], 1))), key=f"edit_beds_{record_id}")
        changes["latitude"] = c1.number_input("Latitude", value=safe_number(row["latitude"], 10.0), format="%.4f", key=f"edit_lat_{record_id}")
        changes["longitude"] = c2.number_input("Longitude", value=safe_number(row["longitude"], 76.3), format="%.4f", key=f"edit_lon_{record_id}")
        submitted = st.form_submit_button("Save changes")
    if submitted:
        ok, message = manager.update(record_id, changes)
        flash("success" if ok else "error", message)
        st.rerun()


def delete_tab(manager):
    section_title("Delete a hospital location")
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
        section_title("Government vs private")
        fig = px.pie(analysis, names="type", hole=0.5, color="type", color_discrete_map=TYPE_COLORS)
        st.plotly_chart(style_chart(fig), width="stretch")
    with right:
        section_title("Bed capacity distribution")
        fig = px.histogram(analysis, x="beds", nbins=12, labels={"beds": "Beds"})
        fig.update_traces(marker_color=TEAL)
        st.plotly_chart(style_chart(fig), width="stretch")
    section_title("Total beds by district")
    summary = manager.district_summary(analysis).sort_values("total_beds")
    fig = px.bar(summary, x="total_beds", y="district", orientation="h", labels={"total_beds": "Total beds", "district": "District"})
    fig.update_traces(marker_color=PRIMARY)
    st.plotly_chart(style_chart(fig, 420), width="stretch")


def report_tab(manager, shown, filters, strategy):
    section_title("Export a summary report")
    text = manager.report_text(shown, filters, strategy)
    st.code(text, language=None)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    c1, c2 = st.columns(2)
    c1.download_button("Download report (.txt)", text.encode("utf-8"), f"locations_report_{stamp}.txt", "text/plain")
    c2.download_button("Download filtered data (.csv)", shown.to_csv(index=False).encode("utf-8"),
                       f"locations_data_{stamp}.csv", "text/csv")


manager = LocationManager()
load_manager(manager)

hero(
    "Map Explorer",
    "Explore hospital locations and capacity across Kerala. Use the sidebar to focus on a type, "
    "district or facility, and keep the location data up to date.",
)
show_flash()

st.sidebar.header("Filters")
search = st.sidebar.text_input("Search hospital name")
picked_types = st.sidebar.multiselect("Hospital type", HOSPITAL_TYPES)
picked_districts = st.sidebar.multiselect("District", DISTRICTS)
min_beds = st.sidebar.slider("Minimum beds", 0, 1500, 0, step=50)
strategy = st.sidebar.radio("Missing values", [EXCLUDE_ROWS, FILL_MEDIAN])

filters = {
    "Search": search,
    "Types": ", ".join(picked_types),
    "Districts": ", ".join(picked_districts),
    "Minimum beds": str(min_beds) if min_beds else "",
}
raw = manager.search(search, picked_districts, picked_types, min_beds)
analysis = manager.apply_missing_strategy(raw, strategy)
missing_notice(manager, raw, strategy)

LABELS = ["Map", "Records", "Add", "Edit", "Delete", "Charts", "Report"]
active = section_nav(LABELS)
if active == LABELS[0]:
    map_tab(manager, analysis)
elif active == LABELS[1]:
    records_tab(manager, analysis, raw)
elif active == LABELS[2]:
    add_tab(manager)
elif active == LABELS[3]:
    edit_tab(manager)
elif active == LABELS[4]:
    delete_tab(manager)
elif active == LABELS[5]:
    charts_tab(manager, analysis)
elif active == LABELS[6]:
    report_tab(manager, analysis, filters, strategy)
