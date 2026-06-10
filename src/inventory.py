"""Inventory analytics (week 14): EOQ (Wilson formula), safety stock at
95% service level and reorder points for all 120 SKUs."""
import numpy as np
import pandas as pd

import config
from src.etl_pipeline import read_table

Z_95 = 1.645


def main():
    inv = read_table("inventory")
    d_daily = inv["annual_demand_units"] / 365
    holding = inv["unit_cost_inr"] * inv["holding_cost_pct"]

    inv["eoq_units"] = np.sqrt(
        2 * inv["annual_demand_units"] * inv["ordering_cost_inr"] / holding).round(0)
    inv["safety_stock"] = (Z_95 * inv["demand_std_daily"] *
                           np.sqrt(inv["lead_time_days"])).round(0)
    inv["reorder_point"] = (d_daily * inv["lead_time_days"] +
                            inv["safety_stock"]).round(0)
    inv["days_of_supply"] = (inv["current_stock_units"] / d_daily).round(1)

    overstocked = inv[inv["days_of_supply"] > 90]
    excess_value = ((overstocked["current_stock_units"] -
                     90 * overstocked["annual_demand_units"] / 365) *
                    overstocked["unit_cost_inr"]).sum()
    stockout_risk = inv[inv["current_stock_units"] < inv["safety_stock"]]

    inv["action"] = "OK"
    inv.loc[overstocked.index, "action"] = "REDUCE (>90d supply)"
    inv.loc[stockout_risk.index, "action"] = "URGENT REORDER"

    inv.to_csv(config.REPORTS_DIR / "inventory_eoq_analysis.csv", index=False)
    print(f"  {len(overstocked)} SKUs overstocked beyond 90-day supply "
          f"(excess value Rs {excess_value / 1e5:.1f} lakh)")
    print(f"  {len(stockout_risk)} SKUs below safety stock (stockout risk)")
    return inv


if __name__ == "__main__":
    main()
