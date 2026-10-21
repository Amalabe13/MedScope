from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from csv_manager import CSVManager, EXCLUDE_ROWS, FILL_MEDIAN
from utils import (
    section_nav, keep_widget_state,
    inject_css, hero, section_title, kpi_card, flash, show_flash, load_manager,
    missing_notice, style_chart, haversine_km, clamp100, yes_score, score_label,
    safe_number, choice_index, DISTRICTS, YES_NO, REFERENCE_PLACES, RATING_COLORS,
    PRIMARY, TEAL, AMBER, VIOLET,
)

st.set_page_config(page_title="Accessibility Analyzer", page_icon="🩺", layout="wide")
inject_css()
keep_widget_state()

DEFAULT_WEIGHTS = {
    "Distance": 25, "ICU": 15, "Emergency": 20, "Wheelchair": 15,
    "Ambulance": 15, "Waiting time": 5, "Rating": 5,
}


class ReadinessManager(CSVManager):
    def __init__(self):
        super().__init__(
            file_name="hospital_readiness.csv",
            columns=[
                "hospital_id", "name", "district", "latitude", "longitude", "icu_beds",
                "emergency", "wheelchair_access", "ambulance", "avg_waiting_min", "rating",
            ],
            id_column="hospital_id",
            id_prefix="H",
            numeric_columns=["latitude", "longitude", "icu_beds", "avg_waiting_min", "rating"],
            integer_columns=["icu_beds"],
            yes_no_columns=["emergency", "wheelchair_access", "ambulance"],
        )

    def validate(self, record):
        errors = self.check_required(record, ["hospital_id", "name", "district"])
        errors += self.check_choice(record, "district", DISTRICTS)
        errors += self.check_number(record, "latitude", 8.0, 13.0)
        errors += self.check_number(record, "longitude", 74.5, 77.5)
        errors += self.check_number(record, "icu_beds", 0, 1000, whole=True)
        errors += self.check_number(record, "avg_waiting_min", 0, 600)
        errors += self.check_number(record, "rating", 0, 5)
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
            return False, f"{record['name']} is already listed for {record['district']}."
        new_row = pd.DataFrame([record], columns=self.columns)
        combined = new_row if self._data.empty else pd.concat([self._data, new_row], ignore_index=True)
        ok, message = self.save(combined)
        return ok, f"Added {record['name']} as {record['hospital_id']}." if ok else message

    def search(self, text="", districts=None, emergency_only=False):
        result = self._data.copy()
        if text:
            result = result[result["name"].str.contains(text, case=False, na=False, regex=False)]
        if districts:
            result = result[result["district"].isin(districts)]
        if emergency_only:
            result = result[result["emergency"] == "Yes"]
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

    def component_scores(self, row, distance_km):
        return {
            "Distance": clamp100(100 - distance_km * 4),
            "ICU": clamp100(row["icu_beds"] * 5),
            "Emergency": yes_score(row["emergency"]),
            "Wheelchair": yes_score(row["wheelchair_access"]),
            "Ambulance": yes_score(row["ambulance"]),
            "Waiting time": clamp100(100 - row["avg_waiting_min"] * 0.8),
            "Rating": clamp100(row["rating"] / 5 * 100),
        }

    def weighted_score(self, components, weights):
        total = sum(weights.values())
        if total == 0:
            return 0.0
        return round(sum(components[name] * weights[name] for name in components) / total, 1)

    def statistics(self, frame):
        if frame.empty:
            return {"hospitals": 0, "avg_wait": np.nan, "median_rating": np.nan,
                    "icu_total": 0, "emergency_share": np.nan}
        return {
            "hospitals": len(frame),
            "avg_wait": frame["avg_waiting_min"].mean(),
            "median_rating": np.median(frame["rating"].dropna()) if frame["rating"].notna().any() else np.nan,
            "icu_total": frame["icu_beds"].sum(),
            "emergency_share": (frame["emergency"] == "Yes").mean() * 100,
        }

    def by_district(self, frame):
        return (
            frame.groupby("district")
            .agg(hospitals=("hospital_id", "count"), avg_rating=("rating", "mean"),
                 avg_waiting_min=("avg_waiting_min", "mean"), icu_beds=("icu_beds", "sum"))
            .round(2)
            .reset_index()
        )

    def report_text(self, frame, filters, strategy):
        lines = self.report_header("MedScope - Hospital Readiness Report", frame, filters)
        stats = self.statistics(frame)
        lines += [
            f"Missing-value rule: {strategy}",
            "",
            "Summary statistics",
            f"  - Hospitals: {stats['hospitals']}",
            f"  - Average waiting time: {stats['avg_wait']:.1f} min",
            f"  - Median rating: {stats['median_rating']:.2f}",
            f"  - Total ICU beds: {int(stats['icu_total'])}",
            f"  - Emergency service available: {stats['emergency_share']:.1f}%",
            "",
            "Average rating by district",
        ]
        for row in self.by_district(frame).itertuples():
            lines.append(f"  - {row.district}: {row.avg_rating:.2f} ({row.hospitals} hospitals)")
        return "\n".join(lines)


