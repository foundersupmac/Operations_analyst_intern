"""End-to-end orchestration: generate data, run ETL and every analytics
module in dependency order."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import (data_generation, etl_pipeline, data_quality, kpi_framework,
                 eda, time_series, oee_analysis, statistical_models,
                 inventory, simulation, forecasting, pdm_model,
                 star_schema, excel_report)

STEPS = [
    ("1. Synthetic data generation", data_generation),
    ("2. ETL pipeline (validate/clean/load)", etl_pipeline),
    ("3. Data quality audit", data_quality),
    ("4. KPI baseline (12 KPIs)", kpi_framework),
    ("5. Exploratory data analysis", eda),
    ("6. Time-series analysis (STL/ADF/OEE trends)", time_series),
    ("7. OEE decomposition & downtime Pareto", oee_analysis),
    ("8. Regression & ANOVA", statistical_models),
    ("9. Inventory EOQ / safety stock", inventory),
    ("10. Line 3 simulation (Monte Carlo scenarios)", simulation),
    ("11. Demand forecasting (XGBoost vs SARIMA)", forecasting),
    ("12. Predictive maintenance model", pdm_model),
    ("13. Star schema export (Power BI)", star_schema),
    ("14. Weekly Excel report", excel_report),
]


def main():
    for title, module in STEPS:
        print(f"\n=== {title} ===")
        module.main()
    print("\nPipeline complete. Outputs in ./output, database in ./data/operations.db")


if __name__ == "__main__":
    main()
