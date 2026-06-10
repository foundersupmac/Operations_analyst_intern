"""Real-time shopfloor data simulator.

Stands in for the live SAP/MES feed: every tick it appends one
5-minute production bucket per machine and one sensor reading per
machine into SQLite, using the same stochastic behaviour as the
historical generator (Line 3 availability problem, Shift B defect
effect, bearing-degradation drift before failures).

Run alongside the dashboard:
    python -m src.live_feed --interval 2
"""
import argparse
import sqlite3
import time
from datetime import datetime

import numpy as np

import config

MACHINES = [f"L{l}-M{m}" for l in range(1, 5)
            for m in range(1, config.MACHINES_PER_LINE + 1)]

DDL = """
CREATE TABLE IF NOT EXISTS live_production (
    ts TEXT, line TEXT, machine_id TEXT, shift TEXT,
    machine_speed REAL, units INTEGER, defects INTEGER, running INTEGER
);
CREATE TABLE IF NOT EXISTS live_sensors (
    ts TEXT, machine_id TEXT, vibration_mm_s REAL, temperature_c REAL,
    current_a REAL, cycle_count INTEGER, days_since_maintenance INTEGER
);
"""


def current_shift(hour):
    return "A" if 6 <= hour < 14 else ("B" if 14 <= hour < 22 else "C")


class MachineState:
    def __init__(self, machine_id, rng):
        self.id = machine_id
        self.line = f"Line {machine_id[1]}"
        self.rng = rng
        self.ttf = int(max(rng.normal(38, 12), 8))      # days to failure
        self.age_days = int(rng.integers(0, self.ttf))
        self.down_ticks = 0

    def tick(self, now):
        rng = self.rng
        self.age_days += 5 / (60 * 24)                  # 5 sim-minutes per tick

        # downtime state machine: Line 3 stops more often
        if self.down_ticks > 0:
            self.down_ticks -= 1
            running = 0
        else:
            p_stop = 0.06 if self.line == "Line 3" else 0.02
            if rng.random() < p_stop:
                self.down_ticks = int(rng.integers(2, 8))
                running = 0
            else:
                running = 1

        shift = current_shift(now.hour)
        speed = float(rng.normal(110, 6))
        units = int(speed * 5 / 60 * rng.normal(0.9, 0.04)) if running else 0
        defect_rate = (1.8 + 0.55 * (speed - 110) / 6
                       + (0.6 if shift == "B" else 0.0) + rng.normal(0, 0.45))
        defects = int(units * max(defect_rate, 0.05) / 100) if running else 0

        wear = self.age_days / self.ttf
        proximity = max(0.0, 1 - (self.ttf - self.age_days) / 5.0)
        if self.age_days >= self.ttf:                   # failure -> reset
            self.age_days, self.ttf = 0, int(max(rng.normal(38, 12), 8))
            wear = proximity = 0.0
        sensor = (
            round(float(rng.normal(2.0 + 1.5 * wear + 1.5 * proximity, 0.55)), 2),
            round(float(rng.normal(58 + 8 * wear + 5.5 * proximity, 3.2)), 1),
            round(float(rng.normal(11 + 1.5 * wear + 0.9 * proximity, 0.75)), 2),
            int(rng.normal(7000, 600)),
            int(self.age_days),
        )
        prod = (now.isoformat(timespec="seconds"), self.line, self.id, shift,
                round(speed, 1), units, defects, running)
        return prod, (now.isoformat(timespec="seconds"), self.id, *sensor)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=2.0,
                        help="seconds between ticks")
    parser.add_argument("--ticks", type=int, default=0,
                        help="stop after N ticks (0 = run forever)")
    args = parser.parse_args()

    rng = np.random.default_rng()
    machines = [MachineState(m, rng) for m in MACHINES]
    conn = sqlite3.connect(config.DB_PATH)
    conn.executescript(DDL)

    n = 0
    while True:
        now = datetime.now()
        rows = [m.tick(now) for m in machines]
        conn.executemany("INSERT INTO live_production VALUES (?,?,?,?,?,?,?,?)",
                         [r[0] for r in rows])
        conn.executemany("INSERT INTO live_sensors VALUES (?,?,?,?,?,?,?)",
                         [r[1] for r in rows])
        conn.commit()
        n += 1
        if n % 10 == 0:
            print(f"  live feed: {n} ticks ({n * len(MACHINES)} records)")
        if args.ticks and n >= args.ticks:
            break
        time.sleep(args.interval)
    conn.close()


if __name__ == "__main__":
    main()
