import { useState } from 'react';
import { X, AlertCircle } from 'lucide-react';
import { useCreateApplication } from '../hooks/useDeployments';

interface CreateAppModalProps {
  onClose: () => void;
}

export function CreateAppModal({ onClose }: CreateAppModalProps) {
  const [name, setName] = useState('');
  const [imageName, setImageName] = useState('');
  const [error, setError] = useState<string | null>(null);

  const mutation = useCreateApplication();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim() || !imageName.trim()) {
      setError('Both fields are required.');
      return;
    }

    try {
      await mutation.mutateAsync({ name: name.trim(), image_name: imageName.trim() });
      onClose();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to create application.';
      setError(msg);
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
      <div className="relative card w-full max-w-md p-8 z-10">
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

          {error && (
            <div className="flex items-center gap-2 text-semantic-error text-body-sm">
              <AlertCircle size={14} />
              <span>{error}</span>
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
