import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api';
import { useAuth } from '../../auth';
import { type FlaggedChat, type Lead, type PublicProject, SOURCES } from '../../types';
import {
  Badge, Empty, errMsg, ErrorBox, reasonLabel, responseLabel, Spinner, useAsync, VisitBadge,
} from '../../ui';

export default function Leads() {
  const { user } = useAuth();
  const [tab, setTab] = useState<'leads' | 'flagged'>('leads');
  const head = user?.role === 'head';
  return (
    <div className="stack-lg">
      <div className="between">
        <h1>{tab === 'leads' ? 'Leads' : 'Flagged chats'}</h1>
        {head && (
          <div className="tabs" role="tablist">
            <button className={`tab ${tab === 'leads' ? 'on' : ''}`} onClick={() => setTab('leads')}>Leads</button>
            <button className={`tab ${tab === 'flagged' ? 'on' : ''}`} onClick={() => setTab('flagged')}>Flagged chats</button>
          </div>
        )}
      </div>
      {tab === 'leads' ? <LeadList /> : <Flagged />}
    </div>
  );
}

function LeadList() {
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('');
  const [dups, setDups] = useState(false);
  const [unassigned, setUnassigned] = useState(false);
  const [panel, setPanel] = useState<'' | 'add' | 'import'>('');
  const [note, setNote] = useState('');

  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const { data, error, loading, reload } = useAsync(
    () =>
      api<{ count: number; results: Lead[] }>('/api/leads/', {
        query: { q: query, source, duplicates: dups ? '1' : '', unassigned: unassigned ? '1' : '' },
      }),
    [query, source, dups, unassigned],
  );

  return (
    <>
      <div className="row">
        <button className="btn primary" onClick={() => setPanel(panel === 'add' ? '' : 'add')}>Add lead</button>
        <button className="btn" onClick={() => setPanel(panel === 'import' ? '' : 'import')}>Import CSV</button>
      </div>
      {note && <div className="banner info">{note}</div>}
      {panel === 'add' && (
        <AddLead
          onDone={(dup) => {
            setPanel('');
            setNote(dup ? 'Lead added. This number already existed, so it is linked as a duplicate.' : 'Lead added.');
            reload();
          }}
        />
      )}
      {panel === 'import' && (
        <ImportCsv
          onDone={() => {
            reload();
          }}
        />
      )}

      <div className="filters">
        <label className="field">
          Search
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or phone" />
        </label>
        <label className="field">
          Source
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">All sources</option>
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={dups} onChange={(e) => setDups(e.target.checked)} />
          Duplicates only
        </label>
        <label className="check">
          <input type="checkbox" checked={unassigned} onChange={(e) => setUnassigned(e.target.checked)} />
          Unassigned only
        </label>
      </div>

      {loading && !data && <Spinner />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && data.results.length === 0 && <Empty title="No leads match" hint="Try clearing a filter." />}
      <div className="stack">
        {data?.results.map((l) => (
          <Link key={l.id} to={`/staff/leads/${l.id}`} className="row-card">
            <div className="grow">
              <div className="name">
                {l.name}
                {l.is_duplicate && <Badge tone="warn">Duplicate</Badge>}
                {l.opted_out && <Badge tone="bad">Opted out</Badge>}
              </div>
              <div className="small muted">
                {l.phone} · {l.project_name}
                {l.wants ? ` · ${l.wants}` : ''}
                {l.assigned_to_name ? ` · ${l.assigned_to_name}` : ' · Unassigned'}
              </div>
            </div>
            <div className="meta">
              <Badge>{l.source_label}</Badge>
              <VisitBadge v={l.latest_visit} />
              <span className="small muted">{responseLabel(l)}</span>
            </div>
          </Link>
        ))}
      </div>
      {data && data.count > data.results.length && (
        <p className="small muted">Showing the latest {data.results.length} of {data.count}. Use search to narrow down.</p>
      )}
    </>
  );
}

