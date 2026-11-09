import { Link, Route, Routes } from 'react-router-dom';
import Chat from './pages/Chat';
import Home from './pages/Home';
import Dashboard from './pages/staff/Dashboard';
import Facts from './pages/staff/Facts';
import LeadDetail from './pages/staff/LeadDetail';
import Leads from './pages/staff/Leads';
import Login from './pages/staff/Login';
import Slots from './pages/staff/Slots';
import { HeadOnly, StaffLayout } from './pages/staff/StaffLayout';

function NotFound() {
  return (
    <main className="container narrow page">
      <h1>Page not found</h1>
      <p className="muted">That link does not lead anywhere.</p>
      <Link to="/">Back to start</Link>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/chat/:projectId" element={<Chat />} />
      <Route path="/staff/login" element={<Login />} />
      <Route path="/staff" element={<StaffLayout />}>
        <Route index element={<Leads />} />
        <Route path="leads/:id" element={<LeadDetail />} />
        <Route path="dashboard" element={<HeadOnly><Dashboard /></HeadOnly>} />
        <Route path="slots" element={<HeadOnly><Slots /></HeadOnly>} />
        <Route path="facts" element={<HeadOnly><Facts /></HeadOnly>} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}