import { useEffect } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router';
import { UNAUTHORIZED_EVENT } from './api/client';
import { Layout } from './components/Layout';
import { CallsPage } from './pages/CallsPage';
import { ContactsPage } from './pages/ContactsPage';
import { DialPadPage } from './pages/DialPadPage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { MemoriesPage } from './pages/MemoriesPage';
import { SettingsPage } from './pages/SettingsPage';

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const onUnauthorized = () => {
      if (location.pathname !== '/login') {
        navigate('/login', { replace: true, state: { from: location.pathname } });
      }
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [navigate, location.pathname]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="contacts" element={<ContactsPage />} />
        <Route path="dial" element={<DialPadPage />} />
        <Route path="memories" element={<MemoriesPage />} />
        <Route path="calls" element={<CallsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