function AddLead({ onDone }: { onDone: (duplicate: boolean) => void }) {
  const projects = useAsync(() => api<PublicProject[]>('/api/public/projects/'), []);
  const [f, setF] = useState({ name: '', phone: '', source: 'hoarding', project: '', wants: '', language: 'en', consent: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const projectId = f.project || String(projects.data?.[0]?.id ?? '');

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const r = await api<{ duplicate: boolean }>('/api/leads/', {
        body: { ...f, project: Number(projectId), name: f.name.trim() },
      });
      onDone(r.duplicate);
    } catch (e2) {
      setErr(errMsg(e2));
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <div className="grid-2">
        <label className="field">
          Name
          <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required maxLength={120} />
        </label>
        <label className="field">
          Mobile number
          <input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required inputMode="tel" />
        </label>
        <label className="field">
          Source
          <select value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}>
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Project
          <select value={projectId} onChange={(e) => setF({ ...f, project: e.target.value })}>
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Wants
          <select value={f.wants} onChange={(e) => setF({ ...f, wants: e.target.value })}>
            <option value="">Not known</option>
            <option value="2 BHK">2 BHK</option>
            <option value="3 BHK">3 BHK</option>
          </select>
        </label>
        <label className="field">
          Language
          <select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}>
            <option value="en">English</option>
            <option value="hi">Hindi</option>
            <option value="gu">Gujarati</option>
          </select>
        </label>
      </div>
      <label className="check">
        <input type="checkbox" checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} />
        <span>The buyer has agreed to be contacted. Without this the lead is stored but never messaged.</span>
      </label>
      {err && <ErrorBox message={err} />}
      <div>
        <button className="btn primary" disabled={busy || !projectId}>{busy ? 'Saving…' : 'Save lead'}</button>
      </div>
    </form>
  );
}

function ImportCsv({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState<{ created: number; duplicates: number; errors: { row: number; error: string }[] } | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setErr('');
    setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      setResult(await api('/api/leads/import/', { form }));
      onDone();
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <p className="small muted">
        Columns: name, phone, source, project (the project’s name). Optional: wants, language. Imported leads have no
        consent recorded, so they are never messaged. Up to 500 rows.
      </p>
      <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      {err && <ErrorBox message={err} />}
      {result && (
        <div className="banner info">
          <span>
            {result.created} added, {result.duplicates} duplicates, {result.errors.length} rows skipped.
            {result.errors.slice(0, 5).map((x) => ` Row ${x.row}: ${x.error}`).join('')}
          </span>
        </div>
      )}
      <div>
        <button className="btn primary" disabled={!file || busy}>{busy ? 'Importing…' : 'Import'}</button>
      </div>
    </form>
  );
}

function Flagged() {
  const [showAll, setShowAll] = useState(false);
  const { data, error, loading, reload } = useAsync(
    () => api<FlaggedChat[]>('/api/chats/flagged/', { query: { reviewed: showAll ? '' : '0' } }),
    [showAll],
  );
  const [err, setErr] = useState('');

  async function review(id: number) {
    setErr('');
    try {
      await api(`/api/chats/${id}/review/`, { method: 'POST' });
      reload();
    } catch (e) {
      setErr(errMsg(e));
    }
  }

  return (
    <>
      <label className="check">
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        Include reviewed chats
      </label>
      {loading && !data && <Spinner />}
      {(error || err) && <ErrorBox message={error || err} onRetry={reload} />}
      {data && data.length === 0 && <Empty title="Nothing to review" hint="Chats are flagged when the assistant hands off or a reply is blocked." />}
      <div className="stack">
        {data?.map((c) => (
          <div key={c.id} className="card stack">
            <div className="between">
              <div className="row">
                <strong>{c.lead_name}</strong>
                <Badge tone="warn">{reasonLabel(c.reason)}</Badge>
                {c.reviewed && <Badge tone="ok">Reviewed</Badge>}
              </div>
              <span className="small muted">{c.project}</span>
            </div>
            {c.last_message && <p className="small">Buyer’s last message: “{c.last_message}”</p>}
            {c.summary && <p className="small muted">{c.summary}</p>}
            <div className="row">
              <Link className="btn small" to={`/staff/leads/${c.lead_id}`}>Open lead</Link>
              {!c.reviewed && <button className="btn small primary" onClick={() => review(c.id)}>Mark reviewed</button>}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}