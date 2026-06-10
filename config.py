"""Central configuration for the operations analytics project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
MODELS_DIR = OUTPUT_DIR / "models"
REPORTS_DIR = OUTPUT_DIR / "reports"
DB_PATH = DATA_DIR / "operations.db"

for _d in (DATA_DIR, CHARTS_DIR, MODELS_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 42

# Plant structure
LINES = ["Line 1", "Line 2", "Line 3", "Line 4"]
SHIFTS = ["A", "B", "C"]
MACHINES_PER_LINE = 3
MATERIAL_GRADES = ["Grade-1", "Grade-2", "Grade-3"]

# 12-month analysis window (matches the SAP extract described in week 5)
PERIOD_START = "2025-02-01"
PERIOD_END = "2026-01-31"

# Production parameters
IDEAL_CYCLE_TIME_MIN = 0.5          # minutes per unit
SHIFT_HOURS = 8.0
N_SKUS = 120

# Downtime cause-code hierarchy (week 10 classification)
DOWNTIME_CATEGORIES = [
    "Breakdown", "Changeover", "Material Shortage",
    "Planned Maintenance", "Quality Stop", "Minor Stop",
]

# KPI targets and industry benchmarks (week 8 workshop)
KPI_TARGETS = {
    "OEE (%)": {"target": 75.0, "benchmark": 85.0},
    "Availability (%)": {"target": 88.0, "benchmark": 90.0},
    "Performance (%)": {"target": 92.0, "benchmark": 95.0},
    "First-Pass Yield (%)": {"target": 96.0, "benchmark": 99.0},
    "Defect Rate (%)": {"target": 2.0, "benchmark": 1.0},
    "MTTR (hrs)": {"target": 1.5, "benchmark": 1.0},
    "MTBF (hrs)": {"target": 120.0, "benchmark": 200.0},
    "On-Time Delivery (%)": {"target": 95.0, "benchmark": 98.0},
    "Changeover Time (min)": {"target": 30.0, "benchmark": 22.0},
    "Inventory Turnover (x/yr)": {"target": 8.0, "benchmark": 12.0},
    "Schedule Adherence (%)": {"target": 90.0, "benchmark": 95.0},
    "PM Compliance (%)": {"target": 95.0, "benchmark": 98.0},
}
