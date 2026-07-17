import { useState } from 'react';
import {
  Rocket,
  Play,
  RotateCcw,
  Square,
  Trash2,
  ScrollText,
  ExternalLink,
  Server,
  Clock,
  Link2,
} from 'lucide-react';
import type { Application, DeploymentStatus } from '../types';
import { StatusBadge } from './StatusBadge';
import { DeployProgress } from './DeployProgress';
import { LogsModal } from './LogsModal';
import {
  useDeploymentStatus,
  useDeployApplication,
  useStopDeployment,
  useStartDeployment,
  useRestartDeployment,
} from '../hooks/useDeployments';

interface AppCardProps {
  app: Application;
  onDelete: (id: number) => void;
}

// Has a deployment record at all (any status means it's been deployed before)
const HAS_DEPLOYMENT: DeploymentStatus[] = [
  'RUNNING', 'STOPPED', 'FAILED', 'DEPLOYING',
  'STARTING', 'RESTARTING', 'QUEUED', 'REMOVED',
];

// Statuses where we lock all action buttons
const TRANSITION_STATUSES: DeploymentStatus[] = [
  'QUEUED', 'DEPLOYING', 'STARTING', 'RESTARTING',
];

export function AppCard({ app, onDelete }: AppCardProps) {
  const [showLogs, setShowLogs] = useState(false);
  const { data: deployStatus, isLoading: statusLoading } = useDeploymentStatus(app.id, true);
  const deployMutation = useDeployApplication(app.id);
  const stopMutation = useStopDeployment(app.id);
  const startMutation = useStartDeployment(app.id);
  const restartMutation = useRestartDeployment(app.id);

  // ── Derive state purely from deployment status ──
  const rawStatus = deployStatus?.status ?? null;

  // Optimistic: show transitional state while mutations are in-flight
  const status: DeploymentStatus | null =
    deployMutation.isPending ? 'QUEUED'
    : stopMutation.isPending ? 'STOPPED'
    : startMutation.isPending ? 'STARTING'
    : restartMutation.isPending ? 'RESTARTING'
    : rawStatus;

  const hasDeployment = status !== null && HAS_DEPLOYMENT.includes(status);
  const isTransitioning = status !== null && TRANSITION_STATUSES.includes(status);
  const isRunning = status === 'RUNNING';
  const isStopped = status === 'STOPPED';
  const isFailed = status === 'FAILED';

  // Any mutation in flight
  const anyPending =
    deployMutation.isPending || stopMutation.isPending ||
    startMutation.isPending || restartMutation.isPending;

  // URL — sourced entirely from the backend; only shown as a link when RUNNING
  const deployUrl = deployStatus?.url ?? null;

  const formattedDate = new Date(app.created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="card p-6 flex flex-col gap-4">
      {/* ── Header: name + image + status badge ── */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-md bg-canvas border border-hairline flex items-center justify-center flex-shrink-0">
            <Server size={16} className="text-muted" />
          </div>
          <div className="min-w-0">
            <h3 className="text-title-sm text-ink truncate">{app.name}</h3>
            <p className="text-caption text-muted font-mono truncate">{app.image_name}</p>
          </div>
        </div>
        <div className="flex-shrink-0">
          {statusLoading && !deployStatus ? (
            <span className="badge-muted">—</span>
          ) : (
            <StatusBadge status={status ?? 'none'} />
          )}
        </div>
      </div>

      {/* ── Deploy progress (only during transition) ── */}
      {isTransitioning && <DeployProgress status={status} />}

      {/* ── Meta rows ── */}
      <div className="flex flex-col gap-1.5">
        {/* URL row — clickable only when RUNNING, otherwise dash */}
        <div className="flex items-center gap-2 min-w-0">
          <Link2 size={11} className="text-muted-soft flex-shrink-0" />
          <span className="section-label flex-shrink-0">URL</span>
          {isRunning && deployUrl ? (
            <a
              href={deployUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-caption text-body hover:text-ink transition-colors truncate font-mono"
            >
              {deployUrl}
            </a>
          ) : (
            <span className="text-caption text-muted-soft">
              {isStopped ? 'Offline' : hasDeployment ? '—' : 'Not deployed'}
            </span>
          )}
        </div>

        {/* Created At */}
        <div className="flex items-center gap-2">
          <Clock size={11} className="text-muted-soft flex-shrink-0" />
          <span className="section-label flex-shrink-0">Created</span>
          <span className="text-caption text-muted">{formattedDate}</span>
        </div>
      </div>

      {/* ── Divider ── */}
      <div className="border-t border-hairline-soft" />

      {/* ── Action bar — derived entirely from deployment status ── */}
      <div className="flex items-center gap-1 flex-wrap">

        {/* NEVER DEPLOYED → Deploy */}
        {!hasDeployment && !deployMutation.isPending && (
          <button
            className="btn-primary text-[13px] h-9 px-4"
            onClick={() => deployMutation.mutate()}
          >
            <Rocket size={13} />
            Deploy
          </button>
        )}

        {/* TRANSITIONING → disabled status label */}
        {isTransitioning && (
          <button className="btn-secondary text-[13px] h-9 px-4" disabled>
            <span className="w-2 h-2 rounded-full bg-[#b86000] deploying-dot" />
            {status === 'QUEUED' ? 'Queued…'
              : status === 'DEPLOYING' ? 'Deploying…'
              : status === 'RESTARTING' ? 'Restarting…'
              : 'Starting…'}
          </button>
        )}

        {/* RUNNING → Open, Restart, Stop */}
        {isRunning && (
          <>
            {deployUrl && (
              <a
                href={deployUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary text-[13px] h-9 px-4 no-underline"
              >
                <ExternalLink size={13} />
                Open
              </a>
            )}
            <button
              className="btn-ghost text-[13px]"
              onClick={() => restartMutation.mutate()}
              disabled={anyPending}
            >
              <RotateCcw size={13} />
              Restart
            </button>
            <button
              className="btn-ghost text-[13px]"
              onClick={() => stopMutation.mutate()}
              disabled={anyPending}
            >
              <Square size={13} />
              Stop
            </button>
          </>
        )}

        {/* STOPPED → Start */}
        {isStopped && (
          <button
            className="btn-primary text-[13px] h-9 px-4"
            onClick={() => startMutation.mutate()}
            disabled={anyPending}
          >
            <Play size={13} />
            Start
          </button>
        )}

        {/* FAILED → Redeploy */}
        {isFailed && (
          <button
            className="btn-primary text-[13px] h-9 px-4"
            onClick={() => deployMutation.mutate()}
            disabled={anyPending}
          >
            <RotateCcw size={13} />
            Redeploy
          </button>
        )}

        {/* ── Right-side: Logs + Delete (always present once deployed) ── */}
        <div className="ml-auto flex items-center gap-0.5">
          {hasDeployment && (
            <button
              className="btn-ghost text-[13px]"
              onClick={() => setShowLogs(true)}
            >
              <ScrollText size={13} />
              Logs
            </button>
          )}
          <button
            className="btn-ghost-danger text-[13px]"
            onClick={() => onDelete(app.id)}
            disabled={isTransitioning}
            title={isTransitioning ? 'Cannot delete while deploying' : 'Delete application'}
          >
            <Trash2 size={13} />
            Delete
          </button>
        </div>
      </div>

      {/* ── Logs Modal ── */}
      {showLogs && (
        <LogsModal
          appId={app.id}
          appName={app.name}
          onClose={() => setShowLogs(false)}
        />
      )}
    </div>
  );
}
