"""Synthetic SAP-style operational data generator.

Produces the datasets described in the training diary (weeks 5-7):
  - production.csv : ~48,000 production-order line records (SAP PP)
  - quality.csv    : ~22,000 inspection records (SAP QM)
  - downtime.csv   : 847 downtime events (SAP PM)
  - sensors.csv    : machine-day sensor aggregates for the PdM model
  - inventory.csv  : 120 SKU master with demand/cost/lead-time data (SAP MM)

Known operational patterns are embedded so the downstream analytics
recover the findings documented in the diary:
  - Line 3 is the bottleneck (low availability, OEE ~61% from Sep 2025)
  - Shift B runs a higher defect rate
  - Aug-Sep 2025 maintenance shutdown dip in output
  - Line 2 throughput turns bimodal after a July 2025 firmware update
  - Machine speed correlates with defect rate (r ~ 0.67)
  - Deliberate dirty data: missing cause codes (~14%), 312 duplicate
    order IDs, mixed date formats, inconsistent labels, a few nulls.
"""
import numpy as np
import pandas as pd

import config


def _shift_dates(rng):
    days = pd.date_range(config.PERIOD_START, config.PERIOD_END, freq="D")
    return days


def generate_production(rng):
    days = _shift_dates(rng)
    rows = []
    order_no = 100000
    for day in days:
        # Plant-wide maintenance shutdown dip mid Aug - mid Sep 2025
        shutdown = pd.Timestamp("2025-08-15") <= day <= pd.Timestamp("2025-09-10")
        for line in config.LINES:
            for shift in config.SHIFTS:
                for m in range(1, config.MACHINES_PER_LINE + 1):
                  # several production orders run per machine per shift
                  n_orders = int(rng.integers(3, 5))
                  slot_hrs = config.SHIFT_HOURS / n_orders
                  for _ in range(n_orders):
                    order_no += 1
                    machine = f"{line.replace('Line ', 'L')}-M{m}"
                    grade = rng.choice(config.MATERIAL_GRADES, p=[0.5, 0.3, 0.2])

                    # Machine speed (units/hr). Line 2 firmware update in
                    # July 2025 creates a second, faster operating mode.
                    base_speed = 110.0
                    if line == "Line 2" and day >= pd.Timestamp("2025-07-15"):
                        base_speed = rng.choice([110.0, 128.0], p=[0.45, 0.55])
                    speed = rng.normal(base_speed, 6.0)

                    # Availability losses concentrate on Line 3, worsening
                    # from September 2025 (the diary's bottleneck finding).
                    avail = rng.normal(0.88, 0.04)
                    if line == "Line 3":
                        avail = rng.normal(0.80, 0.05)
                        if day >= pd.Timestamp("2025-09-01"):
                            avail = rng.normal(0.72, 0.05)
                    if shutdown:
                        avail *= rng.uniform(0.35, 0.6)
                    avail = float(np.clip(avail, 0.2, 0.99))

                    run_hours = slot_hrs * avail
                    perf = float(np.clip(rng.normal(0.90, 0.04), 0.6, 1.0))
                    units = int(run_hours * speed * perf)

                    # Defects driven by speed, material grade, shift B and
                    # time since maintenance (added in sensors join).
                    speed_z = (speed - 110.0) / 6.0
                    defect_rate = (
                        1.8
                        + 0.55 * speed_z
                        + (0.6 if shift == "B" else 0.0)
                        + (0.4 if grade == "Grade-3" else 0.0)
                        + rng.normal(0, 0.45)
                    )
                    defect_rate = max(defect_rate, 0.05)
                    defects = int(units * defect_rate / 100)

                    rows.append({
                        "order_id": f"PO{order_no}",
                        "date": day,
                        "line": line,
                        "machine_id": machine,
                        "shift": shift,
                        "material_grade": grade,
                        "machine_speed": round(speed, 1),
                        "planned_time_hrs": round(slot_hrs, 2),
                        "run_time_hrs": round(run_hours, 2),
                        "units_produced": units,
                        "defect_count": defects,
                    })
    df = pd.DataFrame(rows)

    # --- inject dirty data (cleaned again in week-7 module) ---
    # 312 duplicate order ids from the ERP migration
    dupes = df.sample(312, random_state=1).copy()
    df = pd.concat([df, dupes], ignore_index=True)
    # a handful of missing defect counts
    df.loc[df.sample(5, random_state=2).index, "defect_count"] = np.nan
    # inconsistent shift labels
    idx = df.sample(frac=0.03, random_state=3).index
    df.loc[idx, "shift"] = df.loc[idx, "shift"].map(
        {"A": "shift a", "B": "shift b", "C": "shift c"})
    # mixed date formats are simulated downstream by exporting as string
    df["date"] = df["date"].dt.strftime("%d/%m/%Y")
    return df


