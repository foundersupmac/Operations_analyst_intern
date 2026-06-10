"""Line 3 discrete-event simulation (week 15) using SimPy.

Calibrated to the historical breakdown/changeover profile, then run as a
Monte Carlo over three improvement scenarios:
  A: SMED only      (changeover 47 -> 22 min)
  B: PdM only       (breakdown frequency -40%, duration -25%)
  C: SMED + PdM combined
"""
import numpy as np
import pandas as pd
import simpy

import config
from src.etl_pipeline import read_table

SIM_DAYS = 90
ITERATIONS = 200          # Monte Carlo iterations per scenario
SHIFT_MIN = 8 * 60 * 3    # minutes of planned time per day (3 shifts)


def line3_params():
    """Calibrate stochastic inputs to the historical Line 3 profile.

    Event logs undercount total lost time (uncoded/minor stops), so the
    event rates are scaled such that the simulated baseline availability
    matches the availability observed in the production table.
    """
    from src.kpi_framework import oee_components
    production = oee_components(read_table("production"))
    l3_prod = production[production["line"] == "Line 3"]
    hist_avail = l3_prod["availability"].mean()
    target_down_min = (1 - hist_avail) * SHIFT_MIN     # lost minutes/day

    downtime = read_table("downtime")
    l3 = downtime[downtime["line"] == "Line 3"]
    by_cause = l3.groupby("cause_code")["duration_hrs"].sum()
    bd_share = by_cause.get("Breakdown", 0) / by_cause.sum()
    co_share = by_cause.get("Changeover", 0) / by_cause.sum()
    other_share = 1 - bd_share - co_share

    bd_mean_min = l3.loc[l3["cause_code"] == "Breakdown", "duration_hrs"].mean() * 60
    co_mean_min = l3.loc[l3["cause_code"] == "Changeover", "duration_hrs"].mean() * 60
    other_mean_min = 20.0                              # minor/uncoded stops

    return {
        "bd_per_day": bd_share * target_down_min / bd_mean_min,
        "bd_mean_min": bd_mean_min,
        "co_per_day": co_share * target_down_min / co_mean_min,
        "co_mean_min": co_mean_min,
        "other_per_day": other_share * target_down_min / other_mean_min,
        "other_mean_min": other_mean_min,
        "perf": l3_prod["performance"].mean(),
        "quality": l3_prod["quality"].mean(),
    }


def run_once(params, rng, smed=False, pdm=False):
    bd_rate = params["bd_per_day"] * (0.6 if pdm else 1.0)
    bd_dur = params["bd_mean_min"] * (0.75 if pdm else 1.0)
    co_dur = 22.0 if smed else params["co_mean_min"]

    env = simpy.Environment()
    state = {"run_min": 0.0}

    def machine(env):
        while True:
            # competing risks: next breakdown, changeover or minor stop
            t_bd = rng.exponential(SHIFT_MIN / max(bd_rate, 1e-6))
            t_co = rng.exponential(SHIFT_MIN / max(params["co_per_day"], 1e-6))
            t_ot = rng.exponential(SHIFT_MIN / max(params["other_per_day"], 1e-6))
            run = min(t_bd, t_co, t_ot)
            yield env.timeout(run)
            state["run_min"] += run
            if run == t_bd:
                stop = rng.exponential(bd_dur)
            elif run == t_co:
                stop = rng.exponential(co_dur)
            else:
                stop = rng.exponential(params["other_mean_min"])
            yield env.timeout(stop)

    env.process(machine(env))
    total = SIM_DAYS * SHIFT_MIN
    env.run(until=total)
    availability = state["run_min"] / total
    return availability * params["perf"] * params["quality"] * 100


def scenario(name, params, rng, **kwargs):
    oees = np.array([run_once(params, rng, **kwargs) for _ in range(ITERATIONS)])
    boot = np.array([rng.choice(oees, len(oees)).mean() for _ in range(1000)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"  {name}: OEE {oees.mean():.1f}% [95% CI {lo:.1f}-{hi:.1f}%]")
    return {"scenario": name, "mean_oee": round(oees.mean(), 1),
            "ci_low": round(lo, 1), "ci_high": round(hi, 1)}


def main():
    rng = np.random.default_rng(config.RANDOM_SEED)
    params = line3_params()
    results = [
        scenario("Baseline", params, rng),
        scenario("A: SMED only", params, rng, smed=True),
        scenario("B: PdM only", params, rng, pdm=True),
        scenario("C: SMED + PdM", params, rng, smed=True, pdm=True),
    ]
    df = pd.DataFrame(results)
    df.to_csv(config.REPORTS_DIR / "simulation_scenarios.csv", index=False)
    return df


if __name__ == "__main__":
    main()
