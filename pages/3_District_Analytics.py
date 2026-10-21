from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from csv_manager import CSVManager, EXCLUDE_ROWS, FILL_MEDIAN
from utils import (
    section_nav, keep_widget_state,
    inject_css, hero, section_title, kpi_card, flash, show_flash, load_manager,
    missing_notice, style_chart, score_label, safe_number, RATING_COLORS,
    PRIMARY, TEAL, AMBER, CORAL,
)

st.set_page_config(page_title="District Analytics", page_icon="📊", layout="wide")
inject_css()
keep_widget_state()


class DistrictManager(CSVManager):
    def __init__(self):
        super().__init__(
            file_name="district_profiles.csv",
            columns=[
                "district_id", "district", "population_2011", "centroid_lat", "centroid_lon",
                "hospitals_nearby", "beds_nearby", "icu_beds_nearby", "nearest_hospital_km",
                "service_coverage", "avg_waiting_min", "avg_rating",
            ],
            id_column="district_id",
            id_prefix="D",
            id_width=2,
            numeric_columns=[
                "population_2011", "centroid_lat", "centroid_lon", "hospitals_nearby",
                "beds_nearby", "icu_beds_nearby", "nearest_hospital_km", "service_coverage",
                "avg_waiting_min", "avg_rating",
            ],
            integer_columns=["population_2011", "hospitals_nearby", "beds_nearby", "icu_beds_nearby"],
        )

    def validate(self, record):
        errors = self.check_required(record, ["district_id", "district"])
        errors += self.check_number(record, "population_2011", 1, 50000000, whole=True)
        errors += self.check_number(record, "centroid_lat", 8.0, 13.0)
        errors += self.check_number(record, "centroid_lon", 74.5, 77.5)
        errors += self.check_number(record, "hospitals_nearby", 0, 1000, whole=True)
        errors += self.check_number(record, "beds_nearby", 0, 100000, whole=True)
        errors += self.check_number(record, "icu_beds_nearby", 0, 10000, whole=True)
        errors += self.check_number(record, "nearest_hospital_km", 0, 500)
        errors += self.check_number(record, "service_coverage", 0, 100)
        errors += self.check_number(record, "avg_waiting_min", 0, 600)
        errors += self.check_number(record, "avg_rating", 0, 5)
        return errors

    def district_taken(self, name, skip_position=None):
        same = self._data["district"].str.lower() == str(name).strip().lower()
        if skip_position is not None:
            same = same & (self._data.index != skip_position)
        return bool(same.any())

    def create(self, record):
        record = self.tidy(record)
        errors = self.validate(record)
        if errors:
            return False, " ".join(errors)
        if self.id_exists(record["district_id"]):
            return False, f"A district with ID {record['district_id']} already exists."
        if self.district_taken(record["district"]):
            return False, f"{record['district']} is already in the file."
        new_row = pd.DataFrame([record], columns=self.columns)
        combined = new_row if self._data.empty else pd.concat([self._data, new_row], ignore_index=True)
        ok, message = self.save(combined)
        return ok, f"Added {record['district']} as {record['district_id']}." if ok else message

    def search(self, text="", min_population=0):
        result = self._data.copy()
        if text:
            result = result[result["district"].str.contains(text, case=False, na=False, regex=False)]
        if min_population:
            result = result[result["population_2011"] >= min_population]
        return result

    def update(self, record_id, changes):
        position = self.find_position(record_id)
        if position is None:
            return False, f"No district found with ID {record_id}."
        merged = self._data.loc[position].to_dict()
        merged.update(changes)
        merged = self.tidy(merged)
        errors = self.validate(merged)
        if errors:
            return False, " ".join(errors)
        if self.district_taken(merged["district"], skip_position=position):
            return False, f"Another record already uses the name {merged['district']}."
        updated = self._data.copy()
        for column in self.columns:
            updated.at[position, column] = merged[column]
        ok, message = self.save(updated)
        return ok, f"Updated {merged['district']}." if ok else message

    def delete(self, record_id):
        position = self.find_position(record_id)
        if position is None:
            return False, f"No district found with ID {record_id}."
        name = self._data.at[position, "district"]
        remaining = self._data.drop(index=position).reset_index(drop=True)
        ok, message = self.save(remaining)
        return ok, f"Deleted {name} ({record_id})." if ok else message

    def add_scores(self, frame):
        scored = frame.copy()
        population = scored["population_2011"].replace(0, np.nan)
        scored["beds_per_100k"] = (scored["beds_nearby"] / population * 100000).round(1)
        scored["icu_per_100k"] = (scored["icu_beds_nearby"] / population * 100000).round(2)
        distance = (100 - scored["nearest_hospital_km"] * 4).clip(0, 100)
        capacity = scored["beds_per_100k"].clip(0, 100)
        icu = (scored["icu_per_100k"] * 10).clip(0, 100)
        services = scored["service_coverage"].clip(0, 100)
        waiting = (100 - scored["avg_waiting_min"] * 0.8).clip(0, 100)
        rating = (scored["avg_rating"] / 5 * 100).clip(0, 100)
        scored["accessibility_score"] = (
            0.30 * distance + 0.30 * capacity + 0.10 * icu
            + 0.20 * services + 0.05 * waiting + 0.05 * rating
        ).round(1)
        scored["accessibility"] = scored["accessibility_score"].map(score_label)
        return scored

    def statistics(self, scored):
        if scored.empty:
            return {"districts": 0, "avg_score": np.nan, "avg_distance": np.nan,
                    "poor": 0, "good": 0, "moderate": 0, "total_population": 0}
        return {
            "districts": len(scored),
            "avg_score": scored["accessibility_score"].mean(),
            "avg_distance": scored["nearest_hospital_km"].mean(),
            "good": int((scored["accessibility"] == "Good").sum()),
            "moderate": int((scored["accessibility"] == "Moderate").sum()),
            "poor": int((scored["accessibility"] == "Poor").sum()),
            "total_population": scored["population_2011"].sum(),
        }

    def report_text(self, scored, filters, strategy):
        lines = self.report_header("MedScope - District Accessibility Report", scored, filters)
        stats = self.statistics(scored)
        lines += [
            f"Missing-value rule: {strategy}",
            "",
            "Summary statistics",
            f"  - Districts: {stats['districts']}",
            f"  - Average accessibility score: {stats['avg_score']:.1f}",
            f"  - Average nearest-hospital distance: {stats['avg_distance']:.1f} km",
            f"  - Good / Moderate / Poor: {stats['good']} / {stats['moderate']} / {stats['poor']}",
            "",
            "Ranking",
        ]
        ranked = scored.sort_values("accessibility_score", ascending=False)
        for position, row in enumerate(ranked.itertuples(), start=1):
            lines.append(f"  {position}. {row.district}: {row.accessibility_score} ({row.accessibility})")
        return "\n".join(lines)


