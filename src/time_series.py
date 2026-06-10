"""Time-series analysis (week 9): rolling averages, STL decomposition,
ADF stationarity tests and daily OEE trends per line."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller

import config
from src.etl_pipeline import read_table
from src.kpi_framework import oee_components


def adf_report(series, name):
    stat, pvalue = adfuller(series.dropna())[:2]
    verdict = "stationary" if pvalue < 0.05 else "non-stationary"
    print(f"  ADF {name}: stat={stat:.2f}, p={pvalue:.3f} -> {verdict}")
    return pvalue


def main():
    production = oee_components(read_table("production"))
    daily_output = production.groupby("date")["units_produced"].sum()

    # rolling averages
    fig, ax = plt.subplots(figsize=(13, 4))
    daily_output.plot(ax=ax, lw=0.6, alpha=0.6, label="daily")
    daily_output.rolling(7).mean().plot(ax=ax, lw=1.5, label="7-day")
    daily_output.rolling(28).mean().plot(ax=ax, lw=2, label="28-day")
    ax.legend(); ax.set_title("Throughput with rolling averages")
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "throughput_rolling.png", dpi=120)
    plt.close(fig)

    # STL decomposition (weekly seasonality)
    stl = STL(daily_output, period=7).fit()
    fig = stl.plot()
    fig.set_size_inches(11, 8)
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "stl_decomposition.png", dpi=120)
    plt.close(fig)

    # stationarity: level vs first difference
    adf_report(daily_output, "throughput (level)")
    adf_report(daily_output.diff(), "throughput (1st diff)")

    # daily OEE per line with 28-day rolling average
    daily_oee = production.groupby(["date", "line"])["oee"].mean().unstack() * 100
    fig, ax = plt.subplots(figsize=(13, 5))
    for line in config.LINES:
        daily_oee[line].rolling(28).mean().plot(ax=ax, lw=2, label=line)
    ax.axhline(65, color="red", ls="--", lw=1, label="65% threshold")
    ax.set_ylabel("OEE % (28-day rolling)")
    ax.set_title("OEE trend by production line")
    ax.legend()
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "oee_trends.png", dpi=120)
    plt.close(fig)

    recent = daily_oee.loc["2025-09-01":].mean().round(1)
    print(f"  mean OEE since Sep 2025 by line: {recent.to_dict()}")
    return daily_oee


if __name__ == "__main__":
    main()
