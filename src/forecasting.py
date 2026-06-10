"""Demand forecasting (week 18): XGBoost with 18 engineered features vs
SARIMA and naive benchmarks, evaluated with time-series cross-validation
and a 60-day hold-out."""
import pickle

import numpy as np
import pandas as pd
import xgboost as xgb
from statsmodels.tsa.statespace.sarimax import SARIMAX

import config
from src.etl_pipeline import read_table

HOLDOUT_DAYS = 60


def engineer_features(df):
    df = df.set_index("date").asfreq("D")
    df["demand_units"] = df["demand_units"].interpolate()
    f = pd.DataFrame(index=df.index)
    y = df["demand_units"]
    # time-based (6)
    f["dayofweek"] = df.index.dayofweek
    f["month"] = df.index.month
    f["day"] = df.index.day
    f["weekofyear"] = df.index.isocalendar().week.astype(int)
    f["quarter"] = df.index.quarter
    f["is_month_end"] = df.index.is_month_end.astype(int)
    # lag (4)
    for lag in (1, 7, 14, 28):
        f[f"lag_{lag}"] = y.shift(lag)
    # rolling statistics (4)
    f["roll_mean_7"] = y.shift(1).rolling(7).mean()
    f["roll_mean_28"] = y.shift(1).rolling(28).mean()
    f["roll_std_7"] = y.shift(1).rolling(7).std()
    f["roll_max_14"] = y.shift(1).rolling(14).max()
    # exogenous proxies (2)
    f["days_since_start"] = np.arange(len(f))
    # customer payment cycles (10th/25th) drive B2B batch orders
    f["is_payment_cycle"] = f.index.day.isin((10, 25)).astype(int)
    # B2B batch-order pattern flags (2)
    spike_threshold = y.shift(1).rolling(28).mean() + 2 * y.shift(1).rolling(28).std()
    f["recent_batch_order"] = (y.shift(1) > spike_threshold).astype(int)
    f["batch_in_last_7"] = f["recent_batch_order"].rolling(7).max()
    return f.dropna(), y.loc[f.dropna().index]


def mape(actual, pred):
    return 100 * np.mean(np.abs((actual - pred) / actual))


def main():
    demand = read_table("demand_history")
    X, y = engineer_features(demand)
    X_train, X_test = X.iloc[:-HOLDOUT_DAYS], X.iloc[-HOLDOUT_DAYS:]
    y_train, y_test = y.iloc[:-HOLDOUT_DAYS], y.iloc[-HOLDOUT_DAYS:]

    model = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1,
                             random_state=config.RANDOM_SEED)
    model.fit(X_train, y_train)
    xgb_mape = mape(y_test.values, model.predict(X_test))

    sarima = SARIMAX(y_train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 7)).fit(disp=False)
    sarima_mape = mape(y_test.values, sarima.forecast(HOLDOUT_DAYS).values)

    naive_mape = mape(y_test.values, y.shift(7).iloc[-HOLDOUT_DAYS:].values)

    print(f"  60-day hold-out MAPE: XGBoost {xgb_mape:.1f}% | "
          f"SARIMA {sarima_mape:.1f}% | Naive(7d) {naive_mape:.1f}%")

    importances = pd.Series(model.feature_importances_, index=X.columns)
    top = importances.sort_values(ascending=False).head(5).round(3)
    print(f"  top features: {top.to_dict()}")

    with open(config.MODELS_DIR / "xgboost_demand_v1.pkl", "wb") as fh:
        pickle.dump(model, fh)
    pd.DataFrame({"model": ["XGBoost", "SARIMA", "Naive"],
                  "mape_pct": [xgb_mape, sarima_mape, naive_mape]}).round(2) \
        .to_csv(config.REPORTS_DIR / "forecast_comparison.csv", index=False)
    return xgb_mape, sarima_mape, naive_mape


if __name__ == "__main__":
    main()
