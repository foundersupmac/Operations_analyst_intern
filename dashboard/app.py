"""Real-time operations dashboard (Streamlit + Plotly).

Live view of the simulated shopfloor feed plus the analytical layers
built during the internship: KPI tiles, line OEE, downtime Pareto,
predictive-maintenance alerts and the demand outlook.

Run:
    python -m src.live_feed --interval 2   # in one terminal
    streamlit run dashboard/app.py         # in another
"""
import pickle
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

st.set_page_config(page_title="Operations Control Tower",
                   layout="wide", page_icon="🏭")

PDM_THRESHOLD = 0.5
FEATURES = ["vibration_mm_s", "temperature_c", "current_a",
            "cycle_count", "days_since_maintenance"]


def query(sql, params=()):
    with sqlite3.connect(config.DB_PATH) as conn:
        return pd.read_sql(sql, conn, params=params)


@st.cache_resource
def load_pdm_model():
    path = config.MODELS_DIR / "rf_pdm_v1.pkl"
    if path.exists():
        with open(path, "rb") as fh:
            return pickle.load(fh)
    return None


st.title("🏭 Operations Control Tower — Arrowcosta")
st.caption("Live shopfloor feed (5-min buckets) · refreshes every 5 seconds")


@st.fragment(run_every="5s")
def live_section():
    prod = query("SELECT * FROM live_production ORDER BY ts DESC LIMIT 4000")
    if prod.empty:
        st.warning("No live data yet — start the feed: "
                   "`python -m src.live_feed --interval 2`")
        return
    prod["ts"] = pd.to_datetime(prod["ts"])
    latest_ts = prod["ts"].max()
    window = prod[prod["ts"] >= latest_ts - pd.Timedelta(minutes=30)]

    # ---- KPI tiles -------------------------------------------------
    avail = window["running"].mean()
    units = int(window["units"].sum())
    defects = int(window["defects"].sum())
    defect_rate = 100 * defects / max(units, 1)
    oee_proxy = avail * 0.90 * (1 - defect_rate / 100)

    sensors = query(
        "SELECT * FROM live_sensors ORDER BY ts DESC LIMIT 12")
    n_alerts = 0
    model = load_pdm_model()
    if model is not None and not sensors.empty:
        sensors["risk"] = model.predict_proba(sensors[FEATURES])[:, 1]
        n_alerts = int((sensors["risk"] >= PDM_THRESHOLD).sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Live OEE (est.)", f"{oee_proxy * 100:.1f}%")
    c2.metric("Availability (30 min)", f"{avail * 100:.1f}%")
    c3.metric("Units (30 min)", f"{units:,}")
    c4.metric("Defect rate", f"{defect_rate:.2f}%")
    c5.metric("⚠️ PdM alerts", n_alerts,
              delta="machines at risk" if n_alerts else "all clear",
              delta_color="inverse" if n_alerts else "normal")

    # ---- live charts ----------------------------------------------
    left, right = st.columns([3, 2])
    with left:
        tput = (window.set_index("ts").groupby([pd.Grouper(freq="1min"), "line"])
                ["units"].sum().reset_index())
        fig = px.line(tput, x="ts", y="units", color="line",
                      title="Throughput by line (units/min, last 30 min)")
        fig.update_layout(height=320, margin=dict(t=40, b=10))
        st.plotly_chart(fig, width="stretch")
    with right:
        line_avail = (window.groupby("line")["running"].mean() * 100).round(1)
        fig = go.Figure(go.Bar(x=line_avail.index, y=line_avail.values,
                               marker_color=["#2ca02c" if v >= 80 else
                                             "#d62728" for v in line_avail]))
        fig.update_layout(title="Availability by line (last 30 min, %)",
                          height=320, margin=dict(t=40, b=10),
                          yaxis_range=[0, 100])
        st.plotly_chart(fig, width="stretch")

    # ---- PdM alert table -------------------------------------------
    if model is not None and not sensors.empty:
        at_risk = sensors[sensors["risk"] >= PDM_THRESHOLD]
        if not at_risk.empty:
            st.error(f"Predictive maintenance: {len(at_risk)} machine(s) "
                     "predicted to fail within 72 hours")
            st.dataframe(
                at_risk[["machine_id", "vibration_mm_s", "temperature_c",
                         "current_a", "days_since_maintenance", "risk"]]
                .sort_values("risk", ascending=False)
                .style.format({"risk": "{:.0%}"}),
                width="stretch", hide_index=True)


live_section()

# ---- historical / analytical layer (static per page load) ----------
st.divider()
st.subheader("Analytical layer — 12-month history")
tab1, tab2, tab3 = st.tabs(["OEE & downtime", "KPI baseline", "Demand"])

with tab1:
    left, right = st.columns(2)
    hist = query("SELECT * FROM production")
    hist["date"] = pd.to_datetime(hist["date"])
    hist["availability"] = hist["run_time_hrs"] / hist["planned_time_hrs"]
    daily = (hist.groupby([pd.Grouper(key="date", freq="W"), "line"])
             ["availability"].mean().mul(100).reset_index())
    with left:
        fig = px.line(daily, x="date", y="availability", color="line",
                      title="Weekly availability by line (%)")
        st.plotly_chart(fig, width="stretch")
    with right:
        dt = query("SELECT cause_code, SUM(duration_hrs) AS hrs FROM downtime "
                   "GROUP BY cause_code ORDER BY hrs DESC")
        fig = px.bar(dt, x="cause_code", y="hrs",
                     title="Downtime Pareto (total hours, 12 months)")
        st.plotly_chart(fig, width="stretch")

with tab2:
    kpi_path = config.REPORTS_DIR / "kpi_baseline.csv"
    if kpi_path.exists():
        kpi = pd.read_csv(kpi_path)
        st.dataframe(kpi.style.map(
            lambda v: "background-color:#fadbd8" if v == "RED"
            else ("background-color:#d5f5e3" if v == "GREEN" else ""),
            subset=["status"]), width="stretch", hide_index=True)
    else:
        st.info("Run `python run_all.py` to compute the KPI baseline.")

with tab3:
    demand = query("SELECT * FROM demand_history")
    demand["date"] = pd.to_datetime(demand["date"])
    fig = px.line(demand.tail(120), x="date", y="demand_units",
                  title="Daily demand — last 120 days")
    st.plotly_chart(fig, width="stretch")
    cmp_path = config.REPORTS_DIR / "forecast_comparison.csv"
    if cmp_path.exists():
        st.dataframe(pd.read_csv(cmp_path), hide_index=True)
        st.caption("60-day hold-out MAPE — XGBoost model in production "
                   "(output/models/xgboost_demand_v1.pkl)")
