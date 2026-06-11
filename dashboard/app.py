"""Operations Control Tower — multi-page real-time dashboard.

Ten pages mirroring the 10-page report structure built during the
internship: a live control tower plus dedicated analytical pages for
OEE, downtime, quality, throughput, inventory, demand forecasting,
predictive maintenance, scenario simulation / cost-benefit and the
KPI baseline / data-quality monitor.

Run:
    python -m src.live_feed --interval 2     # terminal 1: live feed
    streamlit run dashboard/app.py           # terminal 2
"""
import pickle
import sqlite3
import sys
from pathlib import Path

import numpy as np
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


# ---------------------------------------------------------------- helpers
def query(sql, params=()):
    with sqlite3.connect(config.DB_PATH) as conn:
        return pd.read_sql(sql, conn, params=params)


@st.cache_data(ttl=300)
def load_production():
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


@st.cache_data(ttl=300)
def load_downtime():
    df = query("SELECT * FROM downtime")
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_resource
def load_pdm_model():
    path = config.MODELS_DIR / "rf_pdm_v1.pkl"
    if path.exists():
        with open(path, "rb") as fh:
            return pickle.load(fh)
    return None


def line_filter(df, key):
    lines = st.multiselect("Production lines", config.LINES,
                           default=config.LINES, key=key)
    return df[df["line"].isin(lines)] if lines else df


def date_filter(df, key):
    lo, hi = df["date"].min().date(), df["date"].max().date()
    start, end = st.slider("Period", lo, hi, (lo, hi), key=key)
    return df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]


# ---------------------------------------------------------------- pages
def page_live():
    st.title("🏭 Live Control Tower")
    st.caption("Simulated shopfloor feed (5-min buckets) · auto-refreshes every 5 s")

    @st.fragment(run_every="5s")
    def live_section():
        prod = query("SELECT * FROM live_production ORDER BY ts DESC LIMIT 4000")
        if prod.empty:
            st.warning("No live data yet — start the feed: "
                       "`python -m src.live_feed --interval 2`")
            return
        prod["ts"] = pd.to_datetime(prod["ts"])
        window = prod[prod["ts"] >= prod["ts"].max() - pd.Timedelta(minutes=30)]

        avail = window["running"].mean()
        units = int(window["units"].sum())
        defects = int(window["defects"].sum())
        defect_rate = 100 * defects / max(units, 1)
        oee_proxy = avail * 0.90 * (1 - defect_rate / 100)

        sensors = query("SELECT * FROM live_sensors ORDER BY ts DESC LIMIT 12")
        model = load_pdm_model()
        n_alerts = 0
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

        left, right = st.columns([3, 2])
        with left:
            tput = (window.set_index("ts")
                    .groupby([pd.Grouper(freq="1min"), "line"])["units"]
                    .sum().reset_index())
            fig = px.line(tput, x="ts", y="units", color="line",
                          title="Throughput by line (units/min, last 30 min)")
            fig.update_layout(height=320, margin=dict(t=40, b=10))
            st.plotly_chart(fig, width="stretch")
        with right:
            la = (window.groupby("line")["running"].mean() * 100).round(1)
            fig = go.Figure(go.Bar(
                x=la.index, y=la.values,
                marker_color=["#2ca02c" if v >= 80 else "#d62728"
                              for v in la.values]))
            fig.update_layout(title="Availability by line (last 30 min, %)",
                              height=320, margin=dict(t=40, b=10),
                              yaxis_range=[0, 100])
            st.plotly_chart(fig, width="stretch")

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


