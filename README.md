# MedScope - Hospital Accessibility Management System

A four-page Streamlit project that studies how accessible hospitals are across Kerala districts.
Every team member owns one CSV file and one page, and each page supports adding, viewing, editing,
deleting, charting and exporting data for that CSV.

Data flow: **Input data → Update CSV → Read / Analyze / View → Visualize**

## Who owns what

| Student | Page | CSV file |
|---|---|---|
| Amala B | `pages/1_Analyzer.py` | `data/hospital_readiness.csv` |
| Megha S | `pages/2_Map_Explorer.py` | `data/hospital_locations.csv` |
| Aiswarya S | `pages/3_District_Analytics.py` | `data/district_profiles.csv` |
| Theertha A | `pages/4_Hospital_Finder.py` | `data/hospital_directory.csv` |

Each page reads and writes only its own CSV. `Home.py` is the landing page and does not touch any CSV.

## Project structure

```text
MedScope/
├── Home.py
├── csv_manager.py
├── utils.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml
├── data/
│   ├── hospital_readiness.csv
│   ├── hospital_locations.csv
│   ├── district_profiles.csv
│   └── hospital_directory.csv
└── pages/
    ├── 1_Analyzer.py
    ├── 2_Map_Explorer.py
    ├── 3_District_Analytics.py
    └── 4_Hospital_Finder.py
```

## Setup

Python 3.10 or newer is required.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run Home.py
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run Home.py
```

## What every page does

| Requirement | How it is done |
|---|---|
| Create | Form with validation of required fields, types and ranges, plus duplicate checks (matching ID or same name in the same district) |
| Read | Sidebar search and filters, sort by any column, summary statistics and a group-by table |
| Update | Pick a record by ID, edit its fields, and the change is written back to the CSV |
| Delete | Pick a record, tick "Yes, delete this record", then press Delete |
| Visualization | At least two chart types per page, built from the current CSV and sidebar filters |
| Missing data | Sidebar option to exclude rows or fill numbers with the median, with the chosen rule shown on the page |
| Report | Download a text report (Finder also offers PDF) with timestamp, row count and applied filters, plus the filtered CSV |
| Robustness | Missing file, empty file, wrong column types, invalid ID and duplicate entries all give friendly messages instead of a traceback |

## Code design

- `csv_manager.py` holds the shared base class `CSVManager`. It keeps the table in a protected
  `_data` attribute exposed through a read-only `data` property, and provides loading, type cleaning,
  ID helpers, validation helpers and saving.
- Every read and write uses `try / except / else / finally`.
- Saves are atomic: rows are written to a temporary file, checked by reading it back, and only then
  swapped in with `os.replace`, so the CSV is never left half-written.
- Each page defines its own manager class that extends `CSVManager`: `ReadinessManager`,
  `LocationManager`, `DistrictManager` and `DirectoryManager`. The methods (`create`, `search`,
  `update`, `delete`, `statistics`, `report_text`) return values instead of printing.
- Each page loads its CSV fresh every time it runs, with no caching.
- All paths are relative to the project root.

## Accessibility scoring

### Hospital readiness score (Analyzer, default weights)

| Factor | Weight |
|---|---:|
| Distance | 25% |
| ICU capacity | 15% |
| Emergency | 20% |
| Wheelchair access | 15% |
| Ambulance | 15% |
| Waiting time | 5% |
| Rating | 5% |

The weights can be changed with sliders on the page and are normalised automatically.

### Hospital match score (Finder)

| Factor | Weight |
|---|---:|
| Distance | 60% |
| Pharmacy + Laboratory + Blood Bank | 30% |
| Opening hours | 10% |

### District score (District Analytics)

| Factor | Weight |
|---|---:|
| Nearest hospital distance | 30% |
| Beds per 100,000 population | 30% |
| ICU beds per 100,000 | 10% |
| Service coverage | 20% |
| Average waiting time | 5% |
| Average rating | 5% |

Classification: **Good** 75-100, **Moderate** 50-74.9, **Poor** below 50.

Distances use the Haversine formula, which is straight-line distance and not road travel time.

## Dataset note

Hospital names, districts, coordinates and bed counts come from the original project. The added
service and operational fields are illustrative demonstration data, not verified hospital records.
District figures in `district_profiles.csv` were calculated from the hospital data using a 25 km
radius around each district centre, with populations from the 2011 census values in the project.

## Screenshots and demo video

- Demo video: add link here
- Screenshots: add images to a `screenshots/` folder and list them here
