import { useState } from 'react';
import { Plus, Box, AlertCircle } from 'lucide-react';
import { AppCard } from '../components/AppCard';
import { CreateAppModal } from '../components/CreateAppModal';
import { useApplications, useDeleteApplication } from '../hooks/useDeployments';

export function ApplicationsPage() {
  const [showModal, setShowModal] = useState(false);
  const { data: apps, isLoading, isError } = useApplications();
  const deleteMutation = useDeleteApplication();

  const handleDelete = (id: number) => {
    if (window.confirm('Delete this application? This cannot be undone.')) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="px-10 py-10 max-w-5xl">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <p className="section-label mb-1">Platform</p>
          <h1 className="text-[26px] font-normal tracking-[-0.325px] leading-[1.25] text-ink">
            Applications
          </h1>
        </div>
        <button
          className="btn-primary"
          onClick={() => setShowModal(true)}
        >
          <Plus size={15} />
          New Application
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center gap-3 py-16 text-muted">
          <div className="w-4 h-4 rounded-full border-2 border-hairline-strong border-t-muted animate-spin" />
          <span className="text-body-sm">Loading applications…</span>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="flex items-center gap-2 py-8 text-semantic-error text-body-sm">
          <AlertCircle size={15} />
          <span>Failed to load applications. Check your connection.</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && apps?.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-12 h-12 rounded-lg bg-surface-strong border border-hairline flex items-center justify-center mb-4">
            <Box size={20} className="text-muted-soft" />
          </div>
          <h2 className="text-title-sm text-ink mb-1">No applications yet</h2>
          <p className="text-body-sm text-muted mb-6 max-w-xs">
            Create your first application to start deploying Docker containers.
          </p>
          <button className="btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={15} />
            New Application
          </button>
        </div>
      )}

      {/* Applications grid */}
      {apps && apps.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {apps.map((app) => (
            <AppCard key={app.id} app={app} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && <CreateAppModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