def analytics_tab(manager, scored):
    if scored.empty:
        st.info("No districts match the current filters.")
        return
    stats = manager.statistics(scored)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Districts", stats["districts"], PRIMARY)
    with c2:
        kpi_card("Average score", f"{stats['avg_score']:.1f}/100", TEAL)
    with c3:
        kpi_card("Average nearest distance", f"{stats['avg_distance']:.1f} km", AMBER)
    with c4:
        kpi_card("Poor districts", stats["poor"], CORAL)
    st.write("")
    g1, g2, g3 = st.columns(3)
    with g1:
        kpi_card("Good", stats["good"], TEAL)
    with g2:
        kpi_card("Moderate", stats["moderate"], AMBER)
    with g3:
        kpi_card("Poor", stats["poor"], CORAL)
    st.divider()
    section_title("District ranking")
    ranked = scored.sort_values(["accessibility_score", "nearest_hospital_km"], ascending=[False, True])
    columns = [
        "district", "population_2011", "accessibility_score", "accessibility", "nearest_hospital_km",
        "hospitals_nearby", "beds_nearby", "icu_beds_nearby", "beds_per_100k", "icu_per_100k",
        "service_coverage", "avg_waiting_min", "avg_rating",
    ]
    st.dataframe(manager.display_frame(ranked[columns]), hide_index=True, width="stretch")
    st.divider()
    section_title("Compare two districts")
    names = sorted(scored["district"])
    a, b = st.columns(2)
    first = a.selectbox("District A", names, index=0, key="compare_a")
    second = b.selectbox("District B", names, index=min(1, len(names) - 1), key="compare_b")
    row_a = scored.loc[scored["district"] == first].iloc[0]
    row_b = scored.loc[scored["district"] == second].iloc[0]
    metrics = [
        ("Accessibility score", "accessibility_score"), ("Accessibility class", "accessibility"),
        ("Population", "population_2011"), ("Nearest hospital (km)", "nearest_hospital_km"),
        ("Hospitals nearby", "hospitals_nearby"), ("Beds nearby", "beds_nearby"),
        ("ICU beds nearby", "icu_beds_nearby"), ("Beds per 100k", "beds_per_100k"),
        ("ICU per 100k", "icu_per_100k"), ("Service coverage (%)", "service_coverage"),
        ("Average waiting (min)", "avg_waiting_min"), ("Average rating", "avg_rating"),
    ]
    comparison = pd.DataFrame({
        "Metric": [label for label, _ in metrics],
        first: [str(row_a[key]) for _, key in metrics],
        f"{second} " if second == first else second: [str(row_b[key]) for _, key in metrics],
    })
    st.dataframe(comparison, hide_index=True, width="stretch")