def records_tab(manager, shown, raw):
    section_title("Hospital records")
    stats = manager.statistics(shown)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Hospitals", stats["hospitals"], PRIMARY)
    with c2:
        kpi_card("Average waiting", f"{stats['avg_wait']:.1f} min", TEAL)
    with c3:
        kpi_card("Median rating", f"{stats['median_rating']:.2f}", AMBER)
    with c4:
        kpi_card("Total ICU beds", f"{int(stats['icu_total']):,}", VIOLET)
    st.write("")
    left, right = st.columns([2, 1])
    sort_column = left.selectbox("Sort by", manager.columns, key="sort_column")
    order = right.radio("Order", ["Ascending", "Descending"], horizontal=True, key="sort_order")
    table = manager.sort_records(raw, sort_column, order == "Ascending")
    st.dataframe(manager.display_frame(table), hide_index=True, width="stretch")
    st.caption(f"Showing {len(table)} of {manager.row_count} records. Empty cells are shown as blank.")
    section_title("Group-by summary")
    if shown.empty:
        st.info("No records to summarise.")
    else:
        st.dataframe(manager.by_district(shown), hide_index=True, width="stretch")


def analyzer_tab(manager, analysis):
    if analysis.empty:
        st.info("No hospitals are available for scoring with the current filters.")
        return
    section_title("1. Select a hospital and reference location")
    names = analysis["name"].tolist()
    c1, c2 = st.columns(2)
    hospital_name = c1.selectbox("Hospital", names, key="analyze_hospital")
    place = c2.selectbox("Reference location", list(REFERENCE_PLACES), key="analyze_place")
    hospital = analysis.loc[analysis["name"] == hospital_name].iloc[0]
    ref_lat, ref_lon = REFERENCE_PLACES[place]
    distance = float(haversine_km(ref_lat, ref_lon, hospital["latitude"], hospital["longitude"]))
    st.info(f"Straight-line distance: **{distance:.2f} km**")
    st.divider()
    section_title("2. Configure accessibility weights")
    st.caption("These weights are a transparent project model, not a medical or government standard. Totals are normalised automatically.")
    columns = st.columns(len(DEFAULT_WEIGHTS))
    weights = {}
    for column, (factor, default) in zip(columns, DEFAULT_WEIGHTS.items()):
        with column:
            weights[factor] = st.slider(factor, 0, 40, default, key=f"weight_{factor}")
    if sum(weights.values()) == 0:
        st.error("At least one weight must be greater than zero.")
        return
    components = manager.component_scores(hospital, distance)
    overall = manager.weighted_score(components, weights)
    total = sum(weights.values())
    st.divider()
    section_title("3. Explainable accessibility score")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Overall score", f"{overall}/100")
    k2.metric("Classification", score_label(overall))
    k3.metric("Distance", f"{distance:.2f} km")
    k4.metric("Rating", f"{hospital['rating']}/5")
    breakdown = pd.DataFrame({
        "Factor": list(components),
        "Raw score": [round(v, 1) for v in components.values()],
        "Weight": [weights[k] for k in components],
        "Contribution": [round(components[k] * weights[k] / total, 2) for k in components],
    })
    left, right = st.columns(2)
    with left:
        st.dataframe(breakdown, hide_index=True, width="stretch", height=300)
    with right:
        fig = px.bar(breakdown.sort_values("Contribution"), x="Contribution", y="Factor", orientation="h")
        fig.update_traces(marker_color=PRIMARY)
        st.plotly_chart(style_chart(fig, 300), width="stretch")
    st.divider()
    section_title("4. Compare hospitals with the same weights")
    chosen = st.multiselect("Hospitals to compare", names, default=names[:3], max_selections=6, key="compare_hospitals")
    rows = []
    for name in chosen:
        row = analysis.loc[analysis["name"] == name].iloc[0]
        d = float(haversine_km(ref_lat, ref_lon, row["latitude"], row["longitude"]))
        score = manager.weighted_score(manager.component_scores(row, d), weights)
        rows.append({"Hospital": name, "District": row["district"], "Distance (km)": round(d, 2),
                     "Score": score, "Class": score_label(score)})
    if rows:
        comparison = pd.DataFrame(rows).sort_values(["Score", "Distance (km)"], ascending=[False, True])
        st.dataframe(comparison, hide_index=True, width="stretch")
        fig = px.bar(comparison.sort_values("Score"), x="Score", y="Hospital", orientation="h",
                     color="Class", color_discrete_map=RATING_COLORS)
        st.plotly_chart(style_chart(fig, 320), width="stretch")
    st.download_button("Download score breakdown CSV", breakdown.to_csv(index=False).encode("utf-8"),
                       "score_breakdown.csv", "text/csv")


