"""Statistical modelling (weeks 11-12): OLS defect-rate regression with
HC3 robust errors, one-way ANOVA across shifts and Tukey HSD post-hoc."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.model_selection import train_test_split
from statsmodels.stats.multicomp import pairwise_tukeyhsd

import config
from src.etl_pipeline import read_table


def build_frame():
    production = read_table("production")
    sensors = read_table("sensors")
    df = production.merge(
        sensors[["date", "machine_id", "days_since_maintenance"]],
        on=["date", "machine_id"], how="left")
    df["defect_rate"] = 100 * df["defect_count"] / df["units_produced"].clip(lower=1)
    df["days_since_maintenance"] = df["days_since_maintenance"].fillna(
        df["days_since_maintenance"].median())
    return df.dropna(subset=["defect_rate", "machine_speed"])


def regression(df):
    train, test = train_test_split(df, test_size=0.2, random_state=config.RANDOM_SEED)
    formula = ("defect_rate ~ machine_speed + days_since_maintenance "
               "+ C(material_grade) + C(shift) + C(line)")
    model = smf.ols(formula, data=train).fit(cov_type="HC3")

    pred = model.predict(test)
    ss_res = ((test["defect_rate"] - pred) ** 2).sum()
    ss_tot = ((test["defect_rate"] - test["defect_rate"].mean()) ** 2).sum()
    r2_test = 1 - ss_res / ss_tot

    summary_path = config.REPORTS_DIR / "regression_summary.txt"
    summary_path.write_text(model.summary().as_text()
                            + f"\n\nHeld-out test R2: {r2_test:.3f}\n")
    print(f"  OLS defect-rate model: train R2={model.rsquared:.3f}, "
          f"test R2={r2_test:.3f} (HC3 robust SEs)")
    return model, r2_test


def anova_shifts(df):
    groups = [g["defect_rate"].values for _, g in df.groupby("shift")]
    f_stat, p = stats.f_oneway(*groups)
    print(f"  ANOVA shift effect: F={f_stat:.2f}, p={p:.2e}")

    tukey = pairwise_tukeyhsd(df["defect_rate"], df["shift"])
    (config.REPORTS_DIR / "anova_tukey.txt").write_text(
        f"One-way ANOVA: F={f_stat:.2f}, p={p:.3e}\n\n{tukey}\n")
    print("  Tukey HSD written to anova_tukey.txt")
    return f_stat, p


def main():
    df = build_frame()
    model, r2 = regression(df)
    anova_shifts(df)
    return model, r2


if __name__ == "__main__":
    main()
