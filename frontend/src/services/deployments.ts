import { api } from './api';
import type { Application, ApplicationCreate, DeploymentStatusResponse, LoginResponse, User } from '../types';

// Auth
export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', password);
  const { data } = await api.post<LoginResponse>('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

export const register = async (email: string, password: string): Promise<User> => {
  const { data } = await api.post<User>('/auth/register', { email, password });
  return data;
};

export const getMe = async (): Promise<User> => {
  const { data } = await api.get<User>('/auth/me');
  return data;
};

// Applications
export const listApplications = async (): Promise<Application[]> => {
  const { data } = await api.get<Application[]>('/applications/');
  return data;
};

export const createApplication = async (payload: ApplicationCreate): Promise<Application> => {
  const { data } = await api.post<Application>('/applications/', payload);
  return data;
};

export const deleteApplication = async (appId: number): Promise<void> => {
  await api.delete(`/applications/${appId}`);
};

// Deployments
export const deployApplication = async (appId: number): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>(`/deployments/${appId}/deploy`);
  return data;
};

export const getDeploymentStatus = async (appId: number): Promise<DeploymentStatusResponse> => {
  const { data } = await api.get<DeploymentStatusResponse>(`/deployments/${appId}/status`);
  return data;
};

export const stopDeployment = async (appId: number): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>(`/deployments/${appId}/stop`);
  return data;
};

export const restartDeployment = async (appId: number): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>(`/deployments/${appId}/restart`);
  return data;
};

export const startDeployment = async (appId: number): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>(`/deployments/${appId}/start`);
  return data;
};

export const getDeploymentLogs = async (appId: number): Promise<{ logs: string[] }> => {
  const { data } = await api.get<{ logs: string[] }>(`/deployments/${appId}/logs`);
  return data;
};
