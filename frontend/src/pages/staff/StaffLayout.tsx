import type { ReactNode } from 'react';
import { Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth';
import { Empty, Spinner } from '../../ui';

export function StaffLayout() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/staff/login" replace />;
  const head = user.role === 'head';
  return (
    <>
      <header className="topbar">
        <div className="container">
          <span className="brand">Site visits</span>
          <nav className="nav" aria-label="Main">
            <NavLink to="/staff" end>Leads</NavLink>
            {head && <NavLink to="/staff/dashboard">Dashboard</NavLink>}
            {head && <NavLink to="/staff/slots">Visit slots</NavLink>}
            {head && <NavLink to="/staff/facts">Fact sheet</NavLink>}
          </nav>
          <div className="row">
            <span className="small muted">{user.name}</span>
            <button
              className="btn small quiet"
              onClick={async () => {
                await logout();
                navigate('/staff/login');
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="container staff-main">
        <Outlet />
      </main>
    </>
  );
}

export function HeadOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user?.role !== 'head') return <Empty title="Sales head only" hint="Ask the sales head if you need this." />;
  return <>{children}</>;
}