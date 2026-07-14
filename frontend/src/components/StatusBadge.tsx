import type { DeploymentStatus } from '../types';

interface StatusBadgeProps {
  status: DeploymentStatus | 'none';
}

export function StatusBadge({ status }: StatusBadgeProps) {
  switch (status) {
    case 'RUNNING':
      return (
        <span className="badge-success">
          <span className="w-1.5 h-1.5 rounded-full bg-semantic-success inline-block" />
          Running
        </span>
      );

    case 'DEPLOYING':
    case 'RESTARTING':
    case 'STARTING':
      return (
        <span className="badge-warning">
          <span className="w-1.5 h-1.5 rounded-full bg-[#b86000] inline-block deploying-dot" />
          {status === 'DEPLOYING' ? 'Deploying' : status === 'RESTARTING' ? 'Restarting' : 'Starting'}
        </span>
      );

    case 'QUEUED':
      return (
        <span className="badge-info">
          <span className="w-1.5 h-1.5 rounded-full bg-[#2d72c8] inline-block deploying-dot" />
          Queued
        </span>
      );

    case 'STOPPED':
      return (
        <span className="badge-muted">
          <span className="w-1.5 h-1.5 rounded-full bg-muted-soft inline-block" />
          Stopped
        </span>
      );

    case 'FAILED':
      return (
        <span className="badge-error">
          <span className="w-1.5 h-1.5 rounded-full bg-semantic-error inline-block" />
          Failed
        </span>
      );

    case 'REMOVED':
      return (
        <span className="badge-muted">Removed</span>
      );

    case 'none':
    default:
      return (
        <span className="badge-muted">Not Deployed</span>
      );
  }
}