def records_tab(manager, scored, raw):
    section_title("District records")
    stats = manager.statistics(scored)
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Districts in view", len(raw), PRIMARY)
    with c2:
        kpi_card("Total population", f"{int(stats['total_population']):,}", TEAL)
    with c3:
        kpi_card("Average score", f"{stats['avg_score']:.1f}", AMBER)
    st.write("")
    left, right = st.columns([2, 1])
    sort_column = left.selectbox("Sort by", manager.columns, key="sort_column")
    order = right.radio("Order", ["Ascending", "Descending"], horizontal=True, key="sort_order")
    table = manager.sort_records(raw, sort_column, order == "Ascending")
    st.dataframe(manager.display_frame(table), hide_index=True, width="stretch")
    st.caption(f"Showing {len(table)} of {manager.row_count} records. Empty cells are shown as blank.")
    if not scored.empty:
        section_title("Summary of numeric columns")
        summary = scored[["population_2011", "beds_nearby", "nearest_hospital_km", "avg_rating"]].describe().round(2)
        st.dataframe(summary, width="stretch")


def form_fields(prefix, defaults, record_id=""):
    c1, c2 = st.columns(2)
    key = lambda name: f"{prefix}_{name}_{record_id}".rstrip("_")
    values = {}
    values["district"] = c1.text_input("District name", value=defaults["district"], key=key("district"))
    values["population_2011"] = c2.number_input("Population (2011)", 1, 50000000, int(defaults["population_2011"]), key=key("population"))
    values["centroid_lat"] = c1.number_input("Centroid latitude", value=defaults["centroid_lat"], format="%.4f", key=key("lat"))
    values["centroid_lon"] = c2.number_input("Centroid longitude", value=defaults["centroid_lon"], format="%.4f", key=key("lon"))
    values["hospitals_nearby"] = c1.number_input("Hospitals within 25 km", 0, 1000, int(defaults["hospitals_nearby"]), key=key("hospitals"))
    values["beds_nearby"] = c2.number_input("Beds within 25 km", 0, 100000, int(defaults["beds_nearby"]), key=key("beds"))
    values["icu_beds_nearby"] = c1.number_input("ICU beds within 25 km", 0, 10000, int(defaults["icu_beds_nearby"]), key=key("icu"))
    values["nearest_hospital_km"] = c2.number_input("Nearest hospital (km)", 0.0, 500.0, float(defaults["nearest_hospital_km"]), key=key("nearest"))
    values["service_coverage"] = c1.number_input("Service coverage (%)", 0.0, 100.0, float(defaults["service_coverage"]), key=key("coverage"))
    values["avg_waiting_min"] = c2.number_input("Average waiting (min)", 0.0, 600.0, float(defaults["avg_waiting_min"]), key=key("waiting"))
    values["avg_rating"] = c1.number_input("Average rating (0-5)", 0.0, 5.0, float(defaults["avg_rating"]), step=0.1, key=key("rating"))
    return values


def add_tab(manager):
    section_title("Add a district")
    defaults = {"district": "", "population_2011": 1000000, "centroid_lat": 10.0, "centroid_lon": 76.3,
                "hospitals_nearby": 1, "beds_nearby": 100, "icu_beds_nearby": 10,
                "nearest_hospital_km": 5.0, "service_coverage": 70.0, "avg_waiting_min": 60.0, "avg_rating": 4.0}
    with st.form("add_form", clear_on_submit=True):
        record = {"district_id": st.text_input("District ID", value=manager.next_id(), key="add_id")}
        record.update(form_fields("add", defaults))
        submitted = st.form_submit_button("Add district")
    if submitted:
        ok, message = manager.create(record)
        flash("success" if ok else "error", message)
        st.rerun()


