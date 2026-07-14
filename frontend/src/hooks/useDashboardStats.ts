import { useQueries } from '@tanstack/react-query';
import { getDeploymentStatus } from '../services/deployments';
import { useApplications } from './useDeployments';

/**
 * Fetches all deployment statuses in parallel (shared cache).
 * Polls every 5s — lighter than the card-level 2s, just enough to
 * keep the dashboard counts live without hammering the API.
 */
export function useDashboardStats() {
  const { data: apps, isLoading: appsLoading } = useApplications();
  const appIds = apps?.map((a) => a.id) ?? [];

  const statusQueries = useQueries({
    queries: appIds.map((id) => ({
      queryKey: ['deployment-status', id],
      queryFn: () => getDeploymentStatus(id),
      refetchInterval: 5000,
      retry: false,
      staleTime: 4000,
    })),
  });

  const total = appIds.length;
  const running = statusQueries.filter((q) => q.data?.status === 'RUNNING').length;
  const isLoading = appsLoading || statusQueries.some((q) => q.isLoading);

  return { total, running, isLoading };
}
