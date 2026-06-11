"""FastAPI backend for the Operations Control Tower frontend.

Serves the analytics in data/operations.db as JSON and, when present,
the built React app from frontend/dist.

Run:
    python -m src.live_feed --interval 2          # live data feed
    uvicorn api.main:app --port 8000 --reload     # API + frontend
"""
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

app = FastAPI(title="Operations Control Tower API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

FEATURES = ["vibration_mm_s", "temperature_c", "current_a",
            "cycle_count", "days_since_maintenance"]
_pdm_model = None


def query(sql, params=()):
    with sqlite3.connect(config.DB_PATH) as conn:
        return pd.read_sql(sql, conn, params=params)


def pdm_model():
    global _pdm_model
    if _pdm_model is None:
        path = config.MODELS_DIR / "rf_pdm_v1.pkl"
        if path.exists():
            with open(path, "rb") as fh:
                _pdm_model = pickle.load(fh)
    return _pdm_model


def production():
    df = query("SELECT * FROM production")
    df["date"] = pd.to_datetime(df["date"])
    df["availability"] = df["run_time_hrs"] / df["planned_time_hrs"]
    ideal = config.IDEAL_CYCLE_TIME_MIN / 60
    df["performance"] = (df["units_produced"] * ideal /
                         df["run_time_hrs"].clip(lower=0.01)).clip(upper=1.0)
    df["quality"] = ((df["units_produced"] - df["defect_count"]) /
                     df["units_produced"].clip(lower=1)).clip(0, 1)
    df["oee"] = df["availability"] * df["performance"] * df["quality"]
    df["defect_rate"] = 100 * df["defect_count"] / df["units_produced"].clip(lower=1)
    return df


def records(df):
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    out = out.replace([np.inf, -np.inf], np.nan)
    out = out.astype(object).where(pd.notna(out), None)
    return out.to_dict(orient="records")


@app.get("/api/live")
def live():
    prod = query("SELECT * FROM live_production ORDER BY ts DESC LIMIT 4000")
    if prod.empty:
        return {"ok": False, "message": "live feed not running"}
    prod["ts"] = pd.to_datetime(prod["ts"])
    window = prod[prod["ts"] >= prod["ts"].max() - pd.Timedelta(minutes=30)]

    avail = float(window["running"].mean())
    units = int(window["units"].sum())
    defects = int(window["defects"].sum())
    defect_rate = 100 * defects / max(units, 1)
    oee = avail * 0.90 * (1 - defect_rate / 100)

    sensors = query("SELECT * FROM live_sensors ORDER BY ts DESC LIMIT 12")
    alerts = []
    model = pdm_model()
    if model is not None and not sensors.empty:
        sensors["risk"] = model.predict_proba(sensors[FEATURES])[:, 1]
        alerts = records(
            sensors[sensors["risk"] >= 0.5]
            .sort_values("risk", ascending=False)
            [["machine_id", "vibration_mm_s", "temperature_c",
              "current_a", "days_since_maintenance", "risk"]].round(3))

    tput = (window.set_index("ts")
            .groupby([pd.Grouper(freq="1min"), "line"])["units"].sum()
            .unstack(fill_value=0))
    series = [{"t": ts.strftime("%H:%M"),
               **{line: int(v) for line, v in row.items()}}
              for ts, row in tput.iterrows()]
    line_avail = (window.groupby("line")["running"].mean() * 100).round(1)

    return {"ok": True,
            "tiles": {"oee": round(oee * 100, 1),
                      "availability": round(avail * 100, 1),
                      "units": units,
                      "defect_rate": round(defect_rate, 2),
                      "alerts": len(alerts)},
            "throughput": series,
            "line_availability": [{"line": k, "value": float(v)}
                                  for k, v in line_avail.items()],
            "pdm_alerts": alerts}


@app.get("/api/oee")
def oee():
    prod = production()
    decomp = (prod.groupby("line")[["availability", "performance",
                                    "quality", "oee"]].mean() * 100).round(1)
    weekly = (prod.groupby([pd.Grouper(key="date", freq="W"), "line"])["oee"]
              .mean().mul(100).round(1).unstack())
    trend = [{"date": d.strftime("%Y-%m-%d"),
              **{line: (None if pd.isna(v) else float(v))
                 for line, v in row.items()}}
             for d, row in weekly.iterrows()]
    return {"decomposition": [{"line": idx, **row.to_dict()}
                              for idx, row in decomp.iterrows()],
            "trend": trend}


@app.get("/api/downtime")
def downtime():
    dt = query("SELECT * FROM downtime")
    pareto = (dt.groupby("cause_code")["duration_hrs"]
              .agg(hours="sum", events="count").round(1)
              .sort_values("hours", ascending=False).reset_index())
    pareto["cum_pct"] = (100 * pareto["hours"].cumsum()
                         / pareto["hours"].sum()).round(1)
    bd = dt[dt["cause_code"] == "Breakdown"]
    by_line = (dt.groupby("line")["duration_hrs"].sum().round(1)
               .reset_index().rename(columns={"duration_hrs": "hours"}))
    top = dt.sort_values("duration_hrs", ascending=False).head(10)
    return {"summary": {"events": len(dt),
                        "hours": round(float(dt["duration_hrs"].sum()), 1),
                        "mttr": round(float(bd["duration_hrs"].mean()), 2),
                        "breakdown_share": round(100 * bd["duration_hrs"].sum()
                                                 / dt["duration_hrs"].sum(), 1)},
            "pareto": records(pareto),
            "by_line": records(by_line),
            "top_events": records(top)}


@app.get("/api/quality")
def quality():
    prod = production()
    q = query("SELECT * FROM quality")
    by_shift = (prod.groupby("shift")["defect_rate"]
                .agg(["mean", "median"]).round(3).reset_index())
    daily = (prod.groupby("date")
             .apply(lambda g: 100 * g["defect_count"].sum()
                    / max(g["units_produced"].sum(), 1),
                    include_groups=False)
             .rename("rate").round(3).reset_index())
    sample = prod.sample(min(1500, len(prod)), random_state=1)
    return {"fpy": round(100 * float((q["usage_decision"] == "Accepted").mean()), 1),
            "avg_defect_rate": round(float(prod["defect_rate"].mean()), 2),
            "by_shift": records(by_shift),
            "control_chart": records(daily),
            "mean": round(float(daily["rate"].mean()), 3),
            "ucl": round(float(daily["rate"].mean() + 3 * daily["rate"].std()), 3),
            "lcl": round(max(float(daily["rate"].mean() - 3 * daily["rate"].std()), 0), 3),
            "scatter": records(sample[["machine_speed", "defect_rate",
                                       "material_grade"]].round(2))}


@app.get("/api/inventory")
def inventory():
    path = config.REPORTS_DIR / "inventory_eoq_analysis.csv"
    if not path.exists():
        return {"ok": False, "message": "run run_all.py first"}
    inv = pd.read_csv(path).round(2)
    over = inv[inv["action"].str.startswith("REDUCE")]
    urgent = inv[inv["action"] == "URGENT REORDER"]
    excess = float(((over["current_stock_units"]
                     - 90 * over["annual_demand_units"] / 365)
                    * over["unit_cost_inr"]).sum())
    return {"ok": True,
            "summary": {"skus": len(inv), "overstocked": len(over),
                        "stockout_risk": len(urgent),
                        "excess_lakh": round(excess / 1e5, 1)},
            "skus": records(inv)}


@app.get("/api/forecast")
def forecast():
    demand = query("SELECT * FROM demand_history")
    demand["date"] = pd.to_datetime(demand["date"])
    tail = demand.tail(180).copy()
    tail["payment_cycle"] = tail["date"].dt.day.isin((10, 25))
    cmp_path = config.REPORTS_DIR / "forecast_comparison.csv"
    comparison = (pd.read_csv(cmp_path).round(2).to_dict(orient="records")
                  if cmp_path.exists() else [])
    return {"history": records(tail), "comparison": comparison}


@app.get("/api/pdm")
def pdm():
    sensors = query("SELECT * FROM sensors")
    sensors["date"] = pd.to_datetime(sensors["date"])
    model = pdm_model()
    latest = sensors.sort_values("date").groupby("machine_id").tail(1).copy()
    if model is not None:
        latest["risk"] = model.predict_proba(latest[FEATURES])[:, 1].round(3)
    fleet = records(latest[["machine_id", "vibration_mm_s", "temperature_c",
                            "current_a", "days_since_maintenance"]
                           + (["risk"] if "risk" in latest else [])]
                    .sort_values("risk" if "risk" in latest else "machine_id",
                                 ascending=False))
    rep_path = config.REPORTS_DIR / "pdm_classification_report.txt"
    return {"fleet": fleet,
            "report": rep_path.read_text() if rep_path.exists() else ""}


@app.get("/api/pdm/machine/{machine_id}")
def pdm_machine(machine_id: str):
    sensors = query("SELECT * FROM sensors WHERE machine_id = ? ORDER BY date",
                    (machine_id,))
    sensors["date"] = pd.to_datetime(sensors["date"])
    model = pdm_model()
    if model is not None:
        sensors["risk"] = model.predict_proba(sensors[FEATURES])[:, 1].round(3)
    return {"series": records(sensors.round(2))}


@app.get("/api/simulation")
def simulation():
    sim_path = config.REPORTS_DIR / "simulation_scenarios.csv"
    scenarios = (pd.read_csv(sim_path).to_dict(orient="records")
                 if sim_path.exists() else [])
    cba = [
        {"initiative": "SMED changeover reduction", "benefit": 9.8, "cost": 1.2, "payback": 1.5},
        {"initiative": "Predictive maintenance", "benefit": 13.8, "cost": 3.5, "payback": 3.0},
        {"initiative": "Digital QC entry", "benefit": 4.6, "cost": 0.8, "payback": 2.1},
        {"initiative": "Inventory rebalancing", "benefit": 8.2, "cost": 0.4, "payback": 0.6},
        {"initiative": "Demand forecasting", "benefit": 3.4, "cost": 0.6, "payback": 2.1},
    ]
    return {"scenarios": scenarios, "cba": cba,
            "programme": {"benefit_lakh": 39.8, "ratio": "6.1 : 1"}}


@app.get("/api/throughput")
def throughput():
    prod = production()
    daily = prod.groupby("date")["units_produced"].sum()
    out = pd.DataFrame({"units": daily,
                        "avg7": daily.rolling(7).mean().round(0),
                        "avg28": daily.rolling(28).mean().round(0)})
    out.index.name = "date"
    weekday = (prod.assign(dow=prod["date"].dt.day_name())
               .groupby("dow")["units_produced"].mean().round(0)
               .reindex(["Monday", "Tuesday", "Wednesday", "Thursday",
                         "Friday", "Saturday", "Sunday"]).reset_index())
    l2 = prod[prod["line"] == "Line 2"].copy()
    l2["period"] = np.where(l2["date"] < "2025-07-15", "pre", "post")
    bins = np.linspace(l2["machine_speed"].min(), l2["machine_speed"].max(), 40)
    hist = []
    for period, g in l2.groupby("period"):
        counts, edges = np.histogram(g["machine_speed"], bins=bins)
        for c, e in zip(counts, edges):
            hist.append({"speed": round(float(e), 1), "period": period,
                         "count": int(c)})
    return {"daily": records(out.reset_index()),
            "weekday": records(weekday),
            "line2_hist": hist}


@app.get("/api/kpis")
def kpis():
    path = config.REPORTS_DIR / "kpi_baseline.csv"
    if not path.exists():
        return {"ok": False}
    kpi = pd.read_csv(path)
    dq_path = config.REPORTS_DIR / "data_quality_report.csv"
    dq = records(pd.read_csv(dq_path)) if dq_path.exists() else []
    return {"ok": True, "kpis": records(kpi), "data_quality": dq}


# serve the built React app if available
dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