def page_oee():
    st.title("📊 OEE Analysis")
    prod = line_filter(date_filter(load_production(), "oee_date"), "oee_lines")

    decomp = (prod.groupby("line")[["availability", "performance",
                                    "quality", "oee"]].mean() * 100).round(1)
    cols = st.columns(len(decomp) or 1)
    for col, (line, row) in zip(cols, decomp.iterrows()):
        col.metric(f"{line} OEE", f"{row['oee']:.1f}%",
                   delta=f"{row['oee'] - 75:.1f} pp vs 75% target",
                   delta_color="normal" if row["oee"] >= 75 else "inverse")

    left, right = st.columns(2)
    with left:
        fig = px.bar(decomp.reset_index().melt(id_vars="line",
                     value_vars=["availability", "performance", "quality"]),
                     x="line", y="value", color="variable", barmode="group",
                     title="OEE component decomposition (A × P × Q)")
        st.plotly_chart(fig, width="stretch")
    with right:
        weekly = (prod.groupby([pd.Grouper(key="date", freq="W"), "line"])
                  ["oee"].mean().mul(100).reset_index())
        fig = px.line(weekly, x="date", y="oee", color="line",
                      title="Weekly OEE trend by line (%)")
        fig.add_hline(y=65, line_dash="dash", line_color="red",
                      annotation_text="65% threshold")
        st.plotly_chart(fig, width="stretch")

    st.info("**Finding (Wk 9–10):** Line 3 runs consistently below the 65% "
            "threshold since Sep 2025 — availability is the dominant loss "
            "driver, confirming it as the facility bottleneck.")


