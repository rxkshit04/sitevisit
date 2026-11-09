import { type ReactNode, useEffect, useState } from 'react';
import type { Lead, VisitSummary } from './types';

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

const IST = 'Asia/Kolkata';
export const fmtWhen = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: IST,
  });
export const fmtDay = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: IST });
export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', timeZone: IST });
export const inr = (n: number | null) => (n == null ? '—' : '₹' + n.toLocaleString('en-IN'));
export const pct = (n: number | null) => (n == null ? '—' : `${n}%`);

export function responseLabel(l: Lead): string {
  if (!l.first_response_at) return 'No reply yet';
  const mins = Math.max(0, Math.round((new Date(l.first_response_at).getTime() - new Date(l.created_at).getTime()) / 60000));
  if (mins < 60) return `Replied in ${mins} min`;
  const h = Math.round(mins / 60);
  return h < 48 ? `Replied in ${h} h` : `Replied in ${Math.round(h / 24)} d`;
}

const REASONS: Record<string, string> = {
  missing_fact: 'Fact missing',
  buyer_request: 'Asked for a person',
  price_request: 'Asked about price',
  llm_unavailable: 'Assistant unavailable',
  llm_error: 'Assistant unavailable',
  guard_discount_claim: 'Reply blocked: discount',
  guard_unsupported_number: 'Reply blocked: unverified number',
  guard_bad_citation: 'Reply blocked: bad citation',
  guard_empty_reply: 'Reply blocked: empty',
  other: 'Other',
};
export const reasonLabel = (r: string) => REASONS[r] ?? r;

export function Badge({ tone, children }: { tone?: 'ok' | 'warn' | 'bad'; children: ReactNode }) {
  return <span className={`badge ${tone ?? ''}`}>{children}</span>;
}

export function VisitBadge({ v }: { v: VisitSummary | null }) {
  if (!v) return <Badge>No visit</Badge>;
  if (v.status === 'confirmed') return <Badge tone="ok">Booked · {fmtWhen(v.starts_at)}</Badge>;
  if (v.status === 'visited') return <Badge tone="ok">Visited</Badge>;
  if (v.status === 'no_show') return <Badge tone="bad">No-show</Badge>;
  return <Badge>Cancelled</Badge>;
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="center-note" role="status">
      <span className="spinner" aria-hidden /> {label}…
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="banner bad" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button className="btn small" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{ data: T | null; error: string; loading: boolean }>({
    data: null, error: '', loading: true,
  });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: '' }));
    fn()
      .then((data) => live && setState({ data, error: '', loading: false }))
      .catch((e) => live && setState({ data: null, error: errMsg(e), loading: false }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}