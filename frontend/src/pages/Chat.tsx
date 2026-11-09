import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, ApiError } from '../api';
import type { BookingInfo, ChatMsg, ChatReply, ChatState, HandoffInfo, PublicProject, SlotChip } from '../types';
import { errMsg, ErrorBox, fmtDay, fmtWhen, Spinner } from '../ui';

const tokenKey = (id: number) => `sv_chat_${id}`;
function loadToken(id: number): string | null {
  try {
    return localStorage.getItem(tokenKey(id));
  } catch {
    return null;
  }
}
function saveToken(id: number, t: string | null) {
  try {
    if (t) localStorage.setItem(tokenKey(id), t);
    else localStorage.removeItem(tokenKey(id));
  } catch {
    /* storage can be blocked; the chat still works until the tab closes */
  }
}

export default function Chat() {
  const pid = Number(useParams().projectId);
  const [phase, setPhase] = useState<'loading' | 'intake' | 'chat' | 'error'>('loading');
  const [project, setProject] = useState<PublicProject | null>(null);
  const [token, setToken] = useState('');
  const [state, setState] = useState<ChatState | null>(null);
  const [error, setError] = useState('');

  async function open(t: string): Promise<boolean> {
    try {
      const st = await api<ChatState>('/api/public/chat/', { query: { token: t } });
      setToken(t);
      setState(st);
      setPhase('chat');
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        saveToken(pid, null);
        return false;
      }
      throw e;
    }
  }

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const p = await api<PublicProject>(`/api/public/projects/${pid}/`);
        if (!live) return;
        setProject(p);
        const t = loadToken(pid);
        if (t && (await open(t))) return;
        if (live) setPhase('intake');
      } catch (e) {
        if (live) {
          setError(errMsg(e));
          setPhase('error');
        }
      }
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  if (phase === 'loading') return <Spinner />;
  if (phase === 'error' || !project) {
    return (
      <main className="container narrow page">
        <ErrorBox message={error || 'This project could not be found.'} />
      </main>
    );
  }
  if (phase === 'intake') {
    return (
      <Intake
        project={project}
        onStart={async (t) => {
          saveToken(pid, t);
          await open(t);
        }}
      />
    );
  }
  return (
    <Conversation
      project={project}
      token={token}
      initial={state!}
      onExpired={() => {
        saveToken(pid, null);
        setPhase('intake');
      }}
    />
  );
}

function Intake({ project, onStart }: { project: PublicProject; onStart: (token: string) => Promise<void> }) {
  const [f, setF] = useState({ name: '', phone: '', language: 'en', wants: '', consent: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const r = await api<{ token: string }>('/api/public/leads/', {
        body: { name: f.name.trim(), phone: f.phone, project: project.id, wants: f.wants, language: f.language, consent: f.consent },
      });
      await onStart(r.token);
    } catch (e2) {
      setErr(errMsg(e2));
      setBusy(false);
    }
  }

  return (
    <main className="container narrow page">
      <p className="eyebrow">{project.name}</p>
      <h1>Let’s find a time to visit</h1>
      <p className="muted">Tell us who you are and we’ll answer your questions and book a visit.</p>
      <form className="card stack" onSubmit={submit}>
        <label className="field">
          Your name
          <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required maxLength={120} autoComplete="name" />
        </label>
        <label className="field">
          Mobile number
          <input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required inputMode="tel" autoComplete="tel" placeholder="98765 43210" />
        </label>
        <div className="grid-2">
          <label className="field">
            Language
            <select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}>
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
              <option value="gu">ગુજરાતી</option>
            </select>
          </label>
          <label className="field">
            Looking for
            <select value={f.wants} onChange={(e) => setF({ ...f, wants: e.target.value })}>
              <option value="">Not sure yet</option>
              <option value="2 BHK">2 BHK</option>
              <option value="3 BHK">3 BHK</option>
            </select>
          </label>
        </div>
        <label className="check">
          <input type="checkbox" checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} />
          <span>
            I agree to be contacted about {project.name} by phone or WhatsApp. I can reply STOP at any time to opt out.
          </span>
        </label>
        {err && <ErrorBox message={err} />}
        <button className="btn primary" disabled={busy || !f.consent || !f.name.trim()}>
          {busy ? 'Starting…' : 'Start chat'}
        </button>
        <p className="small muted">RERA Reg. No. {project.rera_number}</p>
      </form>
    </main>
  );
}

