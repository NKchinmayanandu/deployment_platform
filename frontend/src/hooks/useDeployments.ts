import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listApplications,
  createApplication,
  deleteApplication,
  deployApplication,
  getDeploymentStatus,
  stopDeployment,
  startDeployment,
  restartDeployment,
  getDeploymentLogs,
} from '../services/deployments';
import type { ApplicationCreate, DeploymentStatus } from '../types';

export function useApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: listApplications,
    staleTime: 30_000,
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ApplicationCreate) => createApplication(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  });
}

export function useDeleteApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (appId: number) => deleteApplication(appId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  });
}

export function useDeployApplication(appId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deployApplication(appId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deployment-status', appId] });
    },
  });
}

export function useStopDeployment(appId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => stopDeployment(appId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deployment-status', appId] });
    },
  });
}

export function useStartDeployment(appId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => startDeployment(appId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deployment-status', appId] });
    },
  });
}

export function useRestartDeployment(appId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => restartDeployment(appId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deployment-status', appId] });
    },
  });
}

// Statuses that keep polling active
const ACTIVE_STATUSES: DeploymentStatus[] = ['QUEUED', 'DEPLOYING', 'RESTARTING', 'STARTING'];

export function useDeploymentStatus(appId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['deployment-status', appId],
    queryFn: () => getDeploymentStatus(appId),
    enabled,
    // Poll every 2s while transitioning; stop on terminal status; always poll if no data yet
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status) return 2000;
      return ACTIVE_STATUSES.includes(status) ? 2000 : false;
    },
    retry: false,
  });
}

export function useDeploymentLogs(appId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['deployment-logs', appId],
    queryFn: () => getDeploymentLogs(appId),
    enabled,
    refetchInterval: 3000,
  });
}
