import { Link } from 'react-router-dom';
import { api } from '../api';
import type { PublicProject } from '../types';
import { Empty, ErrorBox, Spinner, useAsync } from '../ui';

export default function Home() {
  const { data, error, loading, reload } = useAsync(() => api<PublicProject[]>('/api/public/projects/'), []);
  return (
    <main className="container narrow page">
      <p className="eyebrow">Ahmedabad</p>
      <h1>Visit your next home</h1>
      <p className="muted lead">Choose a project, ask us anything, and book a site visit at a time that suits you.</p>
      {loading && <Spinner />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && data.length === 0 && <Empty title="No projects yet" hint="Please check back soon." />}
      <div className="stack">
        {data?.map((p) => (
          <Link key={p.id} to={`/chat/${p.id}`} className="card project-card">
            <h2>{p.name}</h2>
            <p className="muted small">{p.address}</p>
            <p className="muted small">RERA Reg. No. {p.rera_number}</p>
            <span className="link">Start a chat →</span>
          </Link>
        ))}
      </div>
      <p className="foot small muted">
        <Link to="/staff/login">Staff sign in</Link>
      </p>
    </main>
  );
}