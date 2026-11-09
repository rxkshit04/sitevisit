import { type FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth';
import { errMsg, ErrorBox } from '../../ui';

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  if (user) return <Navigate to="/staff" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      await login(username.trim(), password);
      navigate('/staff');
    } catch (e2) {
      setErr(errMsg(e2));
      setBusy(false);
    }
  }

  return (
    <main className="container narrow page">
      <p className="eyebrow">Sales team</p>
      <h1>Sign in</h1>
      <form className="card stack" onSubmit={submit}>
        <label className="field">
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label className="field">
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        {err && <ErrorBox message={err} />}
        <button className="btn primary" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}