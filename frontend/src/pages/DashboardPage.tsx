import { AppWindow, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useApplications } from '../hooks/useDeployments';
import { useDashboardStats } from '../hooks/useDashboardStats';
import { StatusBadge } from '../components/StatusBadge';

export function DashboardPage() {
  const { user } = useAuth();
  const { data: apps, isLoading: appsLoading } = useApplications();
  const { total, running, isLoading: statsLoading } = useDashboardStats();

  const isLoading = appsLoading || statsLoading;

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  })();

  const emailName = user?.email?.split('@')[0] ?? '';

  return (
    <div className="px-10 py-10 max-w-5xl">
      {/* Greeting */}
      <div className="mb-10">
        <p className="section-label mb-1">Dashboard</p>
        <h1 className="text-[36px] font-normal tracking-[-0.72px] leading-[1.2] text-ink">
          {greeting}{emailName ? `, ${emailName}` : ''}.
        </h1>
        <p className="text-body-md text-muted mt-2">
          Here's what's happening with your deployments.
        </p>
      </div>

      {/* Live stats */}
      <div className="grid grid-cols-3 gap-4 mb-10">
        <StatCard
          label="Applications"
          value={isLoading ? '—' : String(total)}
        />
        <StatCard
          label="Running"
          value={isLoading ? '—' : String(running)}
          valueClass={running > 0 ? 'text-semantic-success' : undefined}
          live
        />
        <StatCard
          label="Platform"
          value="Online"
          valueClass="text-semantic-success"
        />
      </div>

      {/* Recent applications */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-title-sm text-ink">Applications</h2>
          <Link
            to="/applications"
            className="text-body-sm text-muted hover:text-ink transition-colors"
          >
            View all →
          </Link>
        </div>

        {!appsLoading && (!apps || apps.length === 0) ? (
          <div className="card p-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md bg-canvas border border-hairline flex items-center justify-center">
                <AppWindow size={16} className="text-muted-soft" />
              </div>
              <div>
                <p className="text-title-sm text-ink">No applications yet</p>
                <p className="text-body-sm text-muted">Deploy your first container.</p>
              </div>
            </div>
            <Link to="/applications" className="btn-primary no-underline">
              <Plus size={14} />
              New Application
            </Link>
          </div>
        ) : (
          <div className="card divide-y divide-hairline-soft">
            {apps?.slice(0, 5).map((app) => (
              <DashboardAppRow key={app.id} appId={app.id} name={app.name} image={app.image_name} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string;
  valueClass?: string;
  live?: boolean;
}

function StatCard({ label, value, valueClass, live }: StatCardProps) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-2">
        <p className="section-label">{label}</p>
        {live && value !== '—' && (
          <span className="w-1.5 h-1.5 rounded-full bg-semantic-success deploying-dot" />
        )}
      </div>
      <p className={`text-[26px] font-normal tracking-[-0.325px] leading-[1.25] text-ink ${valueClass ?? ''}`}>
        {value}
      </p>
    </div>
  );
}

// Row that shows status badge using shared cache (no extra fetch)
interface DashboardAppRowProps {
  appId: number;
  name: string;
  image: string;
}

function DashboardAppRow({ appId, name, image }: DashboardAppRowProps) {
  // Re-use the shared cache — no new request unless cache is cold
  const { data: deployment } = useDashboardStats_single(appId);

  return (
    <div className="flex items-center justify-between px-5 py-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="min-w-0">
          <p className="text-title-sm text-ink">{name}</p>
          <p className="text-caption text-muted font-mono truncate">{image}</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <StatusBadge status={deployment?.status ?? 'none'} />
        <Link
          to="/applications"
          className="btn-ghost text-muted no-underline text-[13px]"
        >
          Manage →
        </Link>
      </div>
    </div>
  );
}

// Thin wrapper to read a single app's status from the shared cache
import { useDeploymentStatus } from '../hooks/useDeployments';

function useDashboardStats_single(appId: number) {
  return useDeploymentStatus(appId, true);
}
