"""OEE decomposition and downtime Pareto analysis (week 10)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config
from src.etl_pipeline import read_table
from src.kpi_framework import oee_components


def main():
    production = oee_components(read_table("production"))
    downtime = read_table("downtime")

    # OEE decomposition by line
    decomp = (production.groupby("line")[["availability", "performance", "quality", "oee"]]
              .mean() * 100).round(1)
    decomp.to_csv(config.REPORTS_DIR / "oee_decomposition.csv")
    print(decomp.to_string())

    fig, ax = plt.subplots(figsize=(9, 5))
    decomp[["availability", "performance", "quality"]].plot.bar(ax=ax)
    ax.set_ylabel("%"); ax.set_title("OEE component decomposition by line")
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "oee_decomposition.png", dpi=120)
    plt.close(fig)

    # downtime Pareto by total duration
    pareto = (downtime.groupby("cause_code")["duration_hrs"]
              .agg(["sum", "count"]).sort_values("sum", ascending=False))
    pareto["pct_hours"] = (100 * pareto["sum"] / pareto["sum"].sum()).round(1)
    pareto["cum_pct"] = pareto["pct_hours"].cumsum().round(1)
    pareto.to_csv(config.REPORTS_DIR / "downtime_pareto.csv")
    print(pareto.to_string())

    fig, ax1 = plt.subplots(figsize=(10, 5))
    pareto["sum"].plot.bar(ax=ax1, color="steelblue")
    ax1.set_ylabel("Total downtime hours")
    ax2 = ax1.twinx()
    ax2.plot(range(len(pareto)), pareto["cum_pct"], "o-", color="darkred")
    ax2.set_ylabel("Cumulative %"); ax2.set_ylim(0, 105)
    ax1.set_title("Downtime Pareto (by duration)")
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "downtime_pareto.png", dpi=120)
    plt.close(fig)

    # shift-level OEE controlled by line
    shift_oee = (production.groupby(["line", "shift"])["oee"].mean().unstack() * 100).round(1)
    shift_oee.to_csv(config.REPORTS_DIR / "shift_oee.csv")

    # Line 3 spindle bearing share of breakdown hours (week 11 RCA input)
    l3_bd = downtime[(downtime["line"] == "Line 3") &
                     (downtime["cause_detail"].str.contains("Spindle", na=False))]
    l3_all_bd = downtime[(downtime["line"] == "Line 3") &
                         (downtime["cause_code"] == "Breakdown")]
    if len(l3_all_bd):
        share = 100 * l3_bd["duration_hrs"].sum() / l3_all_bd["duration_hrs"].sum()
        print(f"  spindle bearing failures = {share:.0f}% of Line 3 breakdown hours")
    return decomp, pareto


if __name__ == "__main__":
    main()
