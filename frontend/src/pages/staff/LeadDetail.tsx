import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api';
import type { LeadChat, LeadDetailData } from '../../types';
import {
  Badge, Empty, errMsg, ErrorBox, fmtWhen, reasonLabel, responseLabel, Spinner, useAsync, VisitBadge,
} from '../../ui';

export default function LeadDetail() {
  const id = useParams().id;
  const lead = useAsync(() => api<LeadDetailData>(`/api/leads/${id}/`), [id]);
  const chat = useAsync(() => api<LeadChat>(`/api/leads/${id}/chat/`), [id]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  if (lead.loading && !lead.data) return <Spinner />;
  if (lead.error || !lead.data) {
    return (
      <div className="stack">
        <ErrorBox message={lead.error || 'Lead not found.'} onRetry={lead.reload} />
        <Link to="/staff">← Back to leads</Link>
      </div>
    );
  }

  const l = lead.data;
  const current = l.bookings.find((b) => b.status === 'confirmed');
  const canMark = current && new Date(current.starts_at).getTime() <= Date.now();
  const needs = chat.data?.needs ?? {};

  async function mark(outcome: 'visited' | 'no_show') {
    if (!current) return;
    setBusy(true);
    setErr('');
    try {
      await api(`/api/bookings/${current.id}/outcome/`, { body: { outcome } });
      lead.reload();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack-lg">
      <Link to="/staff" className="small">← Leads</Link>
      <div className="between">
        <div>
          <h1>{l.name}</h1>
          <div className="row">
            <a href={`tel:${l.phone}`}>{l.phone}</a>
            <Badge>{l.source_label}</Badge>
            {l.is_duplicate && <Badge tone="warn">Duplicate of #{l.duplicate_of}</Badge>}
            {l.opted_out && <Badge tone="bad">Opted out</Badge>}
          </div>
        </div>
        <VisitBadge v={l.latest_visit} />
      </div>

      {!l.consent_at && <div className="banner warn">No consent recorded. Do not message this buyer until they agree.</div>}
      {l.opted_out && <div className="banner bad">This buyer opted out. Do not contact them.</div>}
      {chat.data?.flagged && (
        <div className="banner warn">Flagged for review: {reasonLabel(chat.data.flag_reason)}</div>
      )}

      <section className="card stack">
        <h2>Visit</h2>
        {current ? (
          <>
            <p>Booked for <strong>{fmtWhen(current.starts_at)}</strong></p>
            {canMark ? (
              <div className="row">
                <button className="btn primary" disabled={busy} onClick={() => mark('visited')}>Mark visited</button>
                <button className="btn" disabled={busy} onClick={() => mark('no_show')}>Mark no-show</button>
              </div>
            ) : (
              <p className="small muted">Outcome can be recorded once the visit time has passed.</p>
            )}
          </>
        ) : (
          <p className="muted">No upcoming visit. {l.latest_visit ? `Last status: ${l.latest_visit.status.replace('_', ' ')}.` : ''}</p>
        )}
        {err && <ErrorBox message={err} />}
      </section>

      <section className="card">
        <h2>Details</h2>
        <dl className="kv">
          <div><dt>Project</dt><dd>{l.project_name}</dd></div>
          <div><dt>Wants</dt><dd>{l.wants || '—'}</dd></div>
          <div><dt>Language</dt><dd>{l.language.toUpperCase()}</dd></div>
          <div><dt>Owner</dt><dd>{l.assigned_to_name ?? 'Unassigned'}</dd></div>
          <div><dt>Consent</dt><dd>{l.consent_at ? fmtWhen(l.consent_at) : 'Not recorded'}</dd></div>
          <div><dt>First response</dt><dd>{responseLabel(l)}</dd></div>
          {'budget_max_lakh' in needs && <div><dt>Budget (up to)</dt><dd>₹{String(needs.budget_max_lakh)} lakh</dd></div>}
          {typeof needs.timeline === 'string' && <div><dt>Timeline</dt><dd>{needs.timeline}</dd></div>}
          {typeof needs.note === 'string' && <div><dt>Note</dt><dd>{needs.note}</dd></div>}
        </dl>
      </section>

      {chat.data?.handoffs[0] && (
        <section className="card stack">
          <h2>Handoff summary</h2>
          <p className="small muted">
            {reasonLabel(chat.data.handoffs[0].reason)} · {fmtWhen(chat.data.handoffs[0].at)}
            {chat.data.handoffs[0].executive_name ? ` · to ${chat.data.handoffs[0].executive_name}` : ''}
          </p>
          <p style={{ whiteSpace: 'pre-wrap' }}>{chat.data.handoffs[0].summary}</p>
        </section>
      )}

      <section className="card stack">
        <h2>Conversation</h2>
        {chat.loading && !chat.data && <Spinner />}
        {chat.error && <ErrorBox message={chat.error} onRetry={chat.reload} />}
        {chat.data && chat.data.messages.length === 0 && <Empty title="No chat yet" hint="The buyer hasn’t written anything." />}
        <div className="stack">
          {chat.data?.messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.content}
              {m.cited && m.cited.length > 0 && (
                <div className="small muted">Facts used: {m.cited.map((c) => `F${c}`).join(', ')}</div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}