def generate_quality(production, rng):
    base = production.drop_duplicates("order_id").sample(22000, random_state=4)
    df = pd.DataFrame({
        "inspection_lot": [f"IL{600000 + i}" for i in range(len(base))],
        "order_id": base["order_id"].values,
        "date": base["date"].values,
        "line": base["line"].values,
        "shift": base["shift"].values,
        "sample_size": rng.integers(20, 80, len(base)),
    })
    pr = base["defect_count"].fillna(0).values / base["units_produced"].clip(lower=1).values
    df["defects_found"] = rng.binomial(df["sample_size"], np.clip(pr * 1.1, 0, 0.5))
    df["usage_decision"] = np.where(
        df["defects_found"] / df["sample_size"] > 0.05, "Rejected", "Accepted")
    # inconsistent unit labels (cleaned in week 7)
    df["plant_unit"] = rng.choice(["Unit A", "A", "Unit B", "B"], len(df), p=[0.3, 0.25, 0.25, 0.2])
    return df


def generate_downtime(rng):
    days = _shift_dates(rng)
    cats = config.DOWNTIME_CATEGORIES
    # Frequency mix tuned so Breakdown ~42% and Changeover ~22% of hours
    probs = [0.30, 0.21, 0.13, 0.10, 0.11, 0.15]
    mean_dur = {"Breakdown": 2.0, "Changeover": 0.78, "Material Shortage": 1.2,
                "Planned Maintenance": 1.6, "Quality Stop": 0.8, "Minor Stop": 0.3}
    rows = []
    for i in range(847):
        day = rng.choice(days)
        cat = rng.choice(cats, p=probs)
        # Line 3 takes a disproportionate share of breakdowns
        line = rng.choice(config.LINES, p=[0.18, 0.20, 0.42, 0.20]) \
            if cat == "Breakdown" else rng.choice(config.LINES)
        dur = max(0.1, rng.exponential(mean_dur[cat]) * 0.6 + mean_dur[cat] * 0.4)
        cause = cat
        # Line 3 breakdowns: 38% are spindle bearing failures (week 11 RCA)
        detail = "Spindle bearing failure" if (
            cat == "Breakdown" and line == "Line 3" and rng.random() < 0.38
        ) else f"{cat} event"
        rows.append({
            "event_id": f"DT{i + 1:04d}",
            "date": pd.Timestamp(day),
            "line": line,
            "shift": rng.choice(config.SHIFTS),
            "cause_code": cause,
            "cause_detail": detail,
            "duration_hrs": round(float(dur), 2),
        })
    df = pd.DataFrame(rows)
    # ~14% missing cause codes, 3 missing durations (week 7 findings)
    df.loc[df.sample(frac=0.14, random_state=5).index, "cause_code"] = np.nan
    df.loc[df.sample(3, random_state=6).index, "duration_hrs"] = np.nan
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df