def edit_tab(manager):
    section_title("Edit a district")
    data = manager.data
    if data.empty:
        st.info("There are no records to edit.")
        return
    labels = dict(zip(data["district_id"], data["district_id"] + " - " + data["district"].fillna("(no name)")))
    record_id = st.selectbox("Choose a record", data["district_id"].tolist(), format_func=labels.get, key="edit_pick")
    row = data.loc[data["district_id"] == record_id].iloc[0]
    defaults = {key: (str(row[key]) if key == "district" else safe_number(row[key], 0.0)) for key in manager.columns[1:]}
    with st.form("edit_form"):
        changes = form_fields("edit", defaults, record_id)
        submitted = st.form_submit_button("Save changes")
    if submitted:
        ok, message = manager.update(record_id, changes)
        flash("success" if ok else "error", message)
        st.rerun()


def delete_tab(manager):
    section_title("Delete a district")
    data = manager.data
    if data.empty:
        st.info("There are no records to delete.")
        return
    labels = dict(zip(data["district_id"], data["district_id"] + " - " + data["district"].fillna("(no name)")))
    record_id = st.selectbox("Choose a record", data["district_id"].tolist(), format_func=labels.get, key="delete_pick")
    st.dataframe(manager.display_frame(data[data["district_id"] == record_id]), hide_index=True, width="stretch")
    st.warning("Deleting removes this row from the CSV file permanently.")
    confirmed = st.checkbox("Yes, delete this record", key=f"delete_confirm_{record_id}")
    if st.button("Delete record", disabled=not confirmed, key="delete_button"):
        ok, message = manager.delete(record_id)
        flash("success" if ok else "error", message)
        st.rerun()


def charts_tab(scored):
    if scored.empty:
        st.info("No data to chart with the current filters.")
        return
    left, right = st.columns(2)
    with left:
        section_title("Accessibility score by district")
        fig = px.bar(scored.sort_values("accessibility_score"), x="accessibility_score", y="district",
                     orientation="h", color="accessibility", color_discrete_map=RATING_COLORS,
                     labels={"accessibility_score": "Score / 100", "district": "District"})
        st.plotly_chart(style_chart(fig, 460), width="stretch")
    with right:
        section_title("Population vs nearest-hospital distance")
        fig = px.scatter(scored, x="population_2011", y="nearest_hospital_km", size="beds_nearby",
                         color="accessibility", hover_name="district", color_discrete_map=RATING_COLORS,
                         labels={"population_2011": "Population", "nearest_hospital_km": "Nearest hospital (km)"})
        st.plotly_chart(style_chart(fig, 460), width="stretch")


def report_tab(manager, scored, filters, strategy):
    section_title("Export a summary report")
    text = manager.report_text(scored, filters, strategy)
    st.code(text, language=None)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    c1, c2 = st.columns(2)
    c1.download_button("Download report (.txt)", text.encode("utf-8"), f"district_report_{stamp}.txt", "text/plain")
    c2.download_button("Download scored data (.csv)", scored.to_csv(index=False).encode("utf-8"),
                       f"district_scores_{stamp}.csv", "text/csv")


manager = DistrictManager()
load_manager(manager)

hero(
    "District Analytics",
    "Measure healthcare accessibility at district level using distance, capacity, ICU resources, "
    "services, waiting time and rating.",
)
show_flash()

st.sidebar.header("Filters")
search = st.sidebar.text_input("Search district name")
min_population = st.sidebar.slider("Minimum population", 0, 4500000, 0, step=250000)
strategy = st.sidebar.radio("Missing values", [EXCLUDE_ROWS, FILL_MEDIAN])

filters = {
    "Search": search,
    "Minimum population": f"{min_population:,}" if min_population else "",
}
raw = manager.search(search, min_population)
scored = manager.add_scores(manager.apply_missing_strategy(raw, strategy))
missing_notice(manager, raw, strategy)

LABELS = ["Analytics", "Records", "Add", "Edit", "Delete", "Charts", "Report"]
active = section_nav(LABELS)
if active == LABELS[0]:
    analytics_tab(manager, scored)
elif active == LABELS[1]:
    records_tab(manager, scored, raw)
elif active == LABELS[2]:
    add_tab(manager)
elif active == LABELS[3]:
    edit_tab(manager)
elif active == LABELS[4]:
    delete_tab(manager)
elif active == LABELS[5]:
    charts_tab(scored)
elif active == LABELS[6]:
    report_tab(manager, scored, filters, strategy)