def add_tab(manager):
    section_title("Add a hospital")
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        record = {}
        record["hospital_id"] = c1.text_input("Hospital ID", value=manager.next_id(), key="add_id")
        record["name"] = c2.text_input("Hospital name", key="add_name")
        record["district"] = c1.selectbox("District", DISTRICTS, key="add_district")
        record["icu_beds"] = c2.number_input("ICU beds", 0, 1000, 10, key="add_icu")
        record["latitude"] = c1.number_input("Latitude", value=10.0, format="%.4f", key="add_lat")
        record["longitude"] = c2.number_input("Longitude", value=76.3, format="%.4f", key="add_lon")
        record["avg_waiting_min"] = c1.number_input("Average waiting time (min)", 0.0, 600.0, 30.0, key="add_wait")
        record["rating"] = c2.number_input("Rating (0-5)", 0.0, 5.0, 4.0, step=0.1, key="add_rating")
        record["emergency"] = c1.selectbox("Emergency service", YES_NO, key="add_emergency")
        record["wheelchair_access"] = c2.selectbox("Wheelchair access", YES_NO, key="add_wheelchair")
        record["ambulance"] = c1.selectbox("Ambulance", YES_NO, key="add_ambulance")
        submitted = st.form_submit_button("Add hospital")
    if submitted:
        ok, message = manager.create(record)
        flash("success" if ok else "error", message)
        st.rerun()


def edit_tab(manager):
    section_title("Edit a hospital")
    data = manager.data
    if data.empty:
        st.info("There are no records to edit.")
        return
    ids = data["hospital_id"].tolist()
    labels = dict(zip(data["hospital_id"], data["hospital_id"] + " - " + data["name"].fillna("(no name)")))
    record_id = st.selectbox("Choose a record", ids, format_func=labels.get, key="edit_pick")
    row = data.loc[data["hospital_id"] == record_id].iloc[0]
    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        changes = {}
        changes["name"] = c1.text_input("Hospital name", value=str(row["name"]), key=f"edit_name_{record_id}")
        district_options = DISTRICTS if row["district"] in DISTRICTS else DISTRICTS + [row["district"]]
        changes["district"] = c2.selectbox("District", district_options, index=choice_index(district_options, row["district"]), key=f"edit_district_{record_id}")
        changes["icu_beds"] = c1.number_input("ICU beds", 0, 1000, int(safe_number(row["icu_beds"], 0)), key=f"edit_icu_{record_id}")
        changes["rating"] = c2.number_input("Rating (0-5)", 0.0, 5.0, safe_number(row["rating"], 0.0), step=0.1, key=f"edit_rating_{record_id}")
        changes["latitude"] = c1.number_input("Latitude", value=safe_number(row["latitude"], 10.0), format="%.4f", key=f"edit_lat_{record_id}")
        changes["longitude"] = c2.number_input("Longitude", value=safe_number(row["longitude"], 76.3), format="%.4f", key=f"edit_lon_{record_id}")
        changes["avg_waiting_min"] = c1.number_input("Average waiting time (min)", 0.0, 600.0, safe_number(row["avg_waiting_min"], 0.0), key=f"edit_wait_{record_id}")
        changes["emergency"] = c2.selectbox("Emergency service", YES_NO, index=choice_index(YES_NO, row["emergency"]), key=f"edit_emergency_{record_id}")
        changes["wheelchair_access"] = c1.selectbox("Wheelchair access", YES_NO, index=choice_index(YES_NO, row["wheelchair_access"]), key=f"edit_wheelchair_{record_id}")
        changes["ambulance"] = c2.selectbox("Ambulance", YES_NO, index=choice_index(YES_NO, row["ambulance"]), key=f"edit_ambulance_{record_id}")
        submitted = st.form_submit_button("Save changes")
    if submitted:
        ok, message = manager.update(record_id, changes)
        flash("success" if ok else "error", message)
        st.rerun()