function Conversation({
  project, token, initial, onExpired,
}: {
  project: PublicProject; token: string; initial: ChatState; onExpired: () => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>(initial.messages);
  const [booking, setBooking] = useState<BookingInfo | null>(initial.booking);
  const [handoff, setHandoff] = useState<HandoffInfo | null>(initial.handoff);
  const [slots, setSlots] = useState<SlotChip[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending, slots, booking, error]);

  function fail(e: unknown) {
    if (e instanceof ApiError && e.status === 404) onExpired();
    else setError(errMsg(e));
  }

  function absorb(r: { booking?: BookingInfo | null; handoff?: HandoffInfo | null }) {
    if (r.booking) setBooking(r.booking);
    if (r.handoff) setHandoff(r.handoff);
  }

  async function send(text: string) {
    const t = text.trim();
    if (!t || sending) return;
    setMessages((m) => [...m, { role: 'buyer', content: t }]);
    setInput('');
    setSending(true);
    setError('');
    setSlots([]);
    try {
      const r = await api<ChatReply>('/api/public/chat/', { body: { token, message: t } });
      setMessages((m) => [...m, { role: 'assistant', content: r.reply }]);
      setSlots(r.slots ?? []);
      absorb(r);
    } catch (e) {
      fail(e);
    } finally {
      setSending(false);
    }
  }

  async function showSlots() {
    setBusy(true);
    setError('');
    try {
      const rows = await api<{ id: number; starts_at: string }[]>(`/api/projects/${project.id}/slots/`);
      const seen = new Set<string>();
      const perDay: Record<string, number> = {};
      const out: SlotChip[] = [];
      for (const r of rows) {
        const day = fmtDay(r.starts_at);
        if (seen.has(r.starts_at) || (perDay[day] ?? 0) >= 3) continue;
        seen.add(r.starts_at);
        perDay[day] = (perDay[day] ?? 0) + 1;
        out.push({ id: r.id, starts_at: r.starts_at, label: fmtWhen(r.starts_at) });
        if (out.length >= 9) break;
      }
      if (out.length === 0) setError('No free times are open right now. Tap “Talk to a person” and we will arrange one.');
      setSlots(out);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function book(s: SlotChip) {
    setBusy(true);
    setError('');
    try {
      const r = await api<{ booking: BookingInfo }>('/api/public/chat/book/', { body: { token, slot_id: s.id } });
      setBooking(r.booking);
      setSlots([]);
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Your visit is booked for ${r.booking.label} with ${r.booking.executive ?? 'our team'}.` },
      ]);
    } catch (e) {
      fail(e);
      if (e instanceof ApiError && e.status === 409) await showSlots();
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!window.confirm('Cancel this visit?')) return;
    setBusy(true);
    setError('');
    try {
      await api('/api/public/chat/cancel/', { body: { token } });
      setBooking(null);
      setMessages((m) => [...m, { role: 'assistant', content: 'Your visit is cancelled. You can book another time whenever you like.' }]);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function askPerson() {
    setBusy(true);
    setError('');
    try {
      const r = await api<ChatReply>('/api/public/chat/handoff/', { body: { token } });
      setMessages((m) => [...m, { role: 'buyer', content: 'I’d like to talk to a person.' }, { role: 'assistant', content: r.reply }]);
      absorb(r);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-shell">
      <header className="chat-head">
        <div>
          <p className="eyebrow">{project.name}</p>
          <span className="small muted">Site-visit assistant</span>
        </div>
        <button className="btn small" onClick={askPerson} disabled={busy || sending}>
          Talk to a person
        </button>
      </header>

      <div className="chat-scroll" ref={scroller}>
        {booking && (
          <div className="booking-card">
            <span className="small muted">Your visit</span>
            <span className="when">{booking.label}</span>
            <span>With {booking.executive ?? 'our team'} · {booking.project}</span>
            {booking.address && <span className="small muted">{booking.address}</span>}
            <div className="row" style={{ marginTop: 10 }}>
              {booking.map_url && (
                <a className="btn small" href={booking.map_url} target="_blank" rel="noreferrer">
                  Open map
                </a>
              )}
              <button className="btn small" onClick={showSlots} disabled={busy}>
                Change time
              </button>
              <button className="btn small danger" onClick={cancel} disabled={busy}>
                Cancel visit
              </button>
            </div>
          </div>
        )}

        {handoff && (
          <div className="banner info">
            {handoff.executive_name ? `Your chat is with ${handoff.executive_name}. They’ll be in touch.` : 'Our sales team has your chat and will be in touch.'}
          </div>
        )}

        {messages.length === 0 && (
          <div className="bubble assistant">
            Welcome to {project.name}. Ask me anything about the project, or book a site visit whenever you’re ready.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {sending && (
          <div className="bubble assistant" aria-label="Assistant is typing">
            <span className="typing"><span /><span /><span /></span>
          </div>
        )}

        {slots.length > 0 && (
          <div className="sheet">
            <strong>Pick a time</strong>
            <div className="chips">
              {slots.map((s) => (
                <button key={s.id} className="chip" onClick={() => book(s)} disabled={busy}>
                  {s.label}
                </button>
              ))}
            </div>
            <button className="btn quiet small" onClick={() => setSlots([])}>
              Not now
            </button>
          </div>
        )}
        {error && <ErrorBox message={error} />}
      </div>

      <div className="composer">
        {!booking && slots.length === 0 && (
          <div className="chips">
            <button className="chip" onClick={showSlots} disabled={busy || sending}>
              Book a visit
            </button>
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message"
            maxLength={1000}
            aria-label="Message"
          />
          <button className="btn primary" disabled={sending || !input.trim()}>
            Send
          </button>
        </form>
      </div>
      <div className="rera">RERA Reg. No. {project.rera_number} · Reply STOP to opt out</div>
    </div>
  );
}