def generate_sensors(rng):
    """Daily sensor aggregates per machine, with failure-within-72h label.

    Each machine degrades towards a stochastic failure date; vibration,
    temperature and current drift upward as failure approaches (the
    classic bearing-degradation signature), giving the PdM model a
    learnable but noisy signal. ~8% of machine-days fall within the
    72-hour pre-failure window.
    """
    days = _shift_dates(rng)
    machines = [f"L{l}-M{m}" for l in range(1, 5)
                for m in range(1, config.MACHINES_PER_LINE + 1)]
    rows = []
    for machine in machines:
        ttf = int(max(rng.normal(38, 12), 8))     # days until next failure
        days_since_maint = 0
        for day in days:
            days_since_maint += 1
            wear = days_since_maint / ttf
            # degradation accelerates in the final days before failure
            proximity = max(0.0, 1 - (ttf - days_since_maint) / 5.0)
            vibration = rng.normal(2.0 + 1.5 * wear + 1.5 * proximity, 0.55)
            temperature = rng.normal(58 + 8 * wear + 5.5 * proximity, 3.2)
            current = rng.normal(11 + 1.5 * wear + 0.9 * proximity, 0.75)
            cycles = int(rng.normal(7000, 600))
            label = int(ttf - days_since_maint <= 3)
            rows.append({
                "date": day, "machine_id": machine,
                "vibration_mm_s": round(float(vibration), 2),
                "temperature_c": round(float(temperature), 1),
                "current_a": round(float(current), 2),
                "cycle_count": cycles,
                "days_since_maintenance": days_since_maint,
                "failure_within_72h": label,
            })
            if days_since_maint >= ttf:           # failure -> maintenance reset
                days_since_maint = 0
                ttf = int(max(rng.normal(38, 12), 8))
    return pd.DataFrame(rows)


def generate_inventory(rng):
    skus = [f"SKU-{i:03d}" for i in range(1, config.N_SKUS + 1)]
    annual_demand = rng.lognormal(7.2, 0.9, config.N_SKUS).astype(int) + 100
    df = pd.DataFrame({
        "sku": skus,
        "annual_demand_units": annual_demand,
        "demand_std_daily": np.round(annual_demand / 365 * rng.uniform(0.2, 0.6, config.N_SKUS), 2),
        "unit_cost_inr": np.round(rng.lognormal(5.5, 0.8, config.N_SKUS), 2),
        "ordering_cost_inr": np.round(rng.uniform(800, 2500, config.N_SKUS), 0),
        "holding_cost_pct": np.round(rng.uniform(0.18, 0.28, config.N_SKUS), 2),
        "lead_time_days": rng.integers(3, 35, config.N_SKUS),
        "current_stock_units": 0,
    })
    daily = df["annual_demand_units"] / 365
    # reactive replenishment: some SKUs heavily overstocked, some near stockout
    mode = rng.choice(["over", "under", "ok"], config.N_SKUS, p=[0.30, 0.10, 0.60])
    stock = np.where(mode == "over", daily * rng.uniform(95, 200, config.N_SKUS),
             np.where(mode == "under", daily * rng.uniform(0.5, 3, config.N_SKUS),
                      daily * rng.uniform(15, 60, config.N_SKUS)))
    df["current_stock_units"] = stock.astype(int)
    return df


def generate_demand_series(rng):
    """Daily demand history for the forecasting model (week 18)."""
    days = pd.date_range("2024-02-01", config.PERIOD_END, freq="D")
    t = np.arange(len(days))
    # non-sinusoidal weekly profile typical of B2B order books
    weekday_profile = np.array([1.10, 1.18, 1.05, 0.98, 1.12, 0.62, 0.45])
    weekly = weekday_profile[days.dayofweek]
    monthly = 1 + 0.06 * np.sin(2 * np.pi * days.dayofyear / 30.4)
    trend = 1 + 0.00045 * t
    # large B2B batch orders follow customer payment cycles (10th/25th
    # of month) and month-end pushes -- a monthly calendar effect a
    # weekly-seasonal SARIMA cannot represent
    batch_prob = np.where(np.isin(days.day, (10, 25)), 0.9,
                  np.where(days.is_month_end, 0.5, 0.01))
    batch = (rng.random(len(days)) < batch_prob) * rng.uniform(1800, 2600, len(days))
    demand = 4000 * weekly * monthly * trend + batch + rng.normal(0, 180, len(days))
    return pd.DataFrame({"date": days, "demand_units": np.maximum(demand, 0).astype(int)})


def main():
    rng = np.random.default_rng(config.RANDOM_SEED)
    production = generate_production(rng)
    datasets = {
        "production.csv": production,
        "quality.csv": generate_quality(production, rng),
        "downtime.csv": generate_downtime(rng),
        "sensors.csv": generate_sensors(rng),
        "inventory.csv": generate_inventory(rng),
        "demand_history.csv": generate_demand_series(rng),
    }
    for name, df in datasets.items():
        path = config.DATA_DIR / name
        df.to_csv(path, index=False)
        print(f"  wrote {name}: {len(df):,} rows")
    return datasets


if __name__ == "__main__":
    main()
