"""Star-schema export for Power BI (week 16): 1 fact table + 6 dimensions
(DimDate, DimMachine, DimLine, DimShift, DimMaterial, DimOperator)."""
import numpy as np
import pandas as pd

import config
from src.etl_pipeline import read_table
from src.kpi_framework import oee_components

EXPORT_DIR = config.OUTPUT_DIR / "powerbi_export"


def main():
    EXPORT_DIR.mkdir(exist_ok=True)
    production = oee_components(read_table("production"))
    rng = np.random.default_rng(config.RANDOM_SEED)

    dim_date = pd.DataFrame({"date": pd.date_range(config.PERIOD_START, config.PERIOD_END)})
    dim_date["date_key"] = dim_date["date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["weekday"] = dim_date["date"].dt.day_name()

    dim_line = pd.DataFrame({"line_key": range(1, 5), "line": config.LINES})
    dim_shift = pd.DataFrame({"shift_key": range(1, 4), "shift": config.SHIFTS})
    dim_material = pd.DataFrame({"material_key": range(1, 4),
                                 "material_grade": config.MATERIAL_GRADES})
    machines = sorted(production["machine_id"].unique())
    dim_machine = pd.DataFrame({"machine_key": range(1, len(machines) + 1),
                                "machine_id": machines})
    operators = [f"OP{i:03d}" for i in range(1, 25)]
    dim_operator = pd.DataFrame({"operator_key": range(1, 25), "operator_id": operators})

    fact = production.copy()
    fact["date_key"] = fact["date"].dt.strftime("%Y%m%d").astype(int)
    fact = (fact.merge(dim_line, on="line").merge(dim_shift, on="shift")
            .merge(dim_material, on="material_grade")
            .merge(dim_machine, on="machine_id"))
    fact["operator_key"] = rng.integers(1, 25, len(fact))
    fact = fact[["order_id", "date_key", "line_key", "shift_key", "material_key",
                 "machine_key", "operator_key", "units_produced", "defect_count",
                 "run_time_hrs", "planned_time_hrs", "availability",
                 "performance", "quality", "oee"]]

    tables = {"FactProduction": fact, "DimDate": dim_date, "DimLine": dim_line,
              "DimShift": dim_shift, "DimMaterial": dim_material,
              "DimMachine": dim_machine, "DimOperator": dim_operator}
    for name, df in tables.items():
        df.to_csv(EXPORT_DIR / f"{name}.csv", index=False)
    print(f"  star schema exported: {', '.join(tables)} -> {EXPORT_DIR}")
    return tables


if __name__ == "__main__":
    main()
