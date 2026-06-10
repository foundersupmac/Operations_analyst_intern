# Operations Analyst Intern Project

End-to-end operations data analytics project for a manufacturing plant,
built around the work plan of a 24-week industrial training engagement
(Operations Data Analytics, Arrowcosta Technology Pvt. Ltd., Gurugram).

Since real SAP/client data is confidential, the project ships with a
**synthetic data generator** that reproduces the documented datasets and
operational patterns (Line 3 bottleneck, Shift B defect effect, Aug–Sep
maintenance shutdown, Line 2 post-firmware bimodal throughput, dirty-data
issues), so every analysis is fully runnable and reproducible.

## Quick start

```bash
pip install -r requirements.txt
python run_all.py
```

This generates the data, runs the full pipeline and writes all outputs to
`output/` (charts, reports, trained models, Power BI export) and the
cleaned SQLite database to `data/operations.db`.

## Real-time dashboard

A live "control tower" dashboard (Streamlit + Plotly) sits on top of the
pipeline. A shopfloor feed simulator streams 5-minute production buckets
and machine sensor readings into SQLite; the dashboard auto-refreshes
every 5 seconds and scores incoming sensor data with the trained
predictive-maintenance model to raise failure alerts.

```bash
python run_all.py                      # once, to build the DB and models
python -m src.live_feed --interval 2   # terminal 1: live data feed
streamlit run dashboard/app.py         # terminal 2: dashboard
```

Dashboard sections:
- **Live tiles** — estimated OEE, availability, throughput, defect rate
  and predictive-maintenance alert count over the last 30 minutes
- **Live charts** — per-line throughput (units/min) and availability bars
- **PdM alerts** — machines the Random Forest model predicts will fail
  within 72 hours, with sensor readings and risk score
- **Analytical layer** — 12-month availability trends, downtime Pareto,
  the 12-KPI traffic-light baseline and the demand history/forecast
  comparison

## Pipeline modules (mapped to training weeks)

| Module | Training week | What it does |
|---|---|---|
| `src/data_generation.py` | 5 | Synthetic SAP PP/QM/PM/MM extracts: ~46k production orders, 22k inspections, 847 downtime events, machine sensor data, 120 SKUs, 2-year demand history |
| `src/etl_pipeline.py` | 5–6 | Extract → Validate → Clean → Load → Log into SQLite; schema/dtype enforcement |
| `src/data_quality.py` | 7 | 5-dimension audit (completeness, accuracy, consistency, timeliness, uniqueness); duplicate removal, imputation, label normalisation, IQR outliers |
| `src/kpi_framework.py` | 8 | 12 KPIs (OEE, MTTR, MTBF, FPY, …) with traffic-light status vs targets and industry benchmarks |
| `src/eda.py` | 6 | Profiling, distributions (Line 2 bimodality), daily output trend, speed↔defect correlation, shift boxplots |
| `src/time_series.py` | 9 | Rolling averages, STL decomposition, ADF stationarity tests, daily OEE trends per line |
| `src/oee_analysis.py` | 10 | OEE decomposition by line (Availability × Performance × Quality), downtime Pareto, shift comparison |
| `src/statistical_models.py` | 11–12 | OLS defect-rate regression with HC3 robust SEs (test R² ≈ 0.73), one-way ANOVA + Tukey HSD (Shift B effect) |
| `src/inventory.py` | 14 | EOQ (Wilson formula), safety stock @95% service level, reorder points for 120 SKUs; over/understock actions |
| `src/simulation.py` | 15 | SimPy discrete-event simulation of Line 3 calibrated to historical availability; Monte Carlo over SMED / PdM / combined scenarios with bootstrap CIs |
| `src/forecasting.py` | 18 | XGBoost demand forecast (18 engineered features, beats SARIMA and naive benchmarks on a 60-day hold-out) |
| `src/pdm_model.py` | 19 | Random Forest predictive-maintenance classifier; SMOTE inside the CV pipeline (no leakage); test F1 ≈ 0.83, AUC ≈ 0.99 |
| `src/star_schema.py` | 16 | Power BI star-schema export: FactProduction + DimDate/DimMachine/DimLine/DimShift/DimMaterial/DimOperator |
| `src/excel_report.py` | 17 | Automated 6-sheet weekly Excel report (openpyxl) with embedded chart — schedulable via cron/Task Scheduler |

## Headline findings reproduced by the pipeline

- Line 3 is the facility bottleneck: OEE ≈ 60% (lowest), driven by
  **availability** losses; spindle-bearing failures account for ~half of
  its breakdown hours.
- Breakdowns are the top downtime category by total hours (Pareto).
- Machine speed correlates strongly with defect rate (r ≈ 0.77), and
  Shift B runs a significantly higher defect rate (ANOVA + Tukey HSD).
- Simulation: SMED + PdM combined lifts projected Line 3 OEE from
  ~64% to ~68% with tight bootstrap confidence intervals.
- XGBoost beats SARIMA and naive baselines on demand MAPE; payment-cycle
  and day-of-week features dominate importance.

## Repository layout

```
config.py          # paths, plant structure, KPI targets
run_all.py         # orchestrates all 14 steps in dependency order
src/               # one module per analysis area (see table above)
data/              # generated CSVs + operations.db (gitignored)
output/            # charts/, models/, reports/, powerbi_export/ (gitignored)
```
