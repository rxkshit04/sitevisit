import { type FormEvent, useState } from 'react';
import { api } from '../../api';
import type { Fact, PublicProject } from '../../types';
import { Badge, Empty, errMsg, ErrorBox, Spinner, useAsync } from '../../ui';

export default function Facts() {
  const projects = useAsync(() => api<PublicProject[]>('/api/public/projects/'), []);
  const [project, setProject] = useState('');
  const pid = project || String(projects.data?.[0]?.id ?? '');
  const facts = useAsync(() => api<Fact[]>('/api/facts/', { query: { project: pid } }), [pid]);

  const [editing, setEditing] = useState<number | null>(null);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [registered, setRegistered] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  function reset() {
    setEditing(null);
    setTitle('');
    setText('');
    setRegistered(true);
  }

  function edit(f: Fact) {
    setEditing(f.id);
    setTitle(f.title);
    setText(f.text);
    setRegistered(f.is_registered);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const body = { project: Number(pid), title: title.trim(), text: text.trim(), is_registered: registered };
      if (editing) await api(`/api/facts/${editing}/`, { method: 'PATCH', body });
      else await api('/api/facts/', { body });
      reset();
      facts.reload();
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  }

  async function remove(f: Fact) {
    if (!window.confirm(`Delete “${f.title}”? The assistant will stop using it.`)) return;
    setErr('');
    try {
      await api(`/api/facts/${f.id}/`, { method: 'DELETE' });
      facts.reload();
    } catch (e) {
      setErr(errMsg(e));
    }
  }

  return (
    <div className="stack-lg">
      <div className="between">
        <h1>Fact sheet</h1>
        <label className="field">
          Project
          <select value={pid} onChange={(e) => { setProject(e.target.value); reset(); }}>
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">
        The assistant may only state what is written here. If a buyer asks about something missing, it says a person will
        confirm and hands the chat to an executive. Keep prices, possession dates and approvals to registered details.
      </p>

      <form className="card stack" onSubmit={save}>
        <h2>{editing ? 'Edit entry' : 'New entry'}</h2>
        <label className="field">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={120} />
        </label>
        <label className="field">
          Text ({text.length}/600)
          <textarea value={text} onChange={(e) => setText(e.target.value)} required maxLength={600} />
        </label>
        <label className="check">
          <input type="checkbox" checked={registered} onChange={(e) => setRegistered(e.target.checked)} />
          <span>This is a RERA-registered detail</span>
        </label>
        {err && <ErrorBox message={err} />}
        <div className="row">
          <button className="btn primary" disabled={busy || !pid}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Add entry'}</button>
          {editing && <button type="button" className="btn quiet" onClick={reset}>Cancel</button>}
        </div>
      </form>

      {facts.loading && !facts.data && <Spinner />}
      {facts.error && <ErrorBox message={facts.error} onRetry={facts.reload} />}
      {facts.data && facts.data.length === 0 && <Empty title="No entries yet" hint="Add the first fact above." />}
      <div className="stack">
        {facts.data?.map((f) => (
          <div key={f.id} className="card stack">
            <div className="between">
              <strong>{f.title}</strong>
              <Badge tone={f.is_registered ? 'ok' : undefined}>{f.is_registered ? 'Registered' : 'Info'}</Badge>
            </div>
            <p>{f.text}</p>
            <div className="row">
              <button className="btn small" onClick={() => edit(f)}>Edit</button>
              <button className="btn small quiet danger" onClick={() => remove(f)}>Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}