def page_downtime():
    st.title("🔧 Downtime Analysis")
    dt = line_filter(date_filter(load_downtime(), "dt_date"), "dt_lines")

    total_h = dt["duration_hrs"].sum()
    bd = dt[dt["cause_code"] == "Breakdown"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events", f"{len(dt):,}")
    c2.metric("Total hours lost", f"{total_h:,.0f}")
    c3.metric("MTTR (breakdowns)", f"{bd['duration_hrs'].mean():.2f} h")
    c4.metric("Breakdown share", f"{100 * bd['duration_hrs'].sum() / max(total_h, 0.01):.1f}%")

    left, right = st.columns(2)
    with left:
        pareto = (dt.groupby("cause_code")["duration_hrs"].sum()
                  .sort_values(ascending=False))
        cum = 100 * pareto.cumsum() / pareto.sum()
        fig = go.Figure()
        fig.add_bar(x=pareto.index, y=pareto.values, name="hours")
        fig.add_scatter(x=pareto.index, y=cum.values, name="cumulative %",
                        yaxis="y2", mode="lines+markers")
        fig.update_layout(title="Downtime Pareto (by duration)",
                          yaxis2=dict(overlaying="y", side="right",
                                      range=[0, 105]))
        st.plotly_chart(fig, width="stretch")
    with right:
        monthly = (dt.groupby([pd.Grouper(key="date", freq="ME"), "cause_code"])
                   ["duration_hrs"].sum().reset_index())
        fig = px.area(monthly, x="date", y="duration_hrs", color="cause_code",
                      title="Monthly downtime hours by category")
        st.plotly_chart(fig, width="stretch")

    spindle = dt[dt["cause_detail"].str.contains("Spindle", na=False)]
    st.info(f"**RCA (Wk 11):** {len(spindle)} spindle-bearing failure events "
            "— 5-Why traced these to a missing ECN process linking production "
            "speed changes to maintenance SOP reviews.")
    st.dataframe(dt.sort_values("duration_hrs", ascending=False).head(15),
                 width="stretch", hide_index=True)


def page_quality():
    st.title("✅ Quality Analytics")
    prod = line_filter(date_filter(load_production(), "q_date"), "q_lines")
    quality = query("SELECT * FROM quality")

    fpy = 100 * (quality["usage_decision"] == "Accepted").mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("First-Pass Yield", f"{fpy:.1f}%")
    c2.metric("Avg defect rate", f"{prod['defect_rate'].mean():.2f}%")
    c3.metric("Inspection lots", f"{len(quality):,}")

    left, right = st.columns(2)
    with left:
        fig = px.box(prod, x="shift", y="defect_rate",
                     category_orders={"shift": config.SHIFTS},
                     title="Defect rate by shift (ANOVA: Shift B significantly higher)")
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.scatter(prod.sample(min(4000, len(prod)), random_state=1),
                         x="machine_speed", y="defect_rate",
                         color="material_grade", opacity=0.4, trendline="ols",
                         title="Machine speed vs defect rate (r ≈ 0.77)")
        st.plotly_chart(fig, width="stretch")

    # p-chart style control chart on daily defect rate
    daily = (prod.groupby("date")
             .apply(lambda g: 100 * g["defect_count"].sum()
                    / max(g["units_produced"].sum(), 1),
                    include_groups=False).rename("rate").reset_index())
    mean = daily["rate"].mean()
    sigma = daily["rate"].std()
    fig = px.line(daily, x="date", y="rate",
                  title="Daily defect rate control chart (±3σ)")
    for y, c in ((mean, "green"), (mean + 3 * sigma, "red"),
                 (mean - 3 * sigma, "red")):
        fig.add_hline(y=y, line_dash="dot", line_color=c)
    st.plotly_chart(fig, width="stretch")

    anova_path = config.REPORTS_DIR / "anova_tukey.txt"
    if anova_path.exists():
        with st.expander("ANOVA + Tukey HSD results (Wk 12)"):
            st.code(anova_path.read_text())


def page_throughput():
    st.title("📈 Throughput & Time Series")
    prod = line_filter(load_production(), "tp_lines")

    daily = prod.groupby("date")["units_produced"].sum().rename("units")
    fig = go.Figure()
    fig.add_scatter(x=daily.index, y=daily.values, name="daily",
                    line=dict(width=1), opacity=0.5)
    fig.add_scatter(x=daily.index, y=daily.rolling(7).mean(), name="7-day avg")
    fig.add_scatter(x=daily.index, y=daily.rolling(28).mean(), name="28-day avg")
    fig.add_vrect(x0="2025-08-15", x1="2025-09-10", fillcolor="orange",
                  opacity=0.15, annotation_text="maintenance shutdown")
    fig.update_layout(title="Daily production output with rolling averages")
    st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        prod["dow"] = prod["date"].dt.day_name()
        dow = (prod.groupby("dow")["units_produced"].mean()
               .reindex(["Monday", "Tuesday", "Wednesday", "Thursday",
                         "Friday", "Saturday", "Sunday"]))
        fig = px.bar(dow, title="Average output by weekday (weekly seasonality)")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with right:
        l2 = load_production()
        l2 = l2[l2["line"] == "Line 2"]
        l2["period"] = np.where(l2["date"] < "2025-07-15",
                                "pre-firmware", "post-firmware")
        fig = px.histogram(l2, x="machine_speed", color="period", nbins=60,
                           barmode="overlay", opacity=0.6,
                           title="Line 2 speed: bimodal after Jul-2025 firmware update")
        st.plotly_chart(fig, width="stretch")

    st.info("**Finding (Wk 9):** ADF tests show the throughput series is "
            "stationarity-borderline at level and clearly stationary after "
            "first differencing; STL decomposition confirms weekly seasonality.")


def page_inventory():
    st.title("📦 Inventory Optimisation")
    path = config.REPORTS_DIR / "inventory_eoq_analysis.csv"
    if not path.exists():
        st.warning("Run `python run_all.py` to generate the EOQ analysis.")
        return
    inv = pd.read_csv(path)

    over = inv[inv["action"].str.startswith("REDUCE")]
    urgent = inv[inv["action"] == "URGENT REORDER"]
    excess_value = ((over["current_stock_units"]
                     - 90 * over["annual_demand_units"] / 365)
                    * over["unit_cost_inr"]).sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SKUs analysed", len(inv))
    c2.metric("Overstocked (>90d)", len(over))
    c3.metric("Excess value", f"₹{excess_value / 1e5:.1f} L")
    c4.metric("Stockout risk", len(urgent))

    fig = px.scatter(inv, x="days_of_supply", y="unit_cost_inr",
                     size="annual_demand_units", color="action", log_y=True,
                     hover_name="sku",
                     title="SKU positioning: days of supply vs unit cost")
    fig.add_vline(x=90, line_dash="dash", line_color="red",
                  annotation_text="90-day limit")
    st.plotly_chart(fig, width="stretch")

    tab1, tab2 = st.tabs(["Action list", "Full EOQ table"])
    with tab1:
        st.dataframe(inv[inv["action"] != "OK"]
                     .sort_values("days_of_supply", ascending=False),
                     width="stretch", hide_index=True)
    with tab2:
        st.dataframe(inv, width="stretch", hide_index=True)


def page_forecast():
    st.title("🔮 Demand Forecast")
    demand = query("SELECT * FROM demand_history")
    demand["date"] = pd.to_datetime(demand["date"])

    cmp_path = config.REPORTS_DIR / "forecast_comparison.csv"
    if cmp_path.exists():
        cmp = pd.read_csv(cmp_path)
        cols = st.columns(len(cmp))
        best = cmp.loc[cmp["mape_pct"].idxmin(), "model"]
        for col, row in zip(cols, cmp.itertuples()):
            col.metric(f"{row.model} MAPE", f"{row.mape_pct:.1f}%",
                       delta="selected" if row.model == best else None)

    fig = px.line(demand.tail(180), x="date", y="demand_units",
                  title="Daily demand — last 180 days (note 10th/25th payment-cycle spikes)")
    spikes = demand.tail(180)
    spikes = spikes[pd.to_datetime(spikes["date"]).dt.day.isin((10, 25))]
    fig.add_scatter(x=spikes["date"], y=spikes["demand_units"], mode="markers",
                    marker=dict(color="red", size=7), name="payment-cycle days")
    st.plotly_chart(fig, width="stretch")

    model_path = config.MODELS_DIR / "xgboost_demand_v1.pkl"
    if model_path.exists():
        with open(model_path, "rb") as fh:
            model = pickle.load(fh)
        imp = pd.Series(model.feature_importances_,
                        index=model.get_booster().feature_names
                        if hasattr(model, "get_booster") else None)
        if imp.index is not None:
            fig = px.bar(imp.sort_values().tail(10), orientation="h",
                         title="XGBoost feature importance (top 10)")
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch")
    st.info("**Method (Wk 18):** 18 engineered features (lags, rolling stats, "
            "calendar, B2B payment-cycle flags), tuned with rolling time-series "
            "CV; XGBoost selected over SARIMA and naive on a 60-day hold-out.")


def page_pdm():
    st.title("🛠️ Predictive Maintenance")
    sensors = query("SELECT * FROM sensors")
    sensors["date"] = pd.to_datetime(sensors["date"])
    model = load_pdm_model()

    rep_path = config.REPORTS_DIR / "pdm_classification_report.txt"
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Model card — RF v1.0")
        st.markdown("- Random Forest, 200 trees\n"
                    "- SMOTE inside CV pipeline (no leakage)\n"
                    "- Label: failure within 72 h\n"
                    "- Horizon recommended: 72 h")
        if rep_path.exists():
            st.code(rep_path.read_text())
    with c2:
        machine = st.selectbox("Machine", sorted(sensors["machine_id"].unique()))
        m = sensors[sensors["machine_id"] == machine].sort_values("date")
        if model is not None:
            m = m.copy()
            m["risk"] = model.predict_proba(m[FEATURES])[:, 1]
        fig = go.Figure()
        fig.add_scatter(x=m["date"], y=m["vibration_mm_s"], name="vibration mm/s")
        fig.add_scatter(x=m["date"], y=m["temperature_c"] / 10,
                        name="temperature (°C/10)")
        if "risk" in m:
            fig.add_scatter(x=m["date"], y=m["risk"] * 10, name="failure risk ×10",
                            line=dict(color="red", width=1))
        fails = m[m["failure_within_72h"] == 1]
        fig.add_scatter(x=fails["date"], y=fails["vibration_mm_s"],
                        mode="markers", marker=dict(color="black", size=6),
                        name="pre-failure window")
        fig.update_layout(title=f"{machine}: sensor degradation vs model risk")
        st.plotly_chart(fig, width="stretch")

    if model is not None:
        latest = sensors.sort_values("date").groupby("machine_id").tail(1).copy()
        latest["risk"] = model.predict_proba(latest[FEATURES])[:, 1]
        st.subheader("Fleet risk ranking (latest reading per machine)")
        st.dataframe(latest[["machine_id", "vibration_mm_s", "temperature_c",
                             "current_a", "days_since_maintenance", "risk"]]
                     .sort_values("risk", ascending=False)
                     .style.format({"risk": "{:.0%}"})
                     .background_gradient(subset=["risk"], cmap="Reds"),
                     width="stretch", hide_index=True)


def page_simulation():
    st.title("🎲 Scenario Simulation & Cost-Benefit")
    sim_path = config.REPORTS_DIR / "simulation_scenarios.csv"
    if sim_path.exists():
        sim = pd.read_csv(sim_path)
        fig = go.Figure()
        fig.add_bar(x=sim["scenario"], y=sim["mean_oee"],
                    error_y=dict(type="data", symmetric=False,
                                 array=sim["ci_high"] - sim["mean_oee"],
                                 arrayminus=sim["mean_oee"] - sim["ci_low"]),
                    marker_color=["#7f8c8d", "#2980b9", "#27ae60", "#8e44ad"])
        fig.update_layout(title="Line 3 projected OEE by scenario "
                                "(Monte Carlo, 95% bootstrap CI)",
                          yaxis_title="OEE %")
        st.plotly_chart(fig, width="stretch")
        uplift = sim["mean_oee"].iloc[-1] - sim["mean_oee"].iloc[0]
        st.success(f"Combined SMED + PdM scenario projects a "
                   f"**+{uplift:.1f} pp OEE uplift** on Line 3.")

    st.subheader("Cost-benefit analysis (Wk 16, finance-reviewed)")
    cba = pd.DataFrame({
        "Initiative": ["SMED changeover reduction", "Predictive maintenance",
                       "Digital QC entry", "Inventory rebalancing",
                       "Demand forecasting"],
        "Annual benefit (₹L)": [9.8, 13.8, 4.6, 8.2, 3.4],
        "One-time cost (₹L)": [1.2, 3.5, 0.8, 0.4, 0.6],
        "Payback (months)": [1.5, 3.0, 2.1, 0.6, 2.1],
    })
    cba["Benefit:cost"] = (cba["Annual benefit (₹L)"]
                           / cba["One-time cost (₹L)"]).round(1)
    st.dataframe(cba, width="stretch", hide_index=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Programme benefit", "₹39.8 L / yr")
    c2.metric("Programme cost", f"₹{cba['One-time cost (₹L)'].sum():.1f} L")
    c3.metric("Benefit-cost ratio", "6.1 : 1")
    fig = px.scatter(cba, x="Payback (months)", y="Annual benefit (₹L)",
                     size="Benefit:cost", text="Initiative",
                     title="Initiative prioritisation map")
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, width="stretch")


def page_kpi():
    st.title("🎯 KPI Baseline & Data Quality")
    kpi_path = config.REPORTS_DIR / "kpi_baseline.csv"
    if kpi_path.exists():
        kpi = pd.read_csv(kpi_path)
        red = (kpi["status"] == "RED").sum()
        st.metric("KPIs below target", f"{red} of {len(kpi)}")
        st.dataframe(kpi.style.map(
            lambda v: "background-color:#fadbd8" if v == "RED"
            else ("background-color:#d5f5e3" if v == "GREEN" else ""),
            subset=["status"]), width="stretch", hide_index=True)

        kpi["gap_to_target_pct"] = (100 * (kpi["baseline"] - kpi["target"])
                                    / kpi["target"]).round(1)
        fig = px.bar(kpi.sort_values("gap_to_target_pct"),
                     x="gap_to_target_pct", y="kpi", orientation="h",
                     color="status",
                     color_discrete_map={"RED": "#d62728", "GREEN": "#2ca02c"},
                     title="Gap to target (%) — negative = below target")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Data quality monitor")
    dq_path = config.REPORTS_DIR / "data_quality_report.csv"
    if dq_path.exists():
        st.dataframe(pd.read_csv(dq_path), width="stretch", hide_index=True)
    etl_path = config.REPORTS_DIR / "etl_log.txt"
    if etl_path.exists():
        with st.expander("Latest ETL run log"):
            st.code(etl_path.read_text())


# ---------------------------------------------------------------- nav
pages = [
    st.Page(page_live, title="Live Control Tower", icon="🏭", default=True),
    st.Page(page_oee, title="OEE Analysis", icon="📊"),
    st.Page(page_downtime, title="Downtime & Pareto", icon="🔧"),
    st.Page(page_quality, title="Quality Analytics", icon="✅"),
    st.Page(page_throughput, title="Throughput & Time Series", icon="📈"),
    st.Page(page_inventory, title="Inventory Optimisation", icon="📦"),
    st.Page(page_forecast, title="Demand Forecast", icon="🔮"),
    st.Page(page_pdm, title="Predictive Maintenance", icon="🛠️"),
    st.Page(page_simulation, title="Simulation & CBA", icon="🎲"),
    st.Page(page_kpi, title="KPI & Data Quality", icon="🎯"),
]
nav = st.navigation(pages)
st.sidebar.title("Operations Control Tower")
st.sidebar.caption("Arrowcosta Technology · Operations Data Analytics\n\n"
                   "10 pages mirroring the internship's final report build")
nav.run()
