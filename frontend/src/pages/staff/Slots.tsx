import { type FormEvent, useState } from 'react';
import { api } from '../../api';
import type { Executive, PublicProject, SlotRow } from '../../types';
import { Badge, Empty, errMsg, ErrorBox, fmtDay, fmtTime, Spinner, useAsync } from '../../ui';

export default function Slots() {
  const projects = useAsync(() => api<PublicProject[]>('/api/public/projects/'), []);
  const execs = useAsync(() => api<Executive[]>('/api/admin/executives/'), []);
  const [project, setProject] = useState('');
  const [exec, setExec] = useState('');
  const [startDate, setStartDate] = useState(() => new Date(Date.now() + 864e5).toISOString().slice(0, 10));
  const [days, setDays] = useState(7);
  const [startHour, setStartHour] = useState(10);
  const [endHour, setEndHour] = useState(18);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');

  const pid = project || String(projects.data?.[0]?.id ?? '');
  const eid = exec || String(execs.data?.[0]?.id ?? '');
  const slots = useAsync(() => api<SlotRow[]>('/api/admin/slots/', { query: { project: pid } }), [pid]);

  const groups = new Map<string, SlotRow[]>();
  for (const s of slots.data ?? []) {
    const k = fmtDay(s.starts_at);
    const arr = groups.get(k);
    if (arr) arr.push(s);
    else groups.set(k, [s]);
  }

  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    setNote('');
    try {
      const r = await api<{ created: number }>('/api/admin/slots/', {
        body: { project: Number(pid), executive: Number(eid), start_date: startDate, days, start_hour: startHour, end_hour: endHour },
      });
      setNote(r.created === 0 ? 'Those slots already exist.' : `${r.created} slots added.`);
      slots.reload();
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setErr('');
    try {
      await api(`/api/admin/slots/${id}/`, { method: 'DELETE' });
      slots.reload();
    } catch (e) {
      setErr(errMsg(e));
    }
  }

  return (
    <div className="stack-lg">
      <h1>Visit slots</h1>
      <form className="card stack" onSubmit={generate}>
        <h2>Add slots</h2>
        <div className="grid-2">
          <label className="field">
            Project
            <select value={pid} onChange={(e) => setProject(e.target.value)}>
              {projects.data?.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Executive
            <select value={eid} onChange={(e) => setExec(e.target.value)}>
              {execs.data?.map((x) => (
                <option key={x.id} value={x.id}>{x.name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Start date
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </label>
          <label className="field">
            Days
            <input type="number" min={1} max={31} value={days} onChange={(e) => setDays(Number(e.target.value))} />
          </label>
          <label className="field">
            First slot starts (hour)
            <input type="number" min={6} max={21} value={startHour} onChange={(e) => setStartHour(Number(e.target.value))} />
          </label>
          <label className="field">
            Last slot ends (hour)
            <input type="number" min={7} max={22} value={endHour} onChange={(e) => setEndHour(Number(e.target.value))} />
          </label>
        </div>
        <p className="small muted">One slot is one hour with one executive. Running it twice does not create duplicates.</p>
        {err && <ErrorBox message={err} />}
        {note && <div className="banner info">{note}</div>}
        <div>
          <button className="btn primary" disabled={busy || !pid || !eid}>{busy ? 'Adding…' : 'Add slots'}</button>
        </div>
      </form>

      <section className="stack">
        <h2>Upcoming slots</h2>
        {slots.loading && !slots.data && <Spinner />}
        {slots.error && <ErrorBox message={slots.error} onRetry={slots.reload} />}
        {slots.data && slots.data.length === 0 && <Empty title="No upcoming slots" hint="Add some above so buyers can book." />}
        {[...groups.entries()].map(([day, rows]) => (
          <div key={day} className="card stack">
            <strong>{day}</strong>
            {rows.map((s) => (
              <div key={s.id} className="between">
                <span>{fmtTime(s.starts_at)} · {s.executive}</span>
                <span className="row">
                  {s.booked ? <Badge tone="ok">Booked</Badge> : <Badge>Free</Badge>}
                  {!s.booked && <button className="btn small quiet danger" onClick={() => remove(s.id)}>Remove</button>}
                </span>
              </div>
            ))}
          </div>
        ))}
      </section>
    </div>
  );
}