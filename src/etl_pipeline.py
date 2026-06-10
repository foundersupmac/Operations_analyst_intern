"""ETL pipeline v1.0 (weeks 5-6): Extract -> Validate -> Clean -> Load -> Log.

Reads the raw CSV extracts, enforces schemas, applies the week-7 cleaning
rules and loads validated tables into SQLite (data/operations.db).
"""
import sqlite3

import numpy as np
import pandas as pd

import config

SCHEMAS = {
    "production": {
        "required": ["order_id", "date", "line", "machine_id", "shift",
                     "material_grade", "machine_speed", "planned_time_hrs",
                     "run_time_hrs", "units_produced", "defect_count"],
        "numeric": ["machine_speed", "planned_time_hrs", "run_time_hrs",
                    "units_produced", "defect_count"],
    },
    "quality": {
        "required": ["inspection_lot", "order_id", "date", "line", "shift",
                     "sample_size", "defects_found", "usage_decision", "plant_unit"],
        "numeric": ["sample_size", "defects_found"],
    },
    "downtime": {
        "required": ["event_id", "date", "line", "shift", "cause_code",
                     "cause_detail", "duration_hrs"],
        "numeric": ["duration_hrs"],
    },
    "sensors": {
        "required": ["date", "machine_id", "vibration_mm_s", "temperature_c",
                     "current_a", "cycle_count", "days_since_maintenance",
                     "failure_within_72h"],
        "numeric": ["vibration_mm_s", "temperature_c", "current_a",
                    "cycle_count", "days_since_maintenance"],
    },
    "inventory": {
        "required": ["sku", "annual_demand_units", "demand_std_daily",
                     "unit_cost_inr", "ordering_cost_inr", "holding_cost_pct",
                     "lead_time_days", "current_stock_units"],
        "numeric": ["annual_demand_units", "unit_cost_inr", "lead_time_days"],
    },
    "demand_history": {
        "required": ["date", "demand_units"],
        "numeric": ["demand_units"],
    },
}


def extract(table):
    return pd.read_csv(config.DATA_DIR / f"{table}.csv")


def validate(df, table, log):
    schema = SCHEMAS[table]
    missing_cols = set(schema["required"]) - set(df.columns)
    if missing_cols:
        raise ValueError(f"{table}: missing columns {missing_cols}")
    for col in schema["numeric"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    nulls = df[schema["required"]].isna().sum()
    log.append(f"{table}: {len(df):,} rows extracted; "
               f"null counts: {nulls[nulls > 0].to_dict() or 'none'}")
    return df


def clean_production(df, log):
    before = len(df)
    df = df.drop_duplicates(subset="order_id", keep="first")
    log.append(f"production: removed {before - len(df)} duplicate order IDs")

    # unify mixed date formats (DD/MM/YYYY from SAP export)
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")

    # normalise shift labels ('shift b' -> 'B')
    df["shift"] = (df["shift"].str.replace("shift", "", case=False)
                   .str.strip().str.upper())

    # median imputation for the 5 missing defect counts (domain-approved)
    n_miss = int(df["defect_count"].isna().sum())
    df["defect_count"] = df["defect_count"].fillna(df["defect_count"].median())
    log.append(f"production: median-imputed {n_miss} missing defect counts")

    # IQR outlier removal on machine speed
    q1, q3 = df["machine_speed"].quantile([0.25, 0.75])
    iqr = q3 - q1
    mask = df["machine_speed"].between(q1 - 3 * iqr, q3 + 3 * iqr)
    log.append(f"production: removed {int((~mask).sum())} IQR speed outliers")
    return df[mask].reset_index(drop=True)


def clean_quality(df, log):
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
    df["shift"] = (df["shift"].str.replace("shift", "", case=False)
                   .str.strip().str.upper())
    # label normalisation: 'Unit A' -> 'A'
    df["plant_unit"] = df["plant_unit"].str.replace("Unit ", "", regex=False)
    log.append("quality: normalised plant_unit labels and shift codes")
    return df


def clean_downtime(df, log):
    df["date"] = pd.to_datetime(df["date"])
    n_miss = int(df["cause_code"].isna().sum())
    df["cause_code"] = df["cause_code"].fillna("Uncoded")
    n_dur = int(df["duration_hrs"].isna().sum())
    df["duration_hrs"] = df["duration_hrs"].fillna(df["duration_hrs"].mean())
    log.append(f"downtime: {n_miss} missing cause codes flagged 'Uncoded' "
               f"({n_miss / len(df):.0%}); mean-imputed {n_dur} durations")
    return df


def load(tables, log):
    with sqlite3.connect(config.DB_PATH) as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, if_exists="replace", index=False)
            log.append(f"loaded {name}: {len(df):,} rows -> SQLite")


def read_table(name):
    """Convenience accessor used by all downstream analytics modules."""
    with sqlite3.connect(config.DB_PATH) as conn:
        df = pd.read_sql(f"SELECT * FROM {name}", conn)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def main():
    log = []
    tables = {}
    cleaners = {"production": clean_production, "quality": clean_quality,
                "downtime": clean_downtime}
    for table in SCHEMAS:
        df = validate(extract(table), table, log)
        if table in cleaners:
            df = cleaners[table](df, log)
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        tables[table] = df
    load(tables, log)

    log_path = config.REPORTS_DIR / "etl_log.txt"
    log_path.write_text("\n".join(log) + "\n")
    print("\n".join(f"  {line}" for line in log))
    return tables


if __name__ == "__main__":
    main()
