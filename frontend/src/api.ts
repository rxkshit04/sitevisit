export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function cookie(name: string): string {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : '';
}

export async function ensureCsrf(): Promise<void> {
  await fetch('/api/auth/csrf/', { credentials: 'same-origin' });
}

function label(key: string): string {
  const s = key.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function messageFrom(data: any): string {
  if (!data) return '';
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map(messageFrom).filter(Boolean).join(' ');
  if (typeof data.detail === 'string') return data.detail;
  return Object.entries(data)
    .map(([k, v]) => {
      const m = messageFrom(v);
      return k === 'non_field_errors' ? m : `${label(k)}: ${m}`;
    })
    .join(' ');
}

interface Options {
  method?: string;
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | undefined>;
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  let url = path;
  if (opts.query) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined && v !== '') p.set(k, String(v));
    }
    const s = p.toString();
    if (s) url += '?' + s;
  }
  const hasBody = opts.body !== undefined || opts.form !== undefined;
  const method = opts.method ?? (hasBody ? 'POST' : 'GET');
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  if (method !== 'GET') {
    const token = cookie('csrftoken');
    if (token) headers['X-CSRFToken'] = token;
  }
  let res: Response;
  try {
    res = await fetch(url, { method, headers, body, credentials: 'same-origin' });
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.');
  }
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) throw new ApiError(res.status, messageFrom(data) || 'Something went wrong.');
  return data as T;
}