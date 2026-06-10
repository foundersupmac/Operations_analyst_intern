"""Exploratory data analysis (week 6): profiling, distributions,
time-series view and correlation analysis."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy import stats

import config
from src.etl_pipeline import read_table


def main():
    production = read_table("production")

    # descriptive statistics for all numeric fields
    profile = production.describe().T.round(2)
    profile.to_csv(config.REPORTS_DIR / "eda_profile.csv")

    # distribution: throughput per line (Line 2 bimodality post-firmware)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, line in zip(axes.flat, config.LINES):
        sns.histplot(production.loc[production["line"] == line, "machine_speed"],
                     kde=True, ax=ax, bins=40)
        ax.set_title(f"{line} machine speed distribution")
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "speed_distributions.png", dpi=120)
    plt.close(fig)

    # 12-month daily production output (Aug-Sep shutdown dip)
    daily = production.groupby("date")["units_produced"].sum()
    fig, ax = plt.subplots(figsize=(13, 4))
    daily.plot(ax=ax, lw=0.8)
    daily.rolling(7).mean().plot(ax=ax, lw=2, label="7-day avg")
    ax.set_title("Daily production output (12 months)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "daily_output.png", dpi=120)
    plt.close(fig)

    # correlation: machine speed vs defect rate
    production["defect_rate"] = (100 * production["defect_count"] /
                                 production["units_produced"].clip(lower=1))
    r, p = stats.pearsonr(production["machine_speed"], production["defect_rate"])
    print(f"  speed vs defect rate: r = {r:.2f} (p = {p:.2e})")

    num_cols = ["machine_speed", "run_time_hrs", "units_produced",
                "defect_count", "defect_rate"]
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(production[num_cols].corr(), annot=True, fmt=".2f",
                cmap="coolwarm", ax=ax)
    ax.set_title("Correlation matrix (Pearson)")
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "correlation_matrix.png", dpi=120)
    plt.close(fig)

    # shift-level defect comparison boxplot
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(data=production, x="shift", y="defect_rate", order=config.SHIFTS, ax=ax)
    ax.set_title("Defect rate by shift")
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / "defect_rate_by_shift.png", dpi=120)
    plt.close(fig)

    print(f"  EDA charts written to {config.CHARTS_DIR}")
    return {"speed_defect_r": r}


if __name__ == "__main__":
    main()
