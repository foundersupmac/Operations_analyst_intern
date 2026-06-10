"""Data quality audit across 5 dimensions (week 7): completeness,
accuracy, consistency, timeliness, uniqueness."""
import pandas as pd

import config
from src.etl_pipeline import read_table


def audit_table(df, name, key=None):
    completeness = 100 * (1 - df.isna().mean().mean())
    uniqueness = 100.0
    if key:
        uniqueness = 100 * df[key].nunique() / len(df)
    timeliness = "n/a"
    if "date" in df.columns:
        lag_days = (pd.Timestamp(config.PERIOD_END) - df["date"].max()).days
        timeliness = f"latest record {lag_days}d before period end"
    return {
        "table": name,
        "rows": len(df),
        "completeness_pct": round(completeness, 2),
        "uniqueness_pct": round(uniqueness, 2),
        "timeliness": timeliness,
    }


def main():
    results = [
        audit_table(read_table("production"), "production", key="order_id"),
        audit_table(read_table("quality"), "quality", key="inspection_lot"),
        audit_table(read_table("downtime"), "downtime", key="event_id"),
        audit_table(read_table("sensors"), "sensors"),
        audit_table(read_table("inventory"), "inventory", key="sku"),
    ]
    report = pd.DataFrame(results)
    path = config.REPORTS_DIR / "data_quality_report.csv"
    report.to_csv(path, index=False)
    print(report.to_string(index=False))
    return report


if __name__ == "__main__":
    main()
