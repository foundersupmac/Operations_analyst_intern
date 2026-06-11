export function Tile({ label, value, suffix = '', delta, tone = '' }) {
  return (
    <div className={`card tile ${tone}`}>
      <div className="label">{label}</div>
      <div className="value">{value}{suffix}</div>
      {delta && <div className="delta" style={{ color: 'var(--text-dim)' }}>{delta}</div>}
    </div>
  )
}

export function Card({ title, right, children, style }) {
  return (
    <div className="card" style={style}>
      {title && <div className="card-title"><span>{title}</span>{right}</div>}
      {children}
    </div>
  )
}

export function Finding({ children }) {
  return <div className="finding">{children}</div>
}

export function RiskBar({ value }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="risk-bar"><div style={{ width: `${Math.round(value * 100)}%` }} /></div>
      <span style={{ fontSize: 12, fontWeight: 700 }}>{Math.round(value * 100)}%</span>
    </div>
  )
}

export function Table({ columns, rows, render = {} }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((c) => <th key={c}>{c.replace(/_/g, ' ')}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>{render[c] ? render[c](r[c], r) : r[c]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Loading({ error }) {
  return <div className="skeleton">{error ? `API error — is uvicorn running? (${error.message})` : 'Loading…'}</div>
}
