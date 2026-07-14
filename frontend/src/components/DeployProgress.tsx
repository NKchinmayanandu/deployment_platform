import type { DeploymentStatus } from '../types';

interface DeployProgressProps {
  status: DeploymentStatus | null;
}

const STEPS: { key: DeploymentStatus; label: string }[] = [
  { key: 'QUEUED', label: 'Queued' },
  { key: 'DEPLOYING', label: 'Deploying' },
  { key: 'RUNNING', label: 'Running' },
];

function stepIndex(status: DeploymentStatus | null): number {
  if (!status) return -1;
  // STARTING maps to DEPLOYING visually
  const normalised = status === 'STARTING' ? 'DEPLOYING' : status;
  return STEPS.findIndex((s) => s.key === normalised);
}

export function DeployProgress({ status }: DeployProgressProps) {
  const inProgress =
    status === 'QUEUED' || status === 'DEPLOYING' || status === 'STARTING' || status === 'RESTARTING';

  if (!inProgress) return null;

  const currentIdx = stepIndex(status);

  return (
    <div className="pt-1">
      {/* Indeterminate bar */}
      <div className="h-px bg-hairline mb-4 overflow-hidden rounded-full">
        <div className="h-full w-1/3 bg-[#b86000] progress-bar rounded-full opacity-60" />
      </div>

      {/* Step indicators */}
      <div className="flex items-center">
        {STEPS.map((step, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          const future = i > currentIdx;
          return (
            <div key={step.key} className="flex items-center">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={[
                    'w-1.5 h-1.5 rounded-full transition-colors duration-300',
                    done ? 'bg-semantic-success' : active ? 'bg-[#b86000] deploying-dot' : 'bg-hairline-strong',
                  ].join(' ')}
                />
                <span
                  className={[
                    'text-[10px] font-semibold uppercase tracking-[0.7px] transition-colors duration-300',
                    done
                      ? 'text-semantic-success'
                      : active
                      ? 'text-[#b86000]'
                      : future
                      ? 'text-muted-soft'
                      : 'text-muted',
                  ].join(' ')}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={[
                    'w-10 h-px mx-1.5 mb-4 transition-colors duration-300',
                    i < currentIdx ? 'bg-semantic-success' : 'bg-hairline',
                  ].join(' ')}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
