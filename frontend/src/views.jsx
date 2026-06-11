import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area, BarChart, Bar,
  ComposedChart, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, Cell,
} from 'recharts'
import { useApi, LINE_COLORS, PALETTE } from './api'
import { Tile, Card, Finding, RiskBar, Table, Loading } from './components'

const grid = <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
const axis = { stroke: 'rgba(255,255,255,0.12)', tickLine: false }

/* ------------------------------------------------ 1. live control tower */
export function LiveView() {
  const { data, error } = useApi('/api/live', 5000)
  if (!data) return <Loading error={error} />
  if (!data.ok) return <div className="skeleton">Live feed offline — run <code>python -m src.live_feed --interval 2</code></div>
  const t = data.tiles
  return (
    <>
      <div className="grid tiles">
        <Tile label="Live OEE (est.)" value={t.oee} suffix="%" tone="accent" delta="availability × perf × quality" />
        <Tile label="Availability 30 min" value={t.availability} suffix="%" tone={t.availability >= 80 ? 'good' : 'bad'} />
        <Tile label="Units · 30 min" value={t.units.toLocaleString()} />
        <Tile label="Defect rate" value={t.defect_rate} suffix="%" tone={t.defect_rate <= 2 ? 'good' : 'bad'} />
        <Tile label="PdM alerts" value={t.alerts} tone={t.alerts ? 'bad' : 'good'} delta={t.alerts ? 'failure < 72 h predicted' : 'all machines clear'} />
      </div>
      {data.pdm_alerts.length > 0 && (
        <div className="alert-banner" style={{ marginTop: 16 }}>
          ⚠️ Predictive maintenance: {data.pdm_alerts.map((a) => a.machine_id).join(', ')} predicted to fail within 72 hours
        </div>
      )}
      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card title="Throughput by line — units/min, last 30 min">
          <ResponsiveContainer width="100%" height={290}>
            <LineChart data={data.throughput}>
              {grid}<XAxis dataKey="t" {...axis} /><YAxis {...axis} /><Tooltip /><Legend />
              {Object.keys(LINE_COLORS).map((l) => (
                <Line key={l} dataKey={l} stroke={LINE_COLORS[l]} dot={false} strokeWidth={2} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Availability by line — last 30 min">
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={data.line_availability}>
              {grid}<XAxis dataKey="line" {...axis} /><YAxis domain={[0, 100]} {...axis} /><Tooltip />
              <Bar dataKey="value" radius={[8, 8, 0, 0]} isAnimationActive={false}>
                {data.line_availability.map((d) => (
                  <Cell key={d.line} fill={d.value >= 80 ? '#34d399' : '#f87171'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      {data.pdm_alerts.length > 0 && (
        <Card title="Machines at risk" style={{ marginTop: 16 }}>
          <Table
            columns={['machine_id', 'vibration_mm_s', 'temperature_c', 'current_a', 'days_since_maintenance', 'risk']}
            rows={data.pdm_alerts}
            render={{ risk: (v) => <RiskBar value={v} /> }}
          />
        </Card>
      )}
    </>
  )
}

/* ------------------------------------------------ 2. OEE */
export function OeeView() {
  const { data, error } = useApi('/api/oee')
  if (!data) return <Loading error={error} />
  return (
    <>
      <div className="grid tiles">
        {data.decomposition.map((d) => (
          <Tile key={d.line} label={`${d.line} OEE`} value={d.oee} suffix="%"
            tone={d.oee >= 65 ? 'good' : 'bad'}
            delta={`${(d.oee - 75).toFixed(1)} pp vs 75% target`} />
        ))}
      </div>
      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card title="Weekly OEE trend by line (%)">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.trend}>
              {grid}<XAxis dataKey="date" {...axis} minTickGap={40} /><YAxis domain={[40, 90]} {...axis} /><Tooltip /><Legend />
              <ReferenceLine y={65} stroke="#f87171" strokeDasharray="5 4" label={{ value: '65% threshold', fill: '#f87171', fontSize: 11 }} />
              {Object.keys(LINE_COLORS).map((l) => (
                <Line key={l} dataKey={l} stroke={LINE_COLORS[l]} dot={false} strokeWidth={2} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="OEE decomposition — Availability × Performance × Quality">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.decomposition}>
              {grid}<XAxis dataKey="line" {...axis} /><YAxis domain={[0, 100]} {...axis} /><Tooltip /><Legend />
              <Bar dataKey="availability" fill="#22d3ee" radius={[6, 6, 0, 0]} />
              <Bar dataKey="performance" fill="#818cf8" radius={[6, 6, 0, 0]} />
              <Bar dataKey="quality" fill="#34d399" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div style={{ marginTop: 16 }}>
        <Finding><b>Finding (Wk 9–10):</b> Line 3 runs consistently below the 65% threshold since Sep 2025 — availability is the dominant loss driver, confirming it as the facility bottleneck.</Finding>
      </div>
    </>
  )
}

/* ------------------------------------------------ 3. downtime */
export function DowntimeView() {
  const { data, error } = useApi('/api/downtime')
  if (!data) return <Loading error={error} />
  const s = data.summary
  return (
    <>
      <div className="grid tiles">
        <Tile label="Events · 12 months" value={s.events.toLocaleString()} />
        <Tile label="Hours lost" value={s.hours.toLocaleString()} tone="bad" />
        <Tile label="MTTR (breakdowns)" value={s.mttr} suffix=" h" />
        <Tile label="Breakdown share" value={s.breakdown_share} suffix="%" tone="accent" />
      </div>
      <div className="grid two-col" style={{ marginTop: 16 }}>
        <Card title="Downtime Pareto — hours by cause with cumulative %">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data.pareto}>
              {grid}<XAxis dataKey="cause_code" {...axis} interval={0} angle={-18} dy={8} />
              <YAxis yAxisId="l" {...axis} /><YAxis yAxisId="r" orientation="right" domain={[0, 100]} {...axis} />
              <Tooltip /><Legend />
              <Bar yAxisId="l" dataKey="hours" fill="#22d3ee" radius={[6, 6, 0, 0]} />
              <Line yAxisId="r" dataKey="cum_pct" stroke="#fbbf24" strokeWidth={2} dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Hours lost by line">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.by_line} layout="vertical">
              <CartesianGrid stroke="rgba(255,255,255,0.05)" horizontal={false} />
              <XAxis type="number" {...axis} /><YAxis type="category" dataKey="line" width={60} {...axis} /><Tooltip />
              <Bar dataKey="hours" radius={[0, 8, 8, 0]}>
                {data.by_line.map((d) => (
                  <Cell key={d.line} fill={LINE_COLORS[d.line] || '#94a3b8'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div style={{ marginTop: 16 }}>
        <Finding><b>RCA (Wk 11):</b> spindle-bearing failures dominate Line 3 breakdown hours — 5-Why traced the root cause to a missing ECN process linking production-speed changes to maintenance SOP reviews. SMED analysis showed 67% of changeover time is externalisable (47 → 22 min target).</Finding>
      </div>
      <Card title="Longest downtime events" style={{ marginTop: 16 }}>
        <Table columns={['event_id', 'date', 'line', 'cause_code', 'cause_detail', 'duration_hrs']} rows={data.top_events} />
      </Card>
    </>
  )
}

/* ------------------------------------------------ 4. quality */
export function QualityView() {
  const { data, error } = useApi('/api/quality')
  if (!data) return <Loading error={error} />
  const grades = [...new Set(data.scatter.map((d) => d.material_grade))]
  return (
    <>
      <div className="grid tiles">
        <Tile label="First-pass yield" value={data.fpy} suffix="%" tone={data.fpy >= 96 ? 'good' : 'bad'} delta="target 96%" />
        <Tile label="Avg defect rate" value={data.avg_defect_rate} suffix="%" />
        <Tile label="Shift B premium" value={(data.by_shift.find((s) => s.shift === 'B')?.mean - data.by_shift.find((s) => s.shift === 'A')?.mean).toFixed(2)} suffix=" pp" tone="bad" delta="ANOVA p < 0.001 (Tukey HSD)" />
      </div>
      <div className="grid equal-col" style={{ marginTop: 16 }}>
        <Card title="Machine speed vs defect rate — r ≈ 0.77">
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart>
              {grid}<XAxis dataKey="machine_speed" name="speed" {...axis} domain={['auto', 'auto']} />
              <YAxis dataKey="defect_rate" name="defect %" {...axis} /><Tooltip /><Legend />
              {grades.map((g, i) => (
                <Scatter key={g} name={g} data={data.scatter.filter((d) => d.material_grade === g)}
                  fill={PALETTE[i]} opacity={0.45} isAnimationActive={false} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Mean defect rate by shift (%)">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.by_shift}>
              {grid}<XAxis dataKey="shift" {...axis} /><YAxis {...axis} /><Tooltip />
              <Bar dataKey="mean" radius={[8, 8, 0, 0]}>
                {data.by_shift.map((d) => (
                  <Cell key={d.shift} fill={d.shift === 'B' ? '#f87171' : '#22d3ee'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card title={`Daily defect-rate control chart — mean ${data.mean}%, UCL ${data.ucl}%`} style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data.control_chart}>
            {grid}<XAxis dataKey="date" {...axis} minTickGap={50} /><YAxis {...axis} /><Tooltip />
            <ReferenceLine y={data.mean} stroke="#34d399" strokeDasharray="4 4" />
            <ReferenceLine y={data.ucl} stroke="#f87171" strokeDasharray="4 4" />
            <ReferenceLine y={data.lcl} stroke="#f87171" strokeDasharray="4 4" />
            <Line dataKey="rate" stroke="#818cf8" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      </Card>
    </>
  )
}

/* ------------------------------------------------ 5. throughput */
export function ThroughputView() {
  const { data, error } = useApi('/api/throughput')
  if (!data) return <Loading error={error} />
  return (
    <>
      <Card title="Daily production output with 7 / 28-day rolling averages">
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data.daily}>
            {grid}<XAxis dataKey="date" {...axis} minTickGap={50} /><YAxis {...axis} /><Tooltip /><Legend />
            <Area dataKey="units" fill="rgba(34,211,238,0.08)" stroke="rgba(34,211,238,0.35)" strokeWidth={1} />
            <Line dataKey="avg7" stroke="#818cf8" dot={false} strokeWidth={2} />
            <Line dataKey="avg28" stroke="#fbbf24" dot={false} strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>
      <div className="grid equal-col" style={{ marginTop: 16 }}>
        <Card title="Average output by weekday — weekly seasonality">
          <ResponsiveContainer width="100%" height={270}>
            <BarChart data={data.weekday}>
              {grid}<XAxis dataKey="dow" {...axis} tickFormatter={(d) => d.slice(0, 3)} /><YAxis {...axis} /><Tooltip />
              <Bar dataKey="units_produced" fill="#22d3ee" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Line 2 speed distribution — bimodal after Jul-2025 firmware">
          <ResponsiveContainer width="100%" height={270}>
            <AreaChart data={data.line2_hist.filter((d) => d.period === 'post')}>
              {grid}<XAxis dataKey="speed" {...axis} /><YAxis {...axis} /><Tooltip />
              <Area dataKey="count" name="post-firmware" stroke="#818cf8" fill="rgba(129,140,248,0.25)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <div style={{ marginTop: 16 }}>
        <Finding><b>Finding (Wk 6, 9):</b> the Aug–Sep dip is the planned maintenance shutdown, not demand loss. ADF tests confirm stationarity after first differencing; STL shows a strong weekly cycle. Line 2's bimodal speed traces to the July 2025 firmware update found in the IT change log.</Finding>
      </div>
    </>
  )
}

/* ------------------------------------------------ 6. inventory */
export function InventoryView() {
  const { data, error } = useApi('/api/inventory')
  const [tab, setTab] = useState('actions')
  if (!data) return <Loading error={error} />
  if (!data.ok) return <div className="skeleton">{data.message}</div>
  const s = data.summary
  const rows = tab === 'actions' ? data.skus.filter((r) => r.action !== 'OK') : data.skus
  return (
    <>
      <div className="grid tiles">
        <Tile label="SKUs analysed" value={s.skus} />
        <Tile label="Overstocked > 90 d" value={s.overstocked} tone="bad" />
        <Tile label="Excess value" value={`₹${s.excess_lakh} L`} tone="bad" />
        <Tile label="Stockout risk" value={s.stockout_risk} tone="bad" delta="below safety stock" />
      </div>
      <Card title="SKU positioning — days of supply vs unit cost (₹, log)" style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart>
            {grid}<XAxis dataKey="days_of_supply" name="days of supply" {...axis} />
            <YAxis dataKey="unit_cost_inr" name="unit cost" scale="log" domain={['auto', 'auto']} {...axis} />
            <Tooltip /><Legend />
            <ReferenceLine x={90} stroke="#f87171" strokeDasharray="5 4" label={{ value: '90-day limit', fill: '#f87171', fontSize: 11 }} />
            {[['OK', '#34d399'], ['REDUCE (>90d supply)', '#fbbf24'], ['URGENT REORDER', '#f87171']].map(([a, c]) => (
              <Scatter key={a} name={a} data={data.skus.filter((d) => d.action === a)} fill={c} opacity={0.7} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </Card>
      <Card style={{ marginTop: 16 }}
        title="EOQ · safety stock · reorder points"
        right={
          <span className="seg">
            <button className={tab === 'actions' ? 'on' : ''} onClick={() => setTab('actions')}>Action list</button>
            <button className={tab === 'all' ? 'on' : ''} onClick={() => setTab('all')}>All 120 SKUs</button>
          </span>
        }>
        <Table
          columns={['sku', 'annual_demand_units', 'eoq_units', 'safety_stock', 'reorder_point', 'current_stock_units', 'days_of_supply', 'action']}
          rows={rows.slice(0, 40)}
          render={{
            action: (v) => <span className={`pill ${v === 'OK' ? 'green' : v.startsWith('REDUCE') ? 'amber' : 'red'}`}>{v}</span>,
          }}
        />
      </Card>
    </>
  )
}

/* ------------------------------------------------ 7. forecast */
export function ForecastView() {
  const { data, error } = useApi('/api/forecast')
  if (!data) return <Loading error={error} />
  const best = data.comparison.length
    ? data.comparison.reduce((a, b) => (a.mape_pct < b.mape_pct ? a : b)) : null
  return (
    <>
      <div className="grid tiles">
        {data.comparison.map((m) => (
          <Tile key={m.model} label={`${m.model} MAPE`} value={m.mape_pct} suffix="%"
            tone={best && m.model === best.model ? 'good' : ''}
            delta={best && m.model === best.model ? 'selected for production' : '60-day hold-out'} />
        ))}
      </div>
      <Card title="Daily demand — last 180 days (payment-cycle spikes on the 10th/25th)" style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data.history}>
            {grid}<XAxis dataKey="date" {...axis} minTickGap={50} /><YAxis {...axis} domain={['auto', 'auto']} /><Tooltip /><Legend />
            <Area dataKey="demand_units" name="demand" stroke="#22d3ee" strokeWidth={1.5} fill="rgba(34,211,238,0.08)" />
            <Scatter data={data.history.filter((d) => d.payment_cycle)} dataKey="demand_units" name="payment-cycle day" fill="#f87171" />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>
      <div style={{ marginTop: 16 }}>
        <Finding><b>Method (Wk 18):</b> 18 engineered features — lags, rolling statistics, calendar fields and B2B payment-cycle flags — tuned with rolling time-series cross-validation. XGBoost selected over SARIMA and naive baselines on the 60-day hold-out; retraining script monitors MAPE drift.</Finding>
      </div>
    </>
  )
}

/* ------------------------------------------------ 8. predictive maintenance */
export function PdmView() {
  const { data, error } = useApi('/api/pdm')
  const [machine, setMachine] = useState(null)
  const sel = machine || (data?.fleet[0]?.machine_id ?? null)
  const detail = useApi(sel ? `/api/pdm/machine/${sel}` : null)
  if (!data) return <Loading error={error} />
  return (
    <>
      <div className="grid two-col">
        <Card title="Sensor degradation vs model risk"
          right={
            <select value={sel || ''} onChange={(e) => setMachine(e.target.value)}>
              {data.fleet.map((f) => <option key={f.machine_id}>{f.machine_id}</option>)}
            </select>
          }>
          {detail.data ? (
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={detail.data.series}>
                {grid}<XAxis dataKey="date" {...axis} minTickGap={50} />
                <YAxis yAxisId="l" {...axis} /><YAxis yAxisId="r" orientation="right" domain={[0, 1]} {...axis} />
                <Tooltip /><Legend />
                <Line yAxisId="l" dataKey="vibration_mm_s" stroke="#22d3ee" dot={false} strokeWidth={1.5} />
                <Area yAxisId="r" dataKey="risk" stroke="#f87171" fill="rgba(248,113,113,0.15)" strokeWidth={1.5} />
                <Scatter yAxisId="l" data={detail.data.series.filter((d) => d.failure_within_72h === 1)}
                  dataKey="vibration_mm_s" name="pre-failure window" fill="#fbbf24" />
              </ComposedChart>
            </ResponsiveContainer>
          ) : <Loading />}
        </Card>
        <Card title="Model card — Random Forest v1.0">
          <div className="mono">{`• 200 trees, SMOTE inside CV pipeline (no leakage)
• Label: failure within 72 h  ·  recommended horizon 72 h
• 5-fold stratified CV F1 ≈ 0.79

${data.report}`}</div>
        </Card>
      </div>
      <Card title="Fleet risk ranking — latest sensor reading per machine" style={{ marginTop: 16 }}>
        <Table
          columns={['machine_id', 'vibration_mm_s', 'temperature_c', 'current_a', 'days_since_maintenance', 'risk']}
          rows={data.fleet}
          render={{ risk: (v) => (v == null ? '—' : <RiskBar value={v} />) }}
        />
      </Card>
    </>
  )
}

/* ------------------------------------------------ 9. simulation & CBA */
export function SimulationView() {
  const { data, error } = useApi('/api/simulation')
  if (!data) return <Loading error={error} />
  const base = data.scenarios[0]?.mean_oee
  const combined = data.scenarios.at(-1)?.mean_oee
  return (
    <>
      <div className="grid tiles">
        <Tile label="Programme benefit" value="₹39.8 L" delta="per year, finance-reviewed" tone="accent" />
        <Tile label="Benefit : cost" value={data.programme.ratio} tone="good" />
        {base != null && <Tile label="Line 3 OEE uplift" value={`+${(combined - base).toFixed(1)}`} suffix=" pp" tone="good" delta="SMED + PdM combined" />}
      </div>
      <div className="grid equal-col" style={{ marginTop: 16 }}>
        <Card title="Line 3 projected OEE by scenario — Monte Carlo, 95% bootstrap CI">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.scenarios}>
              {grid}<XAxis dataKey="scenario" {...axis} interval={0} angle={-12} dy={8} />
              <YAxis domain={[55, 75]} {...axis} /><Tooltip />
              <Bar dataKey="mean_oee" radius={[8, 8, 0, 0]}>
                {data.scenarios.map((d, i) => <Cell key={i} fill={PALETTE[i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Initiative prioritisation — payback vs annual benefit (₹L)">
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart>
              {grid}<XAxis dataKey="payback" name="payback (months)" {...axis} />
              <YAxis dataKey="benefit" name="benefit ₹L" {...axis} /><Tooltip />
              <Scatter data={data.cba} fill="#22d3ee">
                {data.cba.map((d, i) => <Cell key={i} fill={PALETTE[i]} />)}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card title="Cost-benefit analysis (Wk 16)" style={{ marginTop: 16 }}>
        <Table
          columns={['initiative', 'benefit', 'cost', 'payback']}
          rows={data.cba}
          render={{
            benefit: (v) => `₹${v} L / yr`,
            cost: (v) => `₹${v} L`,
            payback: (v) => `${v} months`,
          }}
        />
      </Card>
    </>
  )
}

/* ------------------------------------------------ 10. KPIs & data quality */
export function KpiView() {
  const { data, error } = useApi('/api/kpis')
  if (!data) return <Loading error={error} />
  if (!data.ok) return <div className="skeleton">Run run_all.py first.</div>
  const red = data.kpis.filter((k) => k.status === 'RED').length
  return (
    <>
      <div className="grid tiles">
        <Tile label="KPIs tracked" value={data.kpis.length} />
        <Tile label="Below target" value={red} tone="bad" />
        <Tile label="On target" value={data.kpis.length - red} tone="good" />
      </div>
      <Card title="KPI baseline vs target & industry benchmark" style={{ marginTop: 16 }}>
        <Table
          columns={['kpi', 'baseline', 'target', 'industry_benchmark', 'status']}
          rows={data.kpis}
          render={{ status: (v) => <span className={`pill ${v === 'RED' ? 'red' : 'green'}`}>{v}</span> }}
        />
      </Card>
      <Card title="Data quality audit — 5 dimensions" style={{ marginTop: 16 }}>
        <Table columns={['table', 'rows', 'completeness_pct', 'uniqueness_pct', 'timeliness']} rows={data.data_quality} />
      </Card>
    </>
  )
}
