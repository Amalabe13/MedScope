import os
import tempfile
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
EXCLUDE_ROWS = "Exclude rows with missing values"
FILL_MEDIAN = "Fill missing numbers with the column median"


class CSVManager:
    def __init__(self, file_name, columns, id_column, id_prefix, numeric_columns=(),
                 integer_columns=(), yes_no_columns=(), id_width=3):
        self.path = DATA_DIR / file_name
        self.columns = list(columns)
        self.id_column = id_column
        self.id_prefix = id_prefix
        self.id_width = id_width
        self.numeric_columns = list(numeric_columns)
        self.integer_columns = list(integer_columns)
        self.yes_no_columns = list(yes_no_columns)
        self.text_columns = [
            c for c in self.columns
            if c not in self.numeric_columns and c not in self.yes_no_columns
        ]
        self._data = pd.DataFrame(columns=self.columns)
        self.warnings = []
        self.problem = None
        self.last_loaded = None

    @property
    def data(self):
        return self._data.copy()

    @property
    def row_count(self):
        return len(self._data)

    def load(self):
        self.warnings = []
        self.problem = None
        try:
            frame = pd.read_csv(self.path)
        except FileNotFoundError:
            self.problem = "missing"
            return False, f"The file {self.path.name} was not found in the data folder."
        except pd.errors.EmptyDataError:
            self.problem = "empty"
            return False, f"The file {self.path.name} is empty."
        except (pd.errors.ParserError, UnicodeDecodeError, PermissionError, OSError) as error:
            self.problem = "unreadable"
            return False, f"The file {self.path.name} could not be read: {error}"
        else:
            absent = [c for c in self.columns if c not in frame.columns]
            if absent:
                self.problem = "columns"
                return False, f"{self.path.name} is missing these columns: {', '.join(absent)}."
            self._data = self.fix_types(frame[self.columns])
            return True, f"Loaded {len(self._data)} rows from {self.path.name}."
        finally:
            self.last_loaded = datetime.now()

    def fix_types(self, frame):
        frame = frame.copy()
        for column in self.text_columns:
            cleaned = frame[column].astype(str).str.strip()
            frame[column] = cleaned.where(frame[column].notna() & (cleaned != ""), np.nan)
        for column in self.numeric_columns:
            converted = pd.to_numeric(frame[column], errors="coerce")
            wrong = int((converted.isna() & frame[column].notna()).sum())
            if wrong:
                self.warnings.append(
                    f"{wrong} value(s) in '{column}' are not numbers and were treated as missing."
                )
            frame[column] = converted
        for column in self.yes_no_columns:
            cleaned = frame[column].astype(str).str.strip().str.title()
            valid = cleaned.isin(["Yes", "No"])
            wrong = int((~valid & frame[column].notna()).sum())
            if wrong:
                self.warnings.append(
                    f"{wrong} value(s) in '{column}' are not Yes/No and were treated as missing."
                )
            frame[column] = cleaned.where(valid, np.nan)
        return frame.reset_index(drop=True)

    def save(self, frame):
        temp_name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            output = frame[self.columns].copy()
            for column in self.integer_columns:
                output[column] = pd.to_numeric(output[column], errors="coerce").round().astype("Int64")
            with tempfile.NamedTemporaryFile(
                "w", suffix=".tmp", dir=self.path.parent, delete=False, newline="", encoding="utf-8"
            ) as handle:
                temp_name = handle.name
                output.to_csv(handle, index=False)
            pd.read_csv(temp_name)
            os.replace(temp_name, self.path)
        except (OSError, ValueError) as error:
            return False, f"The change could not be saved, so the file was left untouched. ({error})"
        else:
            self._data = self.fix_types(output)
            return True, "Saved."
        finally:
            if temp_name and os.path.exists(temp_name):
                os.remove(temp_name)

    def create_empty(self):
        return self.save(pd.DataFrame(columns=self.columns))

    def next_id(self):
        numbers = pd.to_numeric(
            self._data[self.id_column].astype(str).str.extract(r"(\d+)$")[0], errors="coerce"
        )
        highest = int(numbers.max()) if numbers.notna().any() else 0
        return f"{self.id_prefix}{highest + 1:0{self.id_width}d}"

    def find_position(self, record_id):
        wanted = str(record_id).strip().upper()
        matches = self._data.index[self._data[self.id_column].str.upper() == wanted]
        return int(matches[0]) if len(matches) else None

    def id_exists(self, record_id):
        return self.find_position(record_id) is not None

    def tidy(self, record):
        cleaned = {}
        for key, value in record.items():
            cleaned[key] = value.strip() if isinstance(value, str) else value
        cleaned[self.id_column] = str(cleaned[self.id_column]).upper()
        return cleaned

    def name_taken(self, name, district, skip_position=None):
        same = (
            (self._data["name"].str.lower() == str(name).strip().lower())
            & (self._data["district"].str.lower() == str(district).strip().lower())
        )
        if skip_position is not None:
            same = same & (self._data.index != skip_position)
        return bool(same.any())

    def check_required(self, record, fields):
        errors = []
        for field in fields:
            if str(record.get(field, "")).strip() in ("", "nan", "None"):
                errors.append(f"{self.label(field)} is required.")
        return errors

    def check_number(self, record, field, low, high, whole=False):
        try:
            value = float(record.get(field))
        except (TypeError, ValueError):
            return [f"{self.label(field)} must be a number."]
        if np.isnan(value):
            return [f"{self.label(field)} must be a number."]
        if whole and value != int(value):
            return [f"{self.label(field)} must be a whole number."]
        if not low <= value <= high:
            return [f"{self.label(field)} must be between {low} and {high}."]
        return []

    def check_choice(self, record, field, options):
        if record.get(field) not in options:
            return [f"{self.label(field)} must be one of: {', '.join(options)}."]
        return []

    def label(self, field):
        return field.replace("_", " ").title()

    def sort_records(self, frame, column, ascending=True):
        if column in frame.columns:
            return frame.sort_values(column, ascending=ascending, na_position="last")
        return frame

    def display_frame(self, frame):
        shown = frame.copy()
        for column in self.integer_columns:
            if column in shown.columns:
                shown[column] = pd.to_numeric(shown[column], errors="coerce").round().astype("Int64")
        return shown

    def count_missing(self, frame):
        return int(frame[self.columns].isna().sum().sum())

    def apply_missing_strategy(self, frame, strategy):
        cleaned = frame.copy()
        if strategy == FILL_MEDIAN:
            for column in self.numeric_columns:
                if column in cleaned.columns:
                    cleaned[column] = cleaned[column].fillna(cleaned[column].median())
            return cleaned
        return cleaned.dropna(subset=[c for c in self.numeric_columns if c in cleaned.columns])

    def report_header(self, title, shown, filters):
        lines = [
            title,
            "=" * len(title),
            f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Source file: {self.path.name}",
            f"Rows in file: {self.row_count}",
            f"Rows in this report: {len(shown)}",
            "Filters applied:",
        ]
        active = {key: value for key, value in filters.items() if value}
        if active:
            lines += [f"  - {key}: {value}" for key, value in active.items()]
        else:
            lines.append("  - None")
        return lines
