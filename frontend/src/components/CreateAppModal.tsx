import { useState } from 'react';
import { X, AlertCircle, Info } from 'lucide-react';
import { useCreateApplication } from '../hooks/useDeployments';
import { EnvVarsEditor, useEnvVars } from './EnvVarsEditor';

interface CreateAppModalProps {
  onClose: () => void;
}

const PORT_MIN = 1;
const PORT_MAX = 65535;

function validatePort(value: string): string | null {
  if (value.trim() === '') return 'Container port is required.';
  const n = Number(value);
  if (!Number.isInteger(n) || n < PORT_MIN || n > PORT_MAX) {
    return `Port must be a whole number between ${PORT_MIN} and ${PORT_MAX}.`;
  }
  return null;
}

export function CreateAppModal({ onClose }: CreateAppModalProps) {
  const [name, setName] = useState('');
  const [imageName, setImageName] = useState('');
  const [containerPort, setContainerPort] = useState('8000');
  const [portError, setPortError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const { vars, setVars, toJSON } = useEnvVars();

  const mutation = useCreateApplication();

  const handlePortChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setContainerPort(val);
    // Clear the error as soon as the user starts editing again
    if (portError) setPortError(validatePort(val));
  };

  const handlePortBlur = () => {
    setPortError(validatePort(containerPort));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!name.trim() || !imageName.trim()) {
      setFormError('Application name and Docker image are required.');
      return;
    }

    const pErr = validatePort(containerPort);
    if (pErr) {
      setPortError(pErr);
      return;
    }

    try {
      await mutation.mutateAsync({
        name: name.trim(),
        image_name: imageName.trim(),
        container_port: parseInt(containerPort, 10), // ← sent as integer to FastAPI
        env_vars: toJSON(),
      });
      onClose();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to create application.';
      setFormError(msg);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative card w-full max-w-xl p-8 z-10">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-[22px] font-normal tracking-[-0.11px] leading-[1.3] text-ink">
              New Application
            </h2>
            <p className="text-body-sm text-muted mt-1">
              Provide a name and Docker image to get started.
            </p>
          </div>
          <button
            className="btn-ghost w-9 h-9 p-0"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Application Name */}
          <div className="flex flex-col gap-2">
            <label htmlFor="app-name" className="section-label">
              Application Name
            </label>
            <input
              id="app-name"
              className="input"
              placeholder="my-service"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>

          {/* Docker Image */}
          <div className="flex flex-col gap-2">
            <label htmlFor="app-image" className="section-label">
              Docker Image
            </label>
            <input
              id="app-image"
              className="input font-mono"
              placeholder="nginx:latest"
              value={imageName}
              onChange={(e) => setImageName(e.target.value)}
            />
          </div>

          {/* Internal Container Port */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1.5">
              <label htmlFor="app-container-port" className="section-label">
                Internal Container Port
              </label>
              {/* Tooltip trigger */}
              <div className="group relative flex items-center">
                <Info size={12} className="text-muted cursor-default" />
                <div
                  role="tooltip"
                  className={[
                    'pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20',
                    'w-64 rounded-md bg-ink text-canvas text-[12px] leading-[1.5] px-3 py-2 shadow-lg',
                    'opacity-0 group-hover:opacity-100 transition-opacity duration-150',
                  ].join(' ')}
                >
                  Enter the port your application listens on internally.
                  The platform will route external traffic to this port.
                  {/* Arrow */}
                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-ink" />
                </div>
              </div>
            </div>

            <input
              id="app-container-port"
              type="number"
              min={PORT_MIN}
              max={PORT_MAX}
              step={1}
              className={[
                'input font-mono',
                portError ? 'border-semantic-error focus:border-semantic-error' : '',
              ].join(' ')}
              placeholder="8000"
              value={containerPort}
              onChange={handlePortChange}
              onBlur={handlePortBlur}
              aria-describedby={portError ? 'port-error' : 'port-hint'}
              aria-invalid={!!portError}
            />

            {portError ? (
              <p id="port-error" className="flex items-center gap-1.5 text-[12px] text-semantic-error">
                <AlertCircle size={12} />
                {portError}
              </p>
            ) : (
              <p id="port-hint" className="text-[12px] text-muted leading-[1.5]">
                The port your container listens on (e.g.&nbsp;3000, 8000, 5000).
              </p>
            )}
          </div>

          {/* ── Environment Variables ── */}
          <div className="border-t border-hairline pt-5">
            <EnvVarsEditor vars={vars} onChange={setVars} />
          </div>

          {formError && (
            <div className="flex items-center gap-2 text-semantic-error text-body-sm">
              <AlertCircle size={14} />
              <span>{formError}</span>
            </div>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              className="btn-secondary flex-1"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary flex-1"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? 'Creating…' : 'Create Application'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
