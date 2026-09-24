# Hospital Accessibility Management System

Streamlit project for analysing hospital
accessibility across Kerala districts.

## What the project does

The application combines:

- hospital location
- hospital type
- available beds and ICU beds
- emergency service
- wheelchair accessibility
- ambulance availability
- pharmacy
- laboratory
- blood bank
- specialist doctor
- average waiting time
- opening hours
- rating
- district population

into an interactive accessibility management dashboard.


## Project structure

```text
hospital_accessibility_analyzer/
├── About.py
├── utils.py
├── requirements.txt
├── README.md
├── PROJECT_GUIDE.md
├── .streamlit/
│   └── config.toml
├── data/
│   ├── hospitals.csv
│   └── districts.csv
└── pages/
    ├── 1_Analyzer.py
    ├── 2_Map_Explorer.py
    ├── 3_District_Analytics.py
    └── 4_Hospital_Finder.py
```

## Setup on Windows

Open the project folder in VS Code:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run About.py
```

If PowerShell blocks activation, you can run Streamlit directly through the
virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run About.py
```

## Accessibility scoring

### Hospital score

| Factor | Weight |
|---|---:|
| Distance | 20% |
| Bed capacity | 10% |
| ICU capacity | 10% |
| Emergency | 15% |
| Wheelchair access | 10% |
| Ambulance | 10% |
| Pharmacy + Laboratory + Blood Bank | 10% |
| Specialist availability | 10% |
| Waiting time | 3% |
| Rating | 2% |

### District score

| Factor | Weight |
|---|---:|
| Nearest hospital distance | 30% |
| Beds per 100,000 population | 30% |
| ICU beds per 100,000 | 10% |
| Service coverage | 20% |
| Average waiting time | 5% |
| Average rating | 5% |

Classification:

- **Good:** 75–100
- **Moderate:** 50–74.9
- **Poor:** below 50

The weights are transparent and editable in `utils.py`.

## Algorithms

### Haversine distance

The system calculates straight-line geographic distance between two latitude /
longitude points. This is useful for accessibility analysis but is **not the
same as road travel distance or travel time**.

### Filtering

The Hospital Finder applies patient requirements such as:

- specialist
- emergency
- wheelchair access
- ambulance
- pharmacy
- laboratory
- blood bank
- minimum beds
- maximum distance

### Ranking

Matching hospitals are ranked using the explainable hospital accessibility
score, with distance used as a secondary ordering factor.

## Dataset note

The original project hospital names, districts, coordinates and bed counts are
retained from the uploaded project.

The additional service/operational fields were added to make the prototype
demonstrate the full accessibility workflow. **Those added values are
illustrative demonstration data, not verified live hospital records.** Replace
them with official or institutionally verified data before using the system for
real-world healthcare decisions.

District populations are from the existing project dataset and are labelled as
2011 population values.


## Future improvements

- Replace straight-line distance with road travel time using a routing service.
- Use verified government/hospital registry data.
- Add real-time bed availability.
- Add authentication and role-based access.
- Store data in SQLite/PostgreSQL instead of CSV.
- Add ambulance ETA and emergency response time.
- Add route visualization.
- Add machine-learning recommendations after collecting reliable historical data.
