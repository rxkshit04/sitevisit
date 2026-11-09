import { useState } from 'react';
import { api } from '../../api';
import type { DashboardData } from '../../types';
import { ErrorBox, inr, pct, Spinner, useAsync } from '../../ui';

const dash = (n: number | null, unit = '') => (n == null ? '—' : `${n}${unit}`);

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card stat">
      <span className="small muted">{label}</span>
      <strong>{value}</strong>
      {hint && <span className="small muted">{hint}</span>}
    </div>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const { data, error, loading, reload } = useAsync(() => api<DashboardData>('/api/dashboard/', { query: { days } }), [days]);

  return (
    <div className="stack-lg">
      <div className="between">
        <h1>Dashboard</h1>
        <label className="field">
          Period
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </label>
      </div>
      {loading && !data && <Spinner />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && (
        <>
          <div className="grid-stats">
            <Stat label="Leads (duplicates excluded)" value={String(data.overall.leads)} />
            <Stat label="Median first response" value={dash(data.overall.median_response_min, ' min')} hint="Brief target: under 5 min" />
            <Stat label="Not reached in 48 h" value={pct(data.overall.not_reached_48h_pct)} hint="Brief target: under 5%" />
            <Stat label="Lead to visit" value={pct(data.overall.lead_to_visit_pct)} hint="Brief target: 8%" />
            <Stat label="Show-up rate" value={pct(data.overall.show_up_rate_pct)} />
            <Stat label="Cost per visit" value={inr(data.overall.cost_per_visit_inr)} />
          </div>
          <section className="card stack">
            <h2>By source</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Source</th><th>Leads</th><th>Median reply</th><th>Not reached 48 h</th>
                    <th>Visited</th><th>Show-up</th><th>Lead to visit</th><th>Cost per visit</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_source.map((r) => (
                    <tr key={r.source}>
                      <td>{r.label}</td>
                      <td>{r.leads}</td>
                      <td>{dash(r.median_response_min, ' min')}</td>
                      <td>{pct(r.not_reached_48h_pct)}</td>
                      <td>{r.visited}</td>
                      <td>{pct(r.show_up_rate_pct)}</td>
                      <td>{pct(r.lead_to_visit_pct)}</td>
                      <td>{inr(r.cost_per_visit_inr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="small muted">Spend per source is demo data, so cost per visit is illustrative.</p>
          </section>
        </>
      )}
    </div>
  );
}