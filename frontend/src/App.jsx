import { useState } from 'react'
import {
  LiveView, OeeView, DowntimeView, QualityView, ThroughputView,
  InventoryView, ForecastView, PdmView, SimulationView, KpiView,
} from './views'

const PAGES = [
  { id: 'live', icon: '⚡', title: 'Live Control Tower', sub: 'Simulated shopfloor feed · auto-refreshes every 5 s', section: 'Real-time', view: LiveView, live: true },
  { id: 'oee', icon: '◔', title: 'OEE Analysis', sub: 'Availability × Performance × Quality · weeks 9–10', section: 'Analytics', view: OeeView },
  { id: 'downtime', icon: '🛑', title: 'Downtime & Pareto', sub: '847 events classified · weeks 10–11', section: 'Analytics', view: DowntimeView },
  { id: 'quality', icon: '✓', title: 'Quality Analytics', sub: 'SPC, shift effects and speed correlation · week 12', section: 'Analytics', view: QualityView },
  { id: 'throughput', icon: '∿', title: 'Throughput & Seasonality', sub: 'Rolling averages, STL findings · weeks 6, 9', section: 'Analytics', view: ThroughputView },
  { id: 'inventory', icon: '▦', title: 'Inventory Optimisation', sub: 'EOQ, safety stock, reorder points · week 14', section: 'Optimisation', view: InventoryView },
  { id: 'forecast', icon: '↗', title: 'Demand Forecast', sub: 'XGBoost vs SARIMA vs naive · week 18', section: 'Models', view: ForecastView },
  { id: 'pdm', icon: '🛠', title: 'Predictive Maintenance', sub: 'Random Forest failure prediction · week 19', section: 'Models', view: PdmView },
  { id: 'simulation', icon: '🎲', title: 'Simulation & CBA', sub: 'Monte Carlo scenarios, ₹39.8L programme · weeks 15–16', section: 'Optimisation', view: SimulationView },
  { id: 'kpi', icon: '◎', title: 'KPIs & Data Quality', sub: '12-KPI baseline, audit and ETL log · weeks 7–8', section: 'Governance', view: KpiView },
]

const SECTIONS = ['Real-time', 'Analytics', 'Models', 'Optimisation', 'Governance']

export default function App() {
  const [pageId, setPageId] = useState('live')
  const page = PAGES.find((p) => p.id === pageId)
  const View = page.view
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">🏭</div>
          <div>
            <div className="brand-name">Control Tower</div>
            <div className="brand-sub">Arrowcosta · Ops Analytics</div>
          </div>
        </div>
        {SECTIONS.map((section) => (
          <div key={section}>
            <div className="nav-section">{section}</div>
            {PAGES.filter((p) => p.section === section).map((p) => (
              <button key={p.id} className={`nav-item ${p.id === pageId ? 'active' : ''}`}
                onClick={() => setPageId(p.id)}>
                <span className="icon">{p.icon}</span>{p.title}
              </button>
            ))}
          </div>
        ))}
      </aside>
      <main className="main">
        <div className="page-head">
          <div>
            <div className="page-title">{page.title}</div>
            <div className="page-sub">{page.sub}</div>
          </div>
          {page.live && <span className="live-dot">LIVE</span>}
        </div>
        <View key={page.id} />
      </main>
    </div>
  )
}
