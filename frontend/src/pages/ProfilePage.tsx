import { useAuth } from '../hooks/useAuth';
import { User, Mail, LogOut } from 'lucide-react';

export function ProfilePage() {
  const { user, logout } = useAuth();

  return (
    <div className="px-10 py-10 max-w-2xl">
      <div className="mb-8">
        <p className="section-label mb-1">Account</p>
        <h1 className="text-[26px] font-normal tracking-[-0.325px] leading-[1.25] text-ink">
          Profile
        </h1>
      </div>

      <div className="card p-6 flex flex-col gap-6">
        {/* Avatar */}
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-surface-strong border border-hairline flex items-center justify-center">
            <span className="text-[18px] font-semibold text-muted uppercase">
              {user?.email?.[0] ?? 'U'}
            </span>
          </div>
          <div>
            <p className="text-title-sm text-ink">{user?.email}</p>
            <p className="text-caption text-muted">User ID: {user?.id}</p>
          </div>
        </div>

        <div className="border-t border-hairline-soft" />

        {/* Info rows */}
        <div className="flex flex-col gap-4">
          <InfoRow
            icon={<Mail size={14} />}
            label="Email"
            value={user?.email ?? '—'}
          />
          <InfoRow
            icon={<User size={14} />}
            label="User ID"
            value={String(user?.id ?? '—')}
            mono
          />
        </div>

        <div className="border-t border-hairline-soft" />

        {/* Actions */}
        <div>
          <p className="section-label mb-3">Danger Zone</p>
          <button
            className="btn-secondary text-semantic-error border-semantic-error/30 hover:bg-[#fde8ed]"
            onClick={logout}
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </div>

      {/* Coming soon note */}
      <div className="mt-6 card p-5">
        <p className="section-label mb-1">API Keys · Profile Settings</p>
        <p className="text-body-sm text-muted">
          Profile editing and API key management are coming soon.
        </p>
      </div>
    </div>
  );
}

interface InfoRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}

function InfoRow({ icon, label, value, mono }: InfoRowProps) {
  return (
    <div className="flex items-center gap-4">
      <div className="w-7 h-7 rounded-md bg-canvas border border-hairline flex items-center justify-center text-muted flex-shrink-0">
        {icon}
      </div>
      <div className="flex-1">
        <p className="section-label">{label}</p>
        <p className={`text-body-sm text-ink mt-0.5 ${mono ? 'font-mono' : ''}`}>{value}</p>
      </div>
    </div>
  );
}
