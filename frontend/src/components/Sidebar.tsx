import { NavLink } from 'react-router-dom';
import { LayoutGrid, AppWindow, User, LogOut, Rocket } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutGrid, label: 'Dashboard' },
  { to: '/applications', icon: AppWindow, label: 'Applications' },
  { to: '/profile', icon: User, label: 'Profile' },
];

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="w-56 flex-shrink-0 h-screen sticky top-0 flex flex-col bg-canvas border-r border-hairline">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-hairline">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center">
            <Rocket size={14} className="text-white" />
          </div>
          <span className="text-[15px] font-semibold text-ink tracking-tight">Deploy</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `nav-link flex items-center gap-2.5 ${isActive ? 'active text-ink bg-surface-strong' : ''}`
            }
          >
            <Icon size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User section */}
      <div className="p-3 border-t border-hairline">
        <div className="flex items-center gap-2.5 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-surface-strong border border-hairline flex items-center justify-center flex-shrink-0">
            <span className="text-[11px] font-semibold text-muted uppercase">
              {user?.email?.[0] ?? 'U'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-caption font-medium text-ink truncate">{user?.email ?? '—'}</p>
          </div>
        </div>
        <button
          className="nav-link w-full flex items-center gap-2.5 text-muted mt-1"
          onClick={logout}
        >
          <LogOut size={15} />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}
