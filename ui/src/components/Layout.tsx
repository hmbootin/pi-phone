import { NavLink, Outlet } from 'react-router';
import { useLiveUpdates } from '../api/events';

const tabs = [
  { to: '/', label: 'Home', icon: '⌂' },
  { to: '/contacts', label: 'Contacts', icon: '☎' },
  { to: '/dial', label: 'Dial pad', icon: '⌨' },
  { to: '/memories', label: 'Memories', icon: '♪' },
  { to: '/calls', label: 'Calls', icon: '☰' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
];

export function Layout() {
  useLiveUpdates();
  return (
    <div className="app">
      <Outlet />
      <nav className="nav" aria-label="Main">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>
            <span className="nav-icon" aria-hidden>
              {t.icon}
            </span>
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
