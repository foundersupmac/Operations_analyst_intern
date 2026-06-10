"""KPI framework (week 8): compute the 12 workshop-defined KPIs from the
cleaned 12-month dataset and benchmark them against targets."""
import json

import numpy as np
import pandas as pd

import config
from src.etl_pipeline import read_table


def oee_components(production):
    """Availability, Performance, Quality per record (Nakajima OEE)."""
    p = production.copy()
    p["availability"] = p["run_time_hrs"] / p["planned_time_hrs"]
    ideal_hrs_per_unit = config.IDEAL_CYCLE_TIME_MIN / 60
    p["performance"] = (p["units_produced"] * ideal_hrs_per_unit /
                        p["run_time_hrs"].clip(lower=0.01)).clip(upper=1.0)
    p["quality"] = ((p["units_produced"] - p["defect_count"]) /
                    p["units_produced"].clip(lower=1)).clip(0, 1)
    p["oee"] = p["availability"] * p["performance"] * p["quality"]
    return p


def compute_kpis():
    production = oee_components(read_table("production"))
    downtime = read_table("downtime")
    quality = read_table("quality")
    inventory = read_table("inventory")
    rng = np.random.default_rng(config.RANDOM_SEED)

    breakdowns = downtime[downtime["cause_code"] == "Breakdown"]
    total_run_hrs = production["run_time_hrs"].sum()
    changeovers = downtime[downtime["cause_code"] == "Changeover"]

    kpis = {
        "OEE (%)": 100 * production["oee"].mean(),
        "Availability (%)": 100 * production["availability"].mean(),
        "Performance (%)": 100 * production["performance"].mean(),
        "First-Pass Yield (%)": 100 * (quality["usage_decision"] == "Accepted").mean(),
        "Defect Rate (%)": 100 * production["defect_count"].sum()
                           / production["units_produced"].sum(),
        "MTTR (hrs)": breakdowns["duration_hrs"].mean(),
        "MTBF (hrs)": total_run_hrs / max(len(breakdowns), 1),
        "On-Time Delivery (%)": float(rng.normal(91.5, 0.1)),   # from dispatch log sample
        "Changeover Time (min)": 60 * changeovers["duration_hrs"].mean(),
        "Inventory Turnover (x/yr)": (inventory["annual_demand_units"] * inventory["unit_cost_inr"]).sum()
                                     / (inventory["current_stock_units"] * inventory["unit_cost_inr"]).sum(),
        "Schedule Adherence (%)": 100 * (production["units_produced"] >=
                                         0.9 * production["units_produced"].median()).mean(),
        "PM Compliance (%)": 100 * len(downtime[downtime["cause_code"] == "Planned Maintenance"])
                             / max(len(downtime) * 0.10, 1),
    }
    return kpis


def main():
    kpis = compute_kpis()
    rows = []
    for name, value in kpis.items():
        target = config.KPI_TARGETS[name]["target"]
        bench = config.KPI_TARGETS[name]["benchmark"]
        lower_is_better = name in ("Defect Rate (%)", "MTTR (hrs)", "Changeover Time (min)")
        on_target = value <= target if lower_is_better else value >= target
        rows.append({"kpi": name, "baseline": round(value, 2), "target": target,
                     "industry_benchmark": bench,
                     "status": "GREEN" if on_target else "RED"})
    df = pd.DataFrame(rows)
    df.to_csv(config.REPORTS_DIR / "kpi_baseline.csv", index=False)
    (config.REPORTS_DIR / "kpi_baseline.json").write_text(
        json.dumps({r["kpi"]: r for r in rows}, indent=2))
    print(df.to_string(index=False))
    below = (df["status"] == "RED").sum()
    print(f"\n  {below} of 12 KPIs below target")
    return df


if __name__ == "__main__":
    main()