def delete_tab(manager):
    section_title("Delete a hospital")
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


def charts_tab(analysis):
    if analysis.empty:
        st.info("No data to chart with the current filters.")
        return
    left, right = st.columns(2)
    with left:
        section_title("Rating distribution")
        fig = px.histogram(analysis, x="rating", nbins=10, labels={"rating": "Rating"})
        fig.update_traces(marker_color=TEAL)
        st.plotly_chart(style_chart(fig), width="stretch")
    with right:
        section_title("Waiting time vs rating")
        fig = px.scatter(analysis, x="avg_waiting_min", y="rating", color="emergency",
                         size="icu_beds", hover_name="name",
                         labels={"avg_waiting_min": "Waiting time (min)", "rating": "Rating"})
        st.plotly_chart(style_chart(fig), width="stretch")


def report_tab(manager, shown, filters, strategy):
    section_title("Export a summary report")
    text = manager.report_text(shown, filters, strategy)
    st.code(text, language=None)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    c1, c2 = st.columns(2)
    c1.download_button("Download report (.txt)", text.encode("utf-8"), f"readiness_report_{stamp}.txt", "text/plain")
    c2.download_button("Download filtered data (.csv)", shown.to_csv(index=False).encode("utf-8"),
                       f"readiness_data_{stamp}.csv", "text/csv")


manager = ReadinessManager()
load_manager(manager)

hero(
    "Accessibility Analyzer",
    "Understand exactly how hospital accessibility is calculated. Adjust the importance of each "
    "factor, compare hospitals, and keep the readiness data up to date.",
)
show_flash()

st.sidebar.header("Filters")
search = st.sidebar.text_input("Search hospital name")
picked_districts = st.sidebar.multiselect("District", DISTRICTS)
emergency_only = st.sidebar.checkbox("Emergency service only")
strategy = st.sidebar.radio("Missing values", [EXCLUDE_ROWS, FILL_MEDIAN])

filters = {
    "Search": search,
    "Districts": ", ".join(picked_districts),
    "Emergency only": "Yes" if emergency_only else "",
}
raw = manager.search(search, picked_districts, emergency_only)
analysis = manager.apply_missing_strategy(raw, strategy)
missing_notice(manager, raw, strategy)

LABELS = ["Score Analyzer", "Records", "Add", "Edit", "Delete", "Charts", "Report"]
active = section_nav(LABELS)
if active == LABELS[0]:
    analyzer_tab(manager, analysis)
elif active == LABELS[1]:
    records_tab(manager, analysis, raw)
elif active == LABELS[2]:
    add_tab(manager)
elif active == LABELS[3]:
    edit_tab(manager)
elif active == LABELS[4]:
    delete_tab(manager)
elif active == LABELS[5]:
    charts_tab(analysis)
elif active == LABELS[6]:
    report_tab(manager, analysis, filters, strategy)

st.info(
    "This prototype is an accessibility information system. It does not diagnose, triage, or replace "
    "medical advice. The service fields are illustrative and should be verified before real use."